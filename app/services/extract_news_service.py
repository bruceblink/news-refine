from app.dao import save_news_keywords, update_news_item_extracted_state, save_news_items, step1_insert_news_event, \
    step2_insert_news_event_item, update_news_info_extracted_state, step3_fill_event_title_and_summary
from app.db import AsyncSessionLocal


async def extract_keywords_task(items: list[dict]):
    """
     提取新闻关键字
    :param items:
    :return:
    """

    async with AsyncSessionLocal() as session:
        async with session.begin():   # ← ★ 事务开始
            await save_news_keywords(session, items)
            await update_news_item_extracted_state(session, items)

        # async with session.begin() 会自动 commit 或 rollback


async def extract_news_items_task(items: list[dict]):
    """
     提取新闻items
    :param items:
    :return:
    """

    async with AsyncSessionLocal() as session:
        async with session.begin():   # ← ★ 事务开始
            await save_news_items(session, items)
            await update_news_info_extracted_state(session, items)


async def extract_news_event_task() -> None:
    """
    构建新闻事件的离线 task
    幂等、可重复执行
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():   # ← ★ 事务开始
            await step1_insert_news_event(session)
            await step2_insert_news_event_item(session)
            await step3_fill_event_title_and_summary(session)
