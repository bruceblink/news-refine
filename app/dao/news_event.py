from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import news_item, news_event, news_event_item


async def step1_insert_news_event(session: AsyncSession) -> None:
    """
    从 news_item 聚合生成 news_event
    只写事实字段：event_date / cluster_id / news_count
    """

    subq = (
        select(
            news_item.c.published_at.label("event_date"),
            news_item.c.cluster_id.label("cluster_id"),
            func.count().label("news_count"),
        )
        .where(news_item.c.cluster_id.is_not(None))
        .group_by(
            news_item.c.published_at,
            news_item.c.cluster_id,
        )
        .having(func.count() >= 2)
    )

    stmt = (
        insert(news_event)
        .from_select(
            ["event_date", "cluster_id", "news_count"],
            subq,
        )
        .on_conflict_do_nothing()
    )

    await session.execute(stmt)


async def step2_insert_news_event_item(session: AsyncSession) -> None:
    """
    建立 news_event 与 news_item 的关联关系
    """

    join_select = (
        select(
            news_event.c.id.label("event_id"),
            news_item.c.id.label("news_id"),
        )
        .select_from(
            news_event.join(
                news_item,
                (news_event.c.cluster_id == news_item.c.cluster_id)
                & (news_event.c.event_date == news_item.c.published_at),
                )
        )
    )

    stmt = (
        insert(news_event_item)
        .from_select(
            ["event_id", "news_id"],
            join_select,
        )
        .on_conflict_do_nothing()
    )

    await session.execute(stmt)
