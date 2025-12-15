from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import news_keywords


async def save_news_keywords(session: AsyncSession, items: list[dict]) -> None:

    if not items:
        return None

    stmt = insert(news_keywords).values(items)

    # ❗ 冲突更新（推荐：更新 weight）
    stmt = stmt.on_conflict_do_update(
        index_elements=["news_id", "keyword", "method"],
        set_={
            "weight": literal_column("excluded.weight"),
            "method": literal_column("excluded.method"),
        }
    )

    await session.execute(stmt)
    return None