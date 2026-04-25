from datetime import date

import pytest

from app.dao.dto import HotEventDTO, TopNewsItemDTO, DayTrendDTO
from app.dao.stats_dao import fetch_hot_events, fetch_top_news_by_event_ids, fetch_trending_keywords


@pytest.mark.anyio
async def test_fetch_hot_events_maps_to_dto(fake_result_cls, fake_session_cls):
    rows = [
        {
            "id": 1,
            "event_date": date(2026, 4, 20),
            "title": "事件A",
            "summary": "摘要",
            "news_count": 2,
            "score": 1.2,
        }
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])

    result = await fetch_hot_events(session)

    assert len(result) == 1
    assert isinstance(result[0], HotEventDTO)
    assert result[0]["event_date"] == date(2026, 4, 20)


@pytest.mark.anyio
async def test_fetch_top_news_by_event_ids_groups_rows(fake_result_cls, fake_session_cls):
    rows = [
        {
            "event_id": 5,
            "id": 10,
            "title": "新闻1",
            "source": "src",
            "published_at": date(2026, 4, 21),
            "url": "https://example.com/1",
            "rn": 1,
        },
        {
            "event_id": 5,
            "id": 11,
            "title": "新闻2",
            "source": "src",
            "published_at": date(2026, 4, 22),
            "url": "https://example.com/2",
            "rn": 2,
        },
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])

    result = await fetch_top_news_by_event_ids(session, [5], top_n=3)

    assert 5 in result
    assert all(isinstance(x, TopNewsItemDTO) for x in result[5])
    assert result[5][0]["published_at"] == "2026-04-21"


@pytest.mark.anyio
async def test_fetch_trending_keywords_builds_day_trend(fake_result_cls, fake_session_cls):
    rows = [
        {"date": date(2026, 4, 22), "keyword": "AI", "weight": 4.2, "count": 3},
        {"date": date(2026, 4, 22), "keyword": "Agent", "weight": 2.1, "count": 2},
        {"date": date(2026, 4, 21), "keyword": "DB", "weight": 1.0, "count": 1},
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])

    result = await fetch_trending_keywords(session, days=7, top_k=10)

    assert len(result) == 2
    assert isinstance(result[0], DayTrendDTO)
    assert result[0]["date"] == "2026-04-22"
    assert result[0]["keywords"][0]["keyword"] == "AI"
