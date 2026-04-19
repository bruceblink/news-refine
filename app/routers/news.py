from collections import defaultdict

from fastapi import APIRouter, Path, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_

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
        limit: int = Query(5, description="返回相关推荐数量")
):
    async with AsyncSessionLocal() as session:
        # 1) 获取目标新闻关键词及权重

        stmt = (select(news_keywords.c.keyword, news_keywords.c.weight))
        conditions = [news_keywords.c.news_id == news_id]
        stmt = stmt.where(and_(*conditions))

        target_result = await session.execute(stmt)

        target_keywords = {r.keyword: r.weight for r in target_result.all()}
        if not target_keywords:
            raise HTTPException(status_code=404, detail="目标新闻关键词不存在")

        # 2) 查询含相同关键词的其他新闻（在 DB 侧过滤，效率更高）
        target_kw_list = list(target_keywords.keys())
        stmt = select(
            news_keywords.c.news_id,
            news_keywords.c.keyword,
            news_keywords.c.weight
        ).where(
            news_keywords.c.keyword.in_(target_kw_list),
            news_keywords.c.news_id != news_id,
        )
        rows = (await session.execute(stmt)).all()

        if not rows:
            return {"total": 0, "items": []}

        # 3) 在 Python 中计算重叠权重相似度（取两者最小权重之和）
        score_map = defaultdict(float)
        for r in rows:
            score_map[r.news_id] += min(target_keywords[r.keyword], r.weight)

        if not score_map:
            return {"total": 0, "items": []}

        # 4) 取相似度最高的 top N
        top_news_ids = sorted(score_map.items(), key=lambda x: x[1], reverse=True)[:limit]
        related_ids = [nid for nid, _ in top_news_ids]
        score_map = dict(top_news_ids)

        # 5) 回表查询新闻详情
        news_rows = (await session.execute(
            select(
                news_item.c.id,
                news_item.c.title,
                news_item.c.url,
                news_item.c.source,
                news_item.c.published_at
            ).where(news_item.c.id.in_(related_ids))
        )).all()

        # 6) 组合结果
        items = []
        for r in news_rows:
            items.append(RelatedNewsItem(
                id=r.id,
                title=r.title,
                url=r.url,
                source=r.source,
                published_at=r.published_at.isoformat() if r.published_at else None,
                score=score_map.get(r.id, 0)
            ))

        # 保证按 score 排序
        items.sort(key=lambda x: x.score, reverse=True)

        return {"total": len(items), "items": items}


