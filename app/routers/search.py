import wordfreq_cn
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.dao import fetch_news_item_by_keywords

router = APIRouter(prefix="/api/search")


class SearchNewsItem(BaseModel):
    id: int
    title: str | None
    url: str | None
    source: str | None
    published_at: str | None
    score: float


class SearchResponse(BaseModel):
    total: int
    page: int
    pageSize: int
    items: list[SearchNewsItem]


@router.get("/news", response_model=SearchResponse)
async def search_news(
        q: str = Query(..., description="搜索关键词"),
        page: int = Query(1, ge=1, description="页码"),
        pageSize: int = Query(20, ge=1, le=100, description="每页条数"),
):
    keywords = wordfreq_cn.segment_text(q)

    if not keywords:
        return SearchResponse(total=0, page=page, pageSize=pageSize, items=[])

    offset = (page - 1) * pageSize
    items = await fetch_news_item_by_keywords(keywords, pageSize, offset)

    return SearchResponse(total=len(items), page=page, pageSize=pageSize, items=items)
