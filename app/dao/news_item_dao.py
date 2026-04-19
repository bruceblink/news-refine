# helper to query news rows (simple)
from datetime import date

from sqlalchemy import select, and_, update, func, or_, literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.models import news_item, news_keywords


async def fetch_news_item_by_keywords(
        keywords: list[str],
        limit: int = 20,
        offset: int = 0,
) -> list[dict]:
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

        # --- 2) 聚合 TF-IDF 权重排名 ---
        conditions = [news_keywords.c.keyword.ilike(f"%{k}%") for k in keywords]

        stmt = (
            select(
                news_keywords.c.news_id,
                func.coalesce(func.sum(news_keywords.c.weight), 0).label("score")
            )
            .where(or_(*conditions))
            .group_by(news_keywords.c.news_id)
            .order_by(func.coalesce(func.sum(news_keywords.c.weight), 0).desc())
            .limit(limit)
            .offset(offset)
        )

        rows = (await session.execute(stmt)).all()
        if not rows:
            return []

        # --- 3) 获取匹配新闻 ID 和对应分数 ---
        news_ids = [r.news_id for r in rows]
        score_map = {r.news_id: r.score for r in rows}

        # --- 4) 回表查新闻详情 ---
        news_stmt = (
            select(
                news_item.c.id,
                news_item.c.title,
                news_item.c.url,
                news_item.c.source,
                news_item.c.published_at,
            )
            .where(news_item.c.id.in_(news_ids))
        )

        news_rows = (await session.execute(news_stmt)).all()

        # --- 5) 组合结果，按 score 排序 ---
        items = []
        for r in news_rows:
            items.append(
                {
                    "id": r.id,
                    "title": r.title,
                    "url": r.url,
                    "source": r.source,
                    "published_at": r.published_at.isoformat() if r.published_at else None,
                    "score": score_map.get(r.id, 0),
                }
            )

        # 保证排序和前面聚合结果一致
        items.sort(key=lambda x: x["score"], reverse=True)

        return items


async def fetch_news_item_rows_not_extracted(
        start_date: date | None,
        end_date: date | None,
        limit: int | None = 1000
) -> list[dict]:
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

        return [
            {
                "id": r["id"],
                "title": r["title"],
                "url": r["url"],
                "published_at": r["published_at"].isoformat() if r["published_at"] else None,
                "source": r["source"],
                "content": r["content"],
            }
            for r in rows
        ]


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


async def fetch_news_item_by_id(news_id: str) -> dict | None:
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

        return {
            "id": row["id"],
            "news_info_id": row["news_info_id"],
            "title": row["title"],
            "url": row["url"],
            "published_at": row["published_at"].isoformat() if row["published_at"] else None,
            "source": row["source"],
            "content": row["content"],
        }


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