from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..dao.stats_dao import (
    fetch_hot_events,
    count_hot_events,
    fetch_top_news_by_event_ids,
    fetch_trending_keywords,
)
from ..db import AsyncSessionLocal

router = APIRouter(prefix="/api/stats")


# ── 热点相关响应模型 ─────────────────────────────────────────

class TopNewsItem(BaseModel):
    id: int
    title: str | None
    source: str | None
    url: str | None
    published_at: str | None


class HotEventItem(BaseModel):
    id: int
    event_date: str | None
    title: str | None
    summary: str | None
    news_count: int | None
    score: float | None
    top_news: list[TopNewsItem]


class HotResponse(BaseModel):
    items: list[HotEventItem]
    page: int
    pageSize: int
    total: int


# ── 趋势相关响应模型 ─────────────────────────────────────────

class TrendKeyword(BaseModel):
    keyword: str
    weight: float
    count: int


class DayTrend(BaseModel):
    date: str
    keywords: list[TrendKeyword]


class TrendResponse(BaseModel):
    trends: list[DayTrend]
    days: int


# ── 路由 ─────────────────────────────────────────────────────

@router.get("/hot", response_model=HotResponse, summary="热点事件列表")
async def hot_events(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    start_date: date | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: date | None = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    返回按热度（score）降序排列的热点事件列表，每个事件附带 top 3 新闻。

    - **page** / **pageSize**: 分页参数
    - **start_date** / **end_date**: 日期范围过滤（可选）
    """
    async with AsyncSessionLocal() as session:
        events = await fetch_hot_events(
            session,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=pageSize,
        )
        total = await count_hot_events(
            session,
            start_date=start_date,
            end_date=end_date,
        )

        event_ids = [e["id"] for e in events]
        top_news_map = await fetch_top_news_by_event_ids(session, event_ids, top_n=3)

    items = [
        HotEventItem(
            id=e["id"],
            event_date=e["event_date"].isoformat() if e["event_date"] else None,
            title=e["title"],
            summary=e["summary"],
            news_count=e["news_count"],
            score=e["score"],
            top_news=[TopNewsItem(**n) for n in top_news_map.get(e["id"], [])],
        )
        for e in events
    ]

    return HotResponse(items=items, page=page, pageSize=pageSize, total=total)


@router.get("/trend", response_model=TrendResponse, summary="关键词趋势")
async def keyword_trend(
    days: int = Query(7, ge=1, le=30, description="趋势天数（最近 N 天）"),
    top_k: int = Query(10, ge=1, le=50, description="每天返回的关键词数"),
):
    """
    返回最近 N 天每天的热门关键词趋势，按关键词权重合计降序排列。

    - **days**: 最近 N 天（1-30，默认 7）
    - **top_k**: 每天最多返回关键词数（1-50，默认 10）
    """
    async with AsyncSessionLocal() as session:
        trends = await fetch_trending_keywords(session, days=days, top_k=top_k)

    return TrendResponse(
        trends=[DayTrend(**t) for t in trends],
        days=days,
    )
