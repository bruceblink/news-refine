from fastapi.testclient import TestClient

import main


def test_search_news_empty_segment(monkeypatch):
    monkeypatch.setattr("app.routers.search.wordfreq_cn.segment_text", lambda _q: [])

    client = TestClient(main.app)
    resp = client.get("/api/search/news", params={"q": "   ", "page": 1, "pageSize": 20})

    assert resp.status_code == 200
    assert resp.json() == {"total": 0, "page": 1, "pageSize": 20, "items": []}


def test_search_news_success(monkeypatch):
    monkeypatch.setattr("app.routers.search.wordfreq_cn.segment_text", lambda _q: ["AI"])

    async def fake_count(_keywords):
        return 2

    async def fake_fetch(_keywords, _limit, _offset):
        return [
            {
                "id": 1,
                "title": "A",
                "url": "https://example.com/a",
                "source": "src",
                "published_at": "2026-04-20",
                "score": 1.0,
            }
        ]

    monkeypatch.setattr("app.routers.search.count_news_by_keywords", fake_count)
    monkeypatch.setattr("app.routers.search.fetch_news_item_by_keywords", fake_fetch)

    client = TestClient(main.app)
    resp = client.get("/api/search/news", params={"q": "AI", "page": 1, "pageSize": 20})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1
