from datetime import date

import pytest

from app.dao.dto import NewsInfoDetailDTO, NewsInfoRowDTO
from app.dao.news_info_dao import fetch_news_info_by_id, fetch_news_info_rows


@pytest.mark.anyio
async def test_fetch_news_info_rows_maps_to_dto(monkeypatch, fake_result_cls, fake_session_cls, fake_session_factory_cls):
    rows = [
        {
            "id": 1,
            "name": "人民网",
            "news_from": "rmrb",
            "news_date": date(2026, 4, 20),
            "data": {"items": []},
            "extracted": False,
            "error": None,
        }
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])
    monkeypatch.setattr(
        "app.dao.news_info_dao.AsyncSessionLocal",
        lambda: fake_session_factory_cls(session),
    )

    result = await fetch_news_info_rows(None, None, limit=10)

    assert len(result) == 1
    assert isinstance(result[0], NewsInfoRowDTO)
    assert result[0]["news_date"] == date(2026, 4, 20)


@pytest.mark.anyio
async def test_fetch_news_info_by_id_maps_date_to_iso(monkeypatch, fake_result_cls, fake_session_cls, fake_session_factory_cls):
    rows = [
        {
            "id": 9,
            "name": "测试源",
            "news_from": "demo",
            "news_date": date(2026, 4, 21),
            "data": {"items": [{"title": "a"}]},
            "extracted": True,
            "error": None,
        }
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])
    monkeypatch.setattr(
        "app.dao.news_info_dao.AsyncSessionLocal",
        lambda: fake_session_factory_cls(session),
    )

    result = await fetch_news_info_by_id("9")

    assert len(result) == 1
    assert isinstance(result[0], NewsInfoDetailDTO)
    assert result[0]["news_date"] == "2026-04-21"
