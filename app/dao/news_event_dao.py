from datetime import timedelta

from sqlalchemy import select, desc, asc, update, func, cast, Float, literal
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import news_item, news_event, news_event_item
from app.utils import is_same_event


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
            literal("", type_=news_event.c.title.type).label("title"),
            literal("", type_=news_event.c.summary.type).label("summary"),
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
            ["event_date", "cluster_id", "news_count", "title", "summary"],
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
) -> None:
    """
    为 news_event 回填 title / summary
    规则：选事件中最早发布的新闻
    只处理 title 为空或占位值的事件
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
        .where(
            (news_event.c.title.is_(None))
            | (news_event.c.title == "")
        )
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
            summary=rep_news_subq.c.content,
        )
    )

    await session.execute(stmt)


async def step4_update_event_score(
        session: AsyncSession,
        decay_days: float = 5.0,
        lookback_days: int = 30,
):
    """
    计算并更新 news_event.score

    score = ln(news_count + 1) * exp(-(today - event_date) / decay_days)

    只更新最近 lookback_days 天的事件（更早的事件 score 趋近于 0，无需重算）
    """
    since = func.current_date() - lookback_days

    stmt = (
        update(news_event)
        .where(news_event.c.event_date >= since)
        .values(
            score=
            func.ln(news_event.c.news_count + 1)
            * func.exp(
                -cast(
                    func.current_date() - news_event.c.event_date,
                    Float,
                    ) / decay_days
            ),
            updated_at=func.now(),
        )
    )

    await session.execute(stmt)


async def merge_cross_day_events(
        session: AsyncSession,
        event_date,
        lookback_days: int = 2,
        batch_size: int = 100,
        parent_limit: int = 500,
):
    """
    合并跨天事件（使用 merge_at 控制幂等）
    :param session:
    :param event_date:
    :param lookback_days:
    :return:
    """
    # 1. 获取「历史主事件候选」
    candidate_parents = await get_candidate_parent_events(
        session,
        event_date,
        lookback_days,
        limit=parent_limit,
    )

    if not candidate_parents:
        return

    # 2. 分批获取「当天尚未 merge 的新事件」并逐个尝试 merge
    last_id = 0
    while True:
        new_events = await get_new_events(session, event_date, limit=batch_size, after_id=last_id)

        if not new_events:
            break

        for event in new_events:
            parent = _find_parent_event(event, candidate_parents)

            if not parent:
                continue

            # 2.1 建立 parent-child 关系
            await attach_to_parent(
                session,
                child_event_id=event["id"],
                parent_event_id=parent["id"],
            )

            # 2.2 标记 child 已 merge
            await mark_event_merged(session, event["id"])

        last_id = new_events[-1]["id"]


async def get_new_events(
        session: AsyncSession,
        event_date,
        *,
        limit: int = 100,
        after_id: int = 0,
):
    """
    获取「当天尚未被合并的新事件」
    """
    stmt = (
        select(news_event)
        .where(
            news_event.c.event_date == event_date,
            news_event.c.merge_at.is_(None),
            news_event.c.id > after_id,
            )
        .order_by(asc(news_event.c.id))
        .limit(limit)
    )

    result = await session.execute(stmt)
    return result.mappings().all()


async def get_candidate_parent_events(
        session: AsyncSession,
        current_event_date,
        lookback_days: int = 2,
        *,
        limit: int = 500,
):
    """
    获取历史主事件候选（只允许 root event）
    """
    stmt = (
        select(news_event)
        .where(
            news_event.c.parent_event_id.is_(None),
            news_event.c.event_date >= current_event_date - timedelta(days=lookback_days),
            news_event.c.event_date < current_event_date,
            )
        .order_by(news_event.c.event_date.desc(), news_event.c.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.mappings().all()


def _find_parent_event(
        event,
        candidate_events,
):
    """
    为单个事件寻找 parent
    :param event:
    :param candidate_events:
    :return:
    """
    for parent in candidate_events:
        if is_same_event(
                event["title"],
                event["summary"],
                parent["title"],
                parent["summary"],
        ):
            return parent
    return None


async def attach_to_parent(
        session: AsyncSession,
        child_event_id: int,
        parent_event_id: int,
):
    """
    绑定子事件到父事件
    """
    await session.execute(
        update(news_event)
        .where(news_event.c.id == child_event_id)
        .values(parent_event_id=parent_event_id)
    )


async def mark_event_merged(
        session: AsyncSession,
        event_id: int,
):
    """
     标记事件已经被合并（仅子事件）
    :param session:
    :param event_id:
    :return:
    """
    await session.execute(
        update(news_event)
        .where(news_event.c.id == event_id)
        .values(merge_at=func.now())
    )


async def query_news_events(
        session: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "score",     # score | date
        order_desc: bool = True,
        status: int | None = None,
        start_date=None,
        end_date=None,
):
    offset = (page - 1) * page_size

    stmt = select(
        news_event.c.id,
        news_event.c.event_date,
        news_event.c.title,
        news_event.c.summary,
        news_event.c.news_count,
        news_event.c.score,
        news_event.c.status,
    )

    # 1. 过滤条件
    if status is not None:
        stmt = stmt.where(news_event.c.status == status)

    if start_date is not None:
        stmt = stmt.where(news_event.c.event_date >= start_date)

    if end_date is not None:
        stmt = stmt.where(news_event.c.event_date <= end_date)

    # 2. 排序
    if order_by == "date":
        order_col = news_event.c.event_date
    else:
        order_col = news_event.c.score

    stmt = stmt.order_by(
        desc(order_col) if order_desc else asc(order_col),
        desc(news_event.c.id),
    )

    # 3. 分页
    stmt = stmt.limit(page_size).offset(offset)

    result = await session.execute(stmt)
    return result.mappings().all()


async def count_news_events(
        session: AsyncSession,
        *,
        status: int | None = None,
        start_date=None,
        end_date=None,
):
    stmt = select(func.count()).select_from(news_event)

    if status is not None:
        stmt = stmt.where(news_event.c.status == status)

    if start_date is not None:
        stmt = stmt.where(news_event.c.event_date >= start_date)

    if end_date is not None:
        stmt = stmt.where(news_event.c.event_date <= end_date)

    result = await session.execute(stmt)
    return result.scalar_one()


async def get_news_event_by_id(
        session: AsyncSession,
        event_id: int,
):
    stmt = (
        select(
            news_event.c.id,
            news_event.c.event_date,
            news_event.c.title,
            news_event.c.summary,
            news_event.c.news_count,
            news_event.c.score,
            news_event.c.status,
        )
        .where(news_event.c.id == event_id)
    )

    result = await session.execute(stmt)
    return result.mappings().one_or_none()


async def count_news_items_by_event(
        session: AsyncSession,
        event_id: int,
):
    stmt = (
        select(func.count())
        .select_from(news_event_item)
        .where(news_event_item.c.event_id == event_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def list_news_items_by_event(
        session: AsyncSession,
        event_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
):
    stmt = (
        select(
            news_item.c.id,
            news_item.c.title,
            news_item.c.source,
            news_item.c.published_at,
            news_item.c.url,
        )
        .select_from(
            news_event_item
            .join(news_item, news_event_item.c.news_id == news_item.c.id)
        )
        .where(news_event_item.c.event_id == event_id)
        .order_by(
            asc(news_item.c.published_at),
            asc(news_item.c.id),
        )
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(stmt)
    return result.mappings().all()
