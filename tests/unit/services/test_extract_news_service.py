import pytest

from app.services.extract_news_service import extract_news_items_task


@pytest.mark.anyio
async def test_extract_news_items_task_calls_save_and_update(monkeypatch, fake_session_cls, fake_session_factory_cls):
    session = fake_session_cls()
    monkeypatch.setattr(
        "app.services.extract_news_service.AsyncSessionLocal",
        lambda: fake_session_factory_cls(session),
    )

    calls = []

    async def fake_save(_session, items):
        calls.append(("save", len(items)))

    async def fake_update(_session, items):
        calls.append(("update", len(items)))

    monkeypatch.setattr("app.services.extract_news_service.save_news_items", fake_save)
    monkeypatch.setattr("app.services.extract_news_service.update_news_info_extracted_state", fake_update)

    payload = [{"news_info_id": 1, "item_id": "a"}]
    await extract_news_items_task(payload)

    assert calls == [("save", 1), ("update", 1)]
