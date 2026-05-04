from datetime import date, timedelta

from fastapi import APIRouter, Query, HTTPException, Depends, Request
from pydantic import BaseModel, Field, field_validator

from ..auth import require_permission, swagger_auth
from ..core.rate_limit import limiter
from ..dao.news_info_dao import fetch_news_info_rows
from ..dao.news_item_dao import fetch_news_item_rows_not_extracted
from ..services import extract_keywords_task
from ..services.analysis_service import (
    async_tfidf_top, build_news_item_from_news_info, embedding_cluster_pipeline, list_news_events,
    get_news_event_detail, merge_cross_day_events_task, docs_to_corpus, async_generate_wordcloud,
)
from ..config import settings
from ..services.extract_news_service import extract_news_items_task, extract_news_event_task

router = APIRouter(prefix="/api/analysis")


# ── 通用响应模型 ────────────────────────────────────────────
class StatusResponse(BaseModel):
    status: str
    msgs: str


# ── 事件相关响应模型 ─────────────────────────────────────────
class NewsEventItem(BaseModel):
    id: int
    event_date: date | None
    title: str | None
    summary: str | None
    news_count: int | None
    score: float | None
    status: int | None


class NewsEventListResponse(BaseModel):
    status: str
    data: dict


class NewsItemInEvent(BaseModel):
    id: int
    title: str | None
    url: str | None
    source: str | None
    published_at: date | None


class NewsEventDetailResponse(BaseModel):
    event: dict
    news_items: list
    page: int
    pageSize: int
    totalCount: int


# ── 词云响应模型 ─────────────────────────────────────────────
class WordcloudResponse(BaseModel):
    urls: list[str]


class BaseQuery(BaseModel):
    limit: int = Field(30, ge=1, le=100)
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def check_date_format(cls, v):
        if v is None:
            return v
        try:
            return date.fromisoformat(v)
        except ValueError:
            raise ValueError("日期格式错误，应为 YYYY-MM-DD")


@router.post("/extract_news_item", summary="提取新闻item", response_model=StatusResponse)
@limiter.limit("5/minute")
async def extract_news_item(request: Request, params: BaseQuery):
    """
     从原始新闻数据中提取news_item

    - **limit**: 处理的最大新闻数量 (1-100, 默认50)
    - **start_date**: 开始日期 (格式: YYYY-MM-DD)
    - **end_date**: 结束日期 (格式: YYYY-MM-DD)
    """

    # 查询待处理的news_info
    rows = await fetch_news_info_rows(params.start_date, params.end_date, limit=params.limit)

    if not rows:
        return {"status": "ok", "msgs": "no news_info to fetch"}
    # 数据转换
    news_items = build_news_item_from_news_info(rows)
    # 生成embeddings + cluster
    # 1. 获取title list
    title_list = [item["title"] or "" for item in news_items]
    # 2. 执行embeddings -> cluster pipeline
    cluster_ids, cluster_method = embedding_cluster_pipeline(
        title_list,
        n_clusters=params.limit
    )
    # 3. 合并结果
    for item, cid in zip(news_items, cluster_ids):
        item["cluster_id"] = cid
        item["cluster_method"] = cluster_method
    # 执行提取news_item的事务作业
    await extract_news_items_task(news_items)
    return {"status": "ok", "msgs": "news item extract success"}


class TFIDFQuery(BaseModel):
    limit: int = Field(200, ge=1, le=500)
    top_k: int = Field(5, ge=1, le=10)
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def check_date_format(cls, v):
        if v is None:
            return v
        try:
            return date.fromisoformat(v)
        except ValueError:
            raise ValueError("日期格式错误，应为 YYYY-MM-DD")


@router.post("/tfidf", summary="生成 TF-IDF Top N 关键词", response_model=StatusResponse)
@limiter.limit("10/minute")
async def extract_tfidf_top_keywords(request: Request, params: TFIDFQuery):
    """
     请求计算 TF-IDF Top N 词

    - **limit**: 处理的最大新闻数量 (1-500)
    - **top_k**: 返回的关键词数量 (1-10)
    - **start_date**: 开始日期 (格式: YYYY-MM-DD)
    - **end_date**: 结束日期 (格式: YYYY-MM-DD)
    """
    rows = await fetch_news_item_rows_not_extracted(params.start_date, params.end_date, limit=params.limit)

    if not rows:
        return {"status": "ok", "msgs": "no data to generate"}

    tops = await async_tfidf_top(rows, top_n=params.top_k, max_features=settings.TFIDF_MAX_FEATURES)
    # 执行提取关键字的事务作业
    await extract_keywords_task(tops)
    return {"status": "ok", "msgs": "generate success"}


@router.post("/extract_news_event", summary="提取新闻event", response_model=StatusResponse)
@limiter.limit("5/minute")
async def extract_news_event(request: Request):
    """
     执行提取新闻事件的作业
    :return:
    """
    await extract_news_event_task()
    return {"status": "ok", "msgs": "extract_event success"}


@router.get("/events", dependencies=[Depends(require_permission("event:read"))], response_model=NewsEventListResponse)
@limiter.limit("20/minute")
async def get_news_events(
        request: Request,
        page: int = Query(1, ge=1),
        pageSize: int = Query(20, ge=1, le=100),
        orderBy: str = Query("score"),
        orderDesc: bool = Query(True),
        status: int | None = Query(0),
        token: str = Depends(swagger_auth)
):
    data = await list_news_events(
        page=page,
        page_size=pageSize,
        order_by=orderBy,
        order_desc=orderDesc,
        status=status,
    )
    return {
        "status": "ok",
        "data": data
    }


@router.get("/events/{event_id}", response_model=NewsEventDetailResponse)
@limiter.limit("30/minute")
async def get_event_detail(
        request: Request,
        event_id: int,
        page: int = Query(1, ge=1),
        pageSize: int = Query(20, ge=1, le=100),
):
    data = await get_news_event_detail(event_id, page=page, page_size=pageSize)
    if data is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return data


# ── 词云接口 ─────────────────────────────────────────────────
class WordcloudQuery(BaseModel):
    limit: int = Field(30, ge=1, le=200)
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def check_date_format(cls, v):
        if v is None:
            return v
        try:
            return date.fromisoformat(v)
        except ValueError:
            raise ValueError("日期格式错误，应为 YYYY-MM-DD")


@router.get("/wordcloud", summary="生成词云并返回图片 URL 列表", response_model=WordcloudResponse)
@limiter.limit("10/minute")
async def wordcloud(request: Request, params: WordcloudQuery = Depends()):
    """
    基于指定日期范围内的原始新闻数据生成词云图片。

    - **limit**: 处理的最大新闻来源条数 (1-200, 默认50)
    - **start_date**: 开始日期 (格式: YYYY-MM-DD)
    - **end_date**: 结束日期 (格式: YYYY-MM-DD)
    """
    rows = await fetch_news_info_rows(params.start_date, params.end_date, limit=params.limit)
    if not rows:
        raise HTTPException(status_code=404, detail="指定日期范围内无可用数据")

    corpus = await docs_to_corpus(rows)
    if not corpus:
        raise HTTPException(status_code=404, detail="语料为空，无法生成词云")

    urls = await async_generate_wordcloud(corpus)
    return WordcloudResponse(urls=urls)


@router.post("/merge_event", summary="合并新闻event", response_model=StatusResponse)
@limiter.limit("5/minute")
async def merge_cross_day_news_events(request: Request, days: int = Query(2, ge=1, le=30)):
    """
     合并最近 N 天的事件（默认 2 天）
    :return:
    """
    today = date.today()

    for i in range(1, days + 1):
        event_date = today - timedelta(days=i)
        await merge_cross_day_events_task(event_date)

    return {
        "status": "ok",
        "msgs": f"merge_event success, processed {days} days up to {today}"
    }

