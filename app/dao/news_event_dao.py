from sqlalchemy import select, func, update
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


async def step3_fill_event_title_and_summary(
        session: AsyncSession,
        summary_len: int = 300,
) -> None:
    """
    为 news_event 回填 title / summary
    规则：选事件中最早发布的新闻
    只处理 title 为空的事件
    """

    # 子查询：每个 event 选一条代表新闻
    rep_news_subq = (
        select(
            news_event.c.id.label("event_id"),
            news_item.c.title.label("title"),
            news_item.c.content.label("content"),
        )
        .distinct(news_event.c.id)
        .select_from(
            news_event
            .join(news_event_item, news_event.c.id == news_event_item.c.event_id)
            .join(news_item, news_event_item.c.news_id == news_item.c.id)
        )
        .where(news_event.c.title.is_(None))
        .order_by(
            news_event.c.id,
            news_item.c.published_at.asc(),
            news_item.c.id.asc(),
        )
        .subquery()
    )

    # 更新 news_event
    stmt = (
        update(news_event)
        .where(news_event.c.id == rep_news_subq.c.event_id)
        .values(
            title=rep_news_subq.c.title,
            summary=rep_news_subq.c.content[:summary_len],
        )
    )

    await session.execute(stmt)
