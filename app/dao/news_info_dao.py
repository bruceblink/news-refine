from datetime import date

from sqlalchemy import select, and_, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.models import news_info


async def fetch_news_info_rows(
        start_date: date | None,
        end_date: date | None,
        limit: int | None = 1000
) -> list[dict]:
    """
     查询news_info
    :param start_date:
    :param end_date:
    :param limit:
    :return:
    """
    async with AsyncSessionLocal() as session:

        stmt = (
            select(
                news_info.c.id,
                news_info.c.name,
                news_info.c.news_from,
                news_info.c.news_date,
                news_info.c.data,
                news_info.c.extracted,
                news_info.c.error,
            )
        )

        conditions = [news_info.c.extracted == False]  # ⭐ 新闻未提取

        if start_date:
            conditions.append(news_info.c.news_date >= start_date)
        if end_date:
            conditions.append(news_info.c.news_date <= end_date)

        stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(news_info.c.created_at.desc()).limit(limit)

        result = await session.execute(stmt)
        rows = result.mappings().all()

        return [
            {
                "id": r["id"],
                "name": r["name"],
                "news_from": r["news_from"],
                "news_date": r["news_date"],
                "data": r["data"],
                "extracted": r["extracted"],
                "error": r["error"],
            }
            for r in rows
        ]


async def update_news_info_extracted_state(session: AsyncSession, items: list[dict]) -> None:
    """
    更新已提取的新闻info的状态
    :param session:
    :param items:
    :return:
    """
    if not items:
        return
    # 使用字典去重
    news_ids = { item.get("news_info_id", "") for item in items }

    if not news_ids:
        return

    stmt = (
        update(news_info)
        .where(news_info.c.id.in_(news_ids))
        .values(
            extracted=True,
            extracted_at=func.current_timestamp()
        )
    )
    await session.execute(stmt)


async def fetch_news_info_by_id(news_info_id: str) -> list[dict]:
    """
     根据新闻id查询新闻详情
    :param news_info_id:
    :return:
    """
    async with AsyncSessionLocal() as session:

        stmt = (
            select(
                news_info.c.id,
                news_info.c.name,
                news_info.c.news_from,
                news_info.c.news_date,
                news_info.c.data,
                news_info.c.extracted,
                news_info.c.error,
            )
        )

        conditions = [news_info.c.id == news_info_id]

        stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(news_info.c.created_at.desc()).limit(1)

        result = await session.execute(stmt)
        rows = result.mappings().all()

        return [
            {
                "id": r["id"],
                "name": r["name"],
                "news_from": r["news_from"],
                "news_date": r["news_date"].isoformat() if r["news_date"] else None,
                "data": r["data"],
                "extracted": r["extracted"],
                "error": r["error"],
            }
            for r in rows
        ]
