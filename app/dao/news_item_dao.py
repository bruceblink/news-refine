# helper to query news rows (simple)
from datetime import date

from sqlalchemy import select, and_, update, func, or_, literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.dto import NewsItemDTO, NewsItemExtractDTO, NewsItemDetailDTO
from app.db import AsyncSessionLocal
from app.models import news_item, news_keywords


async def fetch_news_item_by_keywords(
        keywords: list[str],
        limit: int = 20,
        offset: int = 0,
) -> list[NewsItemDTO]:
    """
     通过关键字查询所有新闻
    :param keywords: 关键字查询条件
    :param limit:
    :param offset:
    :return:
    """

    # --- 1) 处理关键词，去空格，忽略空字符串 ---
    keywords = [k.strip() for k in keywords if k.strip()]
    if not keywords:
        return []

    async with AsyncSessionLocal() as session:

        conditions = [news_keywords.c.keyword.ilike(f"%{k}%") for k in keywords]

        score_subq = (
            select(
                news_keywords.c.news_id.label("news_id"),
                func.coalesce(func.sum(news_keywords.c.weight), 0).label("score"),
            )
            .where(or_(*conditions))
            .group_by(news_keywords.c.news_id)
            .order_by(func.coalesce(func.sum(news_keywords.c.weight), 0).desc())
            .limit(limit)
            .offset(offset)
            .subquery()
        )

        stmt = (
            select(
                news_item.c.id,
                news_item.c.title,
                news_item.c.url,
                news_item.c.source,
                news_item.c.published_at,
                score_subq.c.score,
            )
            .select_from(score_subq.join(news_item, score_subq.c.news_id == news_item.c.id))
            .order_by(score_subq.c.score.desc(), news_item.c.id.asc())
        )

        rows = (await session.execute(stmt)).mappings().all()

        return [NewsItemDTO.model_validate(r) for r in rows]


async def fetch_news_item_rows_not_extracted(
        start_date: date | None,
        end_date: date | None,
        limit: int | None = 1000
) -> list[NewsItemExtractDTO]:
    """
     查询待提取关键字的新闻item
    :param start_date:
    :param end_date:
    :param limit:
    :return:
    """
    async with AsyncSessionLocal() as session:

        stmt = (
            select(
                news_item.c.id,
                news_item.c.news_info_id,
                news_item.c.title,
                news_item.c.url,
                news_item.c.published_at,
                news_item.c.source,
                news_item.c.content,
            )
        )

        conditions = [news_item.c.extracted == False]  # ⭐ 关键字未提取

        if start_date:
            conditions.append(news_item.c.published_at >= start_date)
        if end_date:
            conditions.append(news_item.c.published_at <= end_date)

        stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(news_item.c.created_at.desc()).limit(limit)

        result = await session.execute(stmt)
        rows = result.mappings().all()

        return [NewsItemExtractDTO.model_validate(r) for r in rows]


async def update_news_item_extracted_state(session: AsyncSession, items: list[dict]) -> None:
    """
    更新已提取的新闻item的状态
    :param session:
    :param items:
    :return:
    """
    if not items:
        return
    # 使用字典去重
    news_ids = { item.get("news_id", "") for item in items }

    if not news_ids:
        return

    stmt = (
        update(news_item)
        .where(news_item.c.id.in_(news_ids))
        .values(
            extracted=True,
            extracted_at=func.current_timestamp()
        )
    )
    await session.execute(stmt)


async def fetch_news_item_by_id(news_id: int) -> NewsItemDetailDTO | None:
    """
     根据新闻id查询新闻详情
    :param news_id:
    :return:
    """
    async with AsyncSessionLocal() as session:

        stmt = (
            select(
                news_item.c.id,
                news_item.c.news_info_id,
                news_item.c.title,
                news_item.c.url,
                news_item.c.published_at,
                news_item.c.source,
                news_item.c.content,
            )
            .where(news_item.c.id == news_id)
            .limit(1)
        )

        result = await session.execute(stmt)
        row = result.mappings().first()

        if row is None:
            return None

        return NewsItemDetailDTO.model_validate(row)


async def count_news_by_keywords(keywords: list[str]) -> int:
    """
    统计匹配关键词的新闻总数（用于分页）
    """
    keywords = [k.strip() for k in keywords if k.strip()]
    if not keywords:
        return 0
    async with AsyncSessionLocal() as session:
        conditions = [news_keywords.c.keyword.ilike(f"%{k}%") for k in keywords]
        stmt = select(func.count(func.distinct(news_keywords.c.news_id))).where(or_(*conditions))
        result = await session.execute(stmt)
        return result.scalar_one()


async def save_news_items(session: AsyncSession, items: list[dict]) -> None:
    if not items:
        return None

    # 1. 对 items 进行去重，保留每个 (item_id, published_at) 的最后一条记录
    seen = {}
    for item in items:
        # 构建唯一键，这里假设 published_at 已处理为日期字符串或 None
        key = (item.get("item_id"), item.get("published_at"))
        seen[key] = item  # 后续出现的记录会覆盖先前的，保留最后一条

    unique_items = list(seen.values())

    # 2. 使用去重后的列表进行插入或更新
    stmt = insert(news_item).values(unique_items)
    stmt = stmt.on_conflict_do_update(
        index_elements=["item_id", "published_at"],
        set_={
            "title": literal_column("excluded.title"),
            "url": literal_column("excluded.url"),
            "source": literal_column("excluded.source"),
            "cluster_method": literal_column("excluded.cluster_method"),
            "cluster_id": literal_column("excluded.cluster_id"),
        }
    )
    await session.execute(stmt)
    return None