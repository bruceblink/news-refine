from datetime import date

import pytest

from app.dao.dto import NewsEventDTO, NewsEventRecordDTO, NewsItemInEventDTO
from app.dao.news_event_dao import (
    get_candidate_parent_events,
    get_new_events,
    get_news_event_by_id,
    list_news_items_by_event,
    query_news_events,
)


@pytest.mark.anyio
async def test_get_new_events_maps_to_dto(fake_result_cls, fake_session_cls):
    rows = [
        {
            "id": 1,
            "event_date": date(2026, 4, 23),
            "cluster_id": 7,
            "title": "事件1",
            "summary": "摘要",
            "news_count": 3,
            "score": 1.5,
            "status": 0,
            "parent_event_id": None,
        }
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])

    result = await get_new_events(session, date(2026, 4, 23), limit=10, after_id=0)

    assert len(result) == 1
    assert isinstance(result[0], NewsEventRecordDTO)


@pytest.mark.anyio
async def test_get_candidate_parent_events_maps_to_dto(fake_result_cls, fake_session_cls):
    rows = [
        {
            "id": 2,
            "event_date": date(2026, 4, 22),
            "cluster_id": 7,
            "title": "父事件",
            "summary": "摘要",
            "news_count": 4,
            "score": 2.0,
            "status": 0,
            "parent_event_id": None,
            "merge_at": None,
        }
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])

    result = await get_candidate_parent_events(session, date(2026, 4, 23), lookback_days=2, limit=50)

    assert len(result) == 1
    assert isinstance(result[0], NewsEventRecordDTO)


@pytest.mark.anyio
async def test_query_news_events_maps_to_dto(fake_result_cls, fake_session_cls):
    rows = [
        {
            "id": 3,
            "event_date": date(2026, 4, 21),
            "title": "事件3",
            "summary": "摘要",
            "news_count": 5,
            "score": 3.2,
            "status": 0,
        }
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])

    result = await query_news_events(session)

    assert len(result) == 1
    assert isinstance(result[0], NewsEventDTO)


@pytest.mark.anyio
async def test_get_news_event_by_id_none(fake_result_cls, fake_session_cls):
    session = fake_session_cls(results=[fake_result_cls(rows=[])])

    result = await get_news_event_by_id(session, 100)

    assert result is None


@pytest.mark.anyio
async def test_get_news_event_by_id_maps_to_dto(fake_result_cls, fake_session_cls):
    rows = [
        {
            "id": 4,
            "event_date": date(2026, 4, 20),
            "title": "事件4",
            "summary": "摘要",
            "news_count": 2,
            "score": 1.1,
            "status": 0,
        }
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])

    result = await get_news_event_by_id(session, 4)

    assert isinstance(result, NewsEventDTO)
    assert result["id"] == 4


@pytest.mark.anyio
async def test_list_news_items_by_event_maps_to_dto(fake_result_cls, fake_session_cls):
    rows = [
        {
            "id": 20,
            "title": "新闻X",
            "source": "src",
            "published_at": date(2026, 4, 20),
            "url": "https://example.com/x",
        }
    ]
    session = fake_session_cls(results=[fake_result_cls(rows=rows)])

    result = await list_news_items_by_event(session, 4)

    assert len(result) == 1
    assert isinstance(result[0], NewsItemInEventDTO)
