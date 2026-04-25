from fastapi import APIRouter, Path, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func

from app.dao.news_item_dao import fetch_news_item_by_id
from app.db import AsyncSessionLocal
from app.models import news_keywords, news_item

router = APIRouter(prefix="/api/news")


class NewsDetailResponse(BaseModel):
    id: int
    item_id: str | None
    title: str | None
    url: str | None
    source: str | None
    published_at: str | None
    content: str | None


@router.get("/{news_id}", response_model=NewsDetailResponse)
async def get_news_detail(news_id: str):
    item = await fetch_news_item_by_id(news_id)
    if item is None:
        raise HTTPException(status_code=404, detail="新闻不存在")
    return item


class RelatedNewsItem(BaseModel):
    id: str
    title: str
    url: str
    source: str
    published_at: str | None
    score: float


class RelatedNewsResponse(BaseModel):
    total: int
    items: list[RelatedNewsItem]


@router.get("/{news_id}/related", response_model=RelatedNewsResponse)
async def get_related_news(
        news_id: str = Path(..., description="目标新闻 ID"),
        limit: int = Query(5, ge=1, le=50, description="返回相关推荐数量")
):
    async with AsyncSessionLocal() as session:
        target_subq = (
            select(
                news_keywords.c.keyword.label("keyword"),
                news_keywords.c.weight.label("target_weight"),
            )
            .where(news_keywords.c.news_id == news_id)
            .subquery()
        )

        target_exists = await session.execute(select(func.count()).select_from(target_subq))
        if target_exists.scalar_one() == 0:
            raise HTTPException(status_code=404, detail="目标新闻关键词不存在")

        score_subq = (
            select(
                news_keywords.c.news_id.label("news_id"),
                func.sum(
                    func.least(
                        target_subq.c.target_weight,
                        news_keywords.c.weight,
                    )
                ).label("score"),
            )
            .select_from(
                news_keywords.join(
                    target_subq,
                    news_keywords.c.keyword == target_subq.c.keyword,
                )
            )
            .where(news_keywords.c.news_id != news_id)
            .group_by(news_keywords.c.news_id)
            .order_by(func.sum(func.least(target_subq.c.target_weight, news_keywords.c.weight)).desc())
            .limit(limit)
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

        rows = (await session.execute(stmt)).all()

        items = [
            RelatedNewsItem(
                id=r.id,
                title=r.title,
                url=r.url,
                source=r.source,
                published_at=r.published_at.isoformat() if r.published_at else None,
                score=float(r.score or 0),
            )
            for r in rows
        ]

        return {"total": len(items), "items": items}

