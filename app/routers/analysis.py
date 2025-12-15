from datetime import date

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..dao.news_info_dao import fetch_news_info_rows
from ..dao.news_item_dao import fetch_news_item_rows_not_extracted
from ..services import extract_keywords_task
from ..services.analysis_service import (
    async_tfidf_top, build_news_item_from_news_info, embedding_cluster_pipeline, list_news_events,
    get_news_event_detail,
)
from ..services.extract_news_service import extract_news_items_task, extract_news_event_task

router = APIRouter(prefix="/api/analysis")


class BaseQuery(BaseModel):
    limit: int = Field(50, ge=1, le=100)
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


@router.post("/extract_news", summary="提取新闻item")
async def extract_news_item_from_news_info(params: BaseQuery):
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
    limit: int = Field(500, ge=1, le=500)
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


#@router.post("/tfidf", summary="生成 TF-IDF Top N 关键词")
async def extract_tfidf_top_keywords(params: TFIDFQuery):
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

    tops = await async_tfidf_top(rows, top_n=params.top_k)
    # 执行提取关键字的事务作业
    await extract_keywords_task(tops)
    return {"status": "ok", "msgs": "generate success"}


@router.post("/extract_event", summary="提取新闻event")
async def extract_news_event():
    """
     执行提取新闻事件的作业
    :return:
    """
    await extract_news_event_task()
    return {"status": "ok", "msgs": "extract_event success"}


@router.get("/events")
async def get_news_events(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        order_by: str = Query("score"),
        order_desc: bool = Query(True),
        status: int | None = Query(0),
):
    return await list_news_events(
        page=page,
        page_size=page_size,
        order_by=order_by,
        order_desc=order_desc,
        status=status,
    )


@router.get("/events/{event_id}")
async def get_event_detail(
        event_id: int,
):
    data = await get_news_event_detail(event_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return data


# class WordcloudQuery(TFIDFQuery):
#     pass
#
#
# @router.get("/wordcloud", summary="生成词云并返回图片 URL")
# async def wordcloud(params: WordcloudQuery = Depends()):
#     rows = await fetch_news_item_rows_not_extracted(params.start_date, params.end_date, limit=params.limit)
#     corpus = await docs_to_corpus(rows)
#     if not corpus:
#         raise HTTPException(status_code=404, detail="No documents")
#
#     out = await async_generate_wordcloud(corpus)
#     # return direct file or url path list
#     return {"urls": out}
#
#
# @router.post("/wordcloud/generate", summary="生成最新词云图")
# async def generate_wordcloud(
#     gene_date: str | None = Body(None),
#     force: bool | None = Body(False),
# ):
#     # 1. 确定日期
#     now_date = datetime.now()
#     if gene_date is None:
#         gene_date = now_date.strftime("%Y-%m-%d")
#
#     # 2. 如果已有文件且 force == False，则返回已有路径
#     dir_path = os.path.join(settings.WORDCLOUD_DIR, gene_date)
#     if os.path.exists(dir_path) and not force:
#         image_path = _get_latest_wordcloud_file(gene_date)
#         return {"status": "exists", "date": gene_date, "image_path": image_path}
#
#     # 3. 获取生成词云的数据
#     rows = await fetch_news_item_rows_not_extracted(start_date=now_date.date(), end_date=now_date.date())
#     corpus = await docs_to_corpus(rows)
#
#     # 4. 调用业务逻辑生成词云
#     image_path = await async_generate_wordcloud(corpus)
#
#     return {"status": "ok", "date": gene_date, "image_path": image_path[0]}
#
#
# # -------------------------
# # 内部函数：返回最新文件
# # -------------------------
# def _get_latest_wordcloud_file(folder: str) -> str | None:
#     """返回指定文件夹中修改时间最新的文件路径"""
#
#     wordcloud_pic_dir = os.path.join(settings.WORDCLOUD_DIR, folder)
#
#     if not os.path.exists(wordcloud_pic_dir):
#         return None
#     files_dir = [
#         os.path.join(wordcloud_pic_dir, f) for f in os.listdir(wordcloud_pic_dir)
#     ]
#     files = [f for f in files_dir if os.path.isfile(f)]
#     if not files:
#         return None
#     # 按修改时间排序
#     latest_file = max(files, key=lambda f: os.path.getmtime(f))
#     return latest_file
#
#
# @router.get("/wordcloud/image", summary="获取词云图片（默认当天日期）")
# async def wordcloud_image_default():
#     """
#     获取当天的词云图
#     :return:
#     """
#     wordcloud_date = datetime.now().strftime("%Y-%m-%d")
#     latest_file = _get_latest_wordcloud_file(wordcloud_date)
#     if not latest_file:
#         raise HTTPException(status_code=404, detail="当天没有可用词云图片")
#     return FileResponse(latest_file, media_type="image/png")
#
#
# def get_latest_date_folder():
#     """
#     获取最新更新的文件夹
#     :return:
#     """
#     folders = []
#     for name in os.listdir(settings.WORDCLOUD_DIR):
#         if re.fullmatch(r"\d{4}-\d{2}-\d{2}", name):
#             folders.append(name)
#
#     if not folders:
#         return None
#
#     # 依赖日期格式排序即可
#     return max(folders)
#
#
# @router.get("/wordcloud/image/latest", summary="获取最新生成的词云图片")
# async def wordcloud_image_latest():
#     # 遍历 WORDCLOUD_DIR 下的日期子文件夹
#     if not os.path.exists(settings.WORDCLOUD_DIR):
#         raise HTTPException(status_code=404, detail="没有可用的词云图片")
#
#     latest_folder = get_latest_date_folder()
#     if not latest_folder:
#         raise HTTPException(status_code=404, detail="没有可用的词云图片")
#
#     # 找到所有文件夹下的最新文件
#     latest_file = _get_latest_wordcloud_file(latest_folder)
#
#     if not latest_file:
#         raise HTTPException(status_code=404, detail="没有可用的词云图片")
#
#     return FileResponse(latest_file, media_type="image/png")
#
#
# @router.get("/wordcloud/image/{wordcloud_date}", summary="获取词云图片（指定日期）")
# async def wordcloud_image_with_date(
#     wordcloud_date: str = Path(..., description="日期，格式 YYYY-MM-DD")
# ):
#     """
#     获取指定日期的词云图
#     :param wordcloud_date:
#     :return:
#     """
#     # 校验日期格式
#     try:
#         datetime.strptime(wordcloud_date, "%Y-%m-%d")
#     except ValueError:
#         raise HTTPException(status_code=422, detail="日期格式错误，必须为 YYYY-MM-DD")
#
#     latest_file = _get_latest_wordcloud_file(wordcloud_date)
#     if not latest_file:
#         raise HTTPException(
#             status_code=404, detail=f"{wordcloud_date} 没有可用词云图片"
#         )
#     return FileResponse(latest_file, media_type="image/png")
