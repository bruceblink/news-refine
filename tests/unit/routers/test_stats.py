from datetime import date

from fastapi.testclient import TestClient

import main
from app.dao.dto import DayTrendDTO, DayTrendKeywordDTO, HotEventDTO, TopNewsItemDTO


def test_stats_hot(monkeypatch):
    async def fake_fetch_hot_events(_session, **_kwargs):
        return [
            HotEventDTO(
                id=1,
                event_date=date(2026, 4, 20),
                title="事件",
                summary="摘要",
                news_count=2,
                score=1.2,
            )
        ]

    async def fake_count_hot_events(_session, **_kwargs):
        return 1

    async def fake_fetch_top_news(_session, _event_ids, top_n=3):
        return {
            1: [
                TopNewsItemDTO(
                    id=10,
                    title="新闻",
                    source="src",
                    published_at="2026-04-20",
                    url="https://example.com/a",
                )
            ]
        }

    monkeypatch.setattr("app.routers.stats.fetch_hot_events", fake_fetch_hot_events)
    monkeypatch.setattr("app.routers.stats.count_hot_events", fake_count_hot_events)
    monkeypatch.setattr("app.routers.stats.fetch_top_news_by_event_ids", fake_fetch_top_news)

    client = TestClient(main.app)
    resp = client.get("/api/stats/hot")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["event_date"] == "2026-04-20"


def test_stats_trend(monkeypatch):
    async def fake_fetch_trend(_session, days=7, top_k=10):
        return [
            DayTrendDTO(
                date="2026-04-20",
                keywords=[DayTrendKeywordDTO(keyword="AI", weight=1.0, count=2)],
            )
        ]

    monkeypatch.setattr("app.routers.stats.fetch_trending_keywords", fake_fetch_trend)

    client = TestClient(main.app)
    resp = client.get("/api/stats/trend", params={"days": 7, "top_k": 10})

    assert resp.status_code == 200
    body = resp.json()
    assert body["days"] == 7
    assert body["trends"][0]["keywords"][0]["keyword"] == "AI"
