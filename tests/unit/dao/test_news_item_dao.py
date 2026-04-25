from datetime import date

import pytest

from app.dao.dto import NewsItemDTO, NewsItemDetailDTO, NewsItemExtractDTO
from app.dao.news_item_dao import (
    count_news_by_keywords,
    fetch_news_item_by_id,
    fetch_news_item_by_keywords,
    fetch_news_item_rows_not_extracted,
    update_news_item_extracted_state,
)


@pytest.mark.anyio
async def test_fetch_news_item_by_keywords_empty_keywords():
    result = await fetch_news_item_by_keywords(["", "  "], limit=10, offset=0)
    assert result == []


@pytest.mark.anyio
async def test_fetch_news_item_by_keywords_maps_to_dto(monkeypatch, fake_result_cls, fake_session_cls, fake_session_factory_cls):
    rows = [
        {
            "id": 3,
            "title": "新闻A",
            "url": "https://example.com/a",
            "source": "src",
            "published_at": date(2026, 4, 20),
            "score": 2.5,
        }
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])
    monkeypatch.setattr(
        "app.dao.news_item_dao.AsyncSessionLocal",
        lambda: fake_session_factory_cls(session),
    )

    result = await fetch_news_item_by_keywords(["A"], limit=20, offset=0)

    assert len(result) == 1
    assert isinstance(result[0], NewsItemDTO)
    assert result[0]["published_at"] == "2026-04-20"


@pytest.mark.anyio
async def test_fetch_news_item_rows_not_extracted_maps_to_dto(monkeypatch, fake_result_cls, fake_session_cls, fake_session_factory_cls):
    rows = [
        {
            "id": 7,
            "news_info_id": 99,
            "title": "新闻B",
            "url": "https://example.com/b",
            "published_at": date(2026, 4, 22),
            "source": "src",
            "content": "content",
        }
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])
    monkeypatch.setattr(
        "app.dao.news_item_dao.AsyncSessionLocal",
        lambda: fake_session_factory_cls(session),
    )

    result = await fetch_news_item_rows_not_extracted(None, None, limit=5)

    assert len(result) == 1
    assert isinstance(result[0], NewsItemExtractDTO)
    assert result[0]["published_at"] == "2026-04-22"


@pytest.mark.anyio
async def test_fetch_news_item_by_id_not_found(monkeypatch, fake_result_cls, fake_session_cls, fake_session_factory_cls):
    session = fake_session_cls(results=[fake_result_cls(rows=[])])
    monkeypatch.setattr(
        "app.dao.news_item_dao.AsyncSessionLocal",
        lambda: fake_session_factory_cls(session),
    )

    result = await fetch_news_item_by_id(100)

    assert result is None


@pytest.mark.anyio
async def test_fetch_news_item_by_id_maps_to_dto(monkeypatch, fake_result_cls, fake_session_cls, fake_session_factory_cls):
    rows = [
        {
            "id": 11,
            "news_info_id": 10,
            "title": "新闻C",
            "url": "https://example.com/c",
            "published_at": date(2026, 4, 23),
            "source": "src",
            "content": "正文",
        }
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])
    monkeypatch.setattr(
        "app.dao.news_item_dao.AsyncSessionLocal",
        lambda: fake_session_factory_cls(session),
    )

    result = await fetch_news_item_by_id(11)

    assert isinstance(result, NewsItemDetailDTO)
    assert result["published_at"] == "2026-04-23"


@pytest.mark.anyio
async def test_count_news_by_keywords_empty_keywords():
    result = await count_news_by_keywords(["", " "])
    assert result == 0


@pytest.mark.anyio
async def test_count_news_by_keywords_returns_scalar(monkeypatch, fake_result_cls, fake_session_cls, fake_session_factory_cls):
    session = fake_session_cls(results=[fake_result_cls(scalar=8)])
    monkeypatch.setattr(
        "app.dao.news_item_dao.AsyncSessionLocal",
        lambda: fake_session_factory_cls(session),
    )

    result = await count_news_by_keywords(["AI"])

    assert result == 8


@pytest.mark.anyio
async def test_update_news_item_extracted_state_empty_items(fake_session_cls):
    session = fake_session_cls()
    await update_news_item_extracted_state(session, [])
    assert len(session.execute_calls) == 0
