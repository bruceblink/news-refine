from app.services.analysis_service import build_news_item_from_news_info, compute_tfidf_top


def test_build_news_item_from_news_info_flattens_items():
    news = [
        {
            "id": 1,
            "name": "人民网",
            "news_date": "2026-04-20",
            "data": {
                "items": [
                    {"id": "a", "title": "标题A", "url": "https://example.com/a"},
                    {"id": "b", "title": "标题B", "url": "https://example.com/b"},
                ]
            },
        }
    ]

    result = build_news_item_from_news_info(news)

    assert len(result) == 2
    assert result[0]["news_info_id"] == 1
    assert result[0]["source"] == "人民网"


def test_compute_tfidf_top_empty_returns_empty():
    assert compute_tfidf_top([]) == []
