from fastapi.testclient import TestClient

import main
from app.dao.dto import NewsItemDetailDTO


def test_get_news_detail_success(monkeypatch):
    async def fake_fetch(news_id):
        return NewsItemDetailDTO(
            id=news_id,
            news_info_id=5,
            title="标题",
            url="https://example.com/a",
            published_at="2026-04-20",
            source="src",
            content="正文",
        )

    monkeypatch.setattr("app.routers.news.fetch_news_item_by_id", fake_fetch)

    client = TestClient(main.app)
    resp = client.get("/api/news/1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["item_id"] == "5"


def test_get_news_detail_not_found(monkeypatch):
    async def fake_fetch(_news_id):
        return None

    monkeypatch.setattr("app.routers.news.fetch_news_item_by_id", fake_fetch)

    client = TestClient(main.app)
    resp = client.get("/api/news/404")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "新闻不存在"
