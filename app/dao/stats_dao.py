from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.dto import HotEventDTO, TopNewsItemDTO, DayTrendDTO, DayTrendKeywordDTO
from app.models import news_event, news_event_item, news_item, news_keywords


async def fetch_hot_events(
    session: AsyncSession,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[HotEventDTO]:
    """
    查询热点事件列表（只返回根事件，按 score 降序）
    """
    offset = (page - 1) * page_size

    stmt = select(
        news_event.c.id,
        news_event.c.event_date,
        news_event.c.title,
        news_event.c.summary,
        news_event.c.news_count,
        news_event.c.score,
    ).where(
        news_event.c.parent_event_id.is_(None),
        news_event.c.title.is_not(None),
    )

    if start_date is not None:
        stmt = stmt.where(news_event.c.event_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(news_event.c.event_date <= end_date)

    stmt = (
        stmt.order_by(
            desc(news_event.c.score),
            desc(news_event.c.event_date),
        )
        .limit(page_size)
        .offset(offset)
    )

    result = await session.execute(stmt)
    return [HotEventDTO(**r) for r in result.mappings().all()]


async def count_hot_events(
    session: AsyncSession,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """
    统计热点事件总数（只统计根事件）
    """
    stmt = select(func.count()).select_from(news_event).where(
        news_event.c.parent_event_id.is_(None),
        news_event.c.title.is_not(None),
    )

    if start_date is not None:
        stmt = stmt.where(news_event.c.event_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(news_event.c.event_date <= end_date)

    result = await session.execute(stmt)
    return result.scalar_one()


async def fetch_top_news_by_event_ids(
    session: AsyncSession,
    event_ids: list[int],
    top_n: int = 3,
) -> dict[int, list[TopNewsItemDTO]]:
    """
    批量获取多个事件下的 top N 新闻（按 news_item.id 升序取前 N 条）
    使用 ROW_NUMBER() 窗口函数一次查询完成。
    """
    if not event_ids:
        return {}

    rn_col = func.row_number().over(
        partition_by=news_event_item.c.event_id,
        order_by=asc(news_item.c.id),
    ).label("rn")

    subq = (
        select(
            news_event_item.c.event_id,
            news_item.c.id,
            news_item.c.title,
            news_item.c.source,
            news_item.c.published_at,
            news_item.c.url,
            rn_col,
        )
        .select_from(
            news_event_item.join(news_item, news_event_item.c.news_id == news_item.c.id)
        )
        .where(news_event_item.c.event_id.in_(event_ids))
        .subquery()
    )

    stmt = select(subq).where(subq.c.rn <= top_n)
    result = await session.execute(stmt)
    rows = result.mappings().all()

    grouped: dict[int, list[TopNewsItemDTO]] = defaultdict(list)
    for r in rows:
        grouped[r["event_id"]].append(
            TopNewsItemDTO(
                id=r["id"],
                title=r["title"],
                source=r["source"],
                url=r["url"],
                published_at=(
                    r["published_at"].isoformat() if r["published_at"] else None
                ),
            )
        )
    return dict(grouped)


async def fetch_trending_keywords(
    session: AsyncSession,
    *,
    days: int = 7,
    top_k: int = 10,
) -> list[DayTrendDTO]:
    """
    返回最近 N 天每天热门关键词（按关键词权重合计降序）。
    结果格式：[{"date": "YYYY-MM-DD", "keywords": [{"keyword", "weight", "count"}]}]
    """
    since = date.today() - timedelta(days=days - 1)

    agg_subq = (
        select(
            news_item.c.published_at.label("pub_date"),
            news_keywords.c.keyword.label("keyword"),
            func.sum(news_keywords.c.weight).label("total_weight"),
            func.count().label("doc_count"),
        )
        .select_from(
            news_keywords.join(news_item, news_keywords.c.news_id == news_item.c.id)
        )
        .where(news_item.c.published_at >= since)
        .group_by(news_item.c.published_at, news_keywords.c.keyword)
        .subquery()
    )

    ranked_subq = (
        select(
            agg_subq.c.pub_date,
            agg_subq.c.keyword,
            agg_subq.c.total_weight,
            agg_subq.c.doc_count,
            func.row_number().over(
                partition_by=agg_subq.c.pub_date,
                order_by=agg_subq.c.total_weight.desc(),
            ).label("rn"),
        )
        .subquery()
    )

    stmt = (
        select(
            ranked_subq.c.pub_date,
            ranked_subq.c.keyword,
            ranked_subq.c.total_weight,
            ranked_subq.c.doc_count,
        )
        .where(ranked_subq.c.rn <= top_k)
        .order_by(ranked_subq.c.pub_date.desc(), ranked_subq.c.total_weight.desc())
    )

    rows = (await session.execute(stmt)).all()

    grouped: dict[str, list[DayTrendKeywordDTO]] = defaultdict(list)
    for r in rows:
        d = r.pub_date.isoformat() if r.pub_date else "unknown"
        grouped[d].append(
            DayTrendKeywordDTO(
                keyword=r.keyword,
                weight=round(float(r.total_weight), 4) if r.total_weight else 0.0,
                count=r.doc_count,
            )
        )

    return [
        DayTrendDTO(date=d, keywords=grouped[d])
        for d in sorted(grouped.keys(), reverse=True)
    ]

