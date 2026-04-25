import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from wordfreq_cn import generate_trend_wordcloud, extract_keywords_tfidf_per_doc

from ..config import settings
from ..dao import query_news_events, count_news_events, get_news_event_by_id, list_news_items_by_event, \
    merge_cross_day_events, count_news_items_by_event
from ..db import AsyncSessionLocal
from ..utils import clean_html

logger = logging.getLogger(__name__)

executor = ThreadPoolExecutor(max_workers=1)  # Render 512MB 限制，只保留 1 个线程


# Helper to fetch documents from DB
async def docs_to_corpus(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    from collections import defaultdict

    corpus = defaultdict(list)  # 自动初始化不存在的键
    for r in rows:
        data = r.get("data", {})
        news_date = r.get("news_date", "")

        for item in data.get("items", []):
            title = item.get("title", "") if isinstance(item, dict) else ""
            hover = ""
            if isinstance(item, dict):
                extra = item.get("extra", {})
                hover = extra.get("hover", "") if isinstance(extra, dict) else ""

            text = f"{title} {hover}"
            text = clean_html(text)

            # 直接添加到对应日期的列表中
            corpus[news_date].append(text)
    return corpus


def compute_tfidf_top(
        corpus: list[dict],
        top_n: int = 5,
        max_features: int = None
) -> list[dict]:
    """
    对每条新闻提取 top_n 关键词（per-document TF-IDF）。
    依赖 extract_keywords_tfidf 返回的:
        - vectorizer
        - matrix (n_docs x n_features)
        - feature_names
    """
    if not corpus:
        return []

    # 1. 提取文本（content 为空时使用 title）
    news_ids = [item.get("id", "") for item in corpus]

    texts = [
        item.get("title", "").strip()
        for item in corpus
    ]

    # 避免空文本导致 vectorizer 报错
    texts = [t if t else " " for t in texts]

    # 2. 每篇新闻 top_n 的 TF-IDF
    per_doc_keywords = extract_keywords_tfidf_per_doc(
        corpus=texts,
        top_k=top_n,
        max_features=max_features
    )

    # 3. Flatten → List[NewsKeywordsDTO]
    results = [
        {
            "news_id": news_id,
            "keyword": kw.word,
            "weight": kw.weight,
            "method": "tfidf"
        }
        for news_id, kws in zip(news_ids, per_doc_keywords)
        for kw in kws
    ]

    return results


def generate_wordcloud(
    corpus: dict[str, list[str]], out_path: str, max_words: int | None = 200
) -> list[str]:
    return generate_trend_wordcloud(corpus, output_dir=out_path, max_words=max_words)


def build_news_item_from_news_info(news: list[dict]) -> list[dict]:
    """从嵌套新闻数据中构建扁平化条目信息"""
    result = []

    for news_item in news:
        if not (data := news_item.get("data")):
            continue

        # 提取data中重复使用的字段
        news_info_id = news_item.get("id")
        published_at = news_item.get("news_date", None)
        source = news_item.get("name", "")

        # 遍历items并构建结果
        for item in data.get("items", []):
            result.append({
                "item_id": str(item.get("id", "")),
                "news_info_id": news_info_id,
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "published_at": published_at,
                "source": source,
            })

    return result


# Public coroutine wrappers
import asyncio


async def async_tfidf_top(corpus: list[dict], top_n: int = 5, max_features: int = None):
    loop = asyncio.get_running_loop()  # 应用于CPU密集型
    return await loop.run_in_executor(
        executor, compute_tfidf_top, corpus, top_n, max_features
    )


async def async_generate_wordcloud(
    corpus: dict[str, list[str]], file_dir: str | None = ""
) -> list[str]:
    out_path = os.path.join(settings.WORDCLOUD_DIR, file_dir)
    # 应用于文件I/O
    return await asyncio.to_thread(generate_wordcloud, corpus, out_path)


def embedding_cluster_pipeline(
        texts: list[str | Any],
        n_clusters: int = 50,
        max_features: int = 512,
        random_state: int = 42,
) -> tuple[list[int], str]:
    """
    文本 → embedding → 聚类流水线（标题专用 / 中文友好 / 自适应）

    返回：
    - cluster_ids: 每条文本对应的 cluster_id
    - cluster_method: 本次使用的方法描述（可观测）
    """

    # =========================
    # Step 0. 输入兜底
    # =========================
    if not texts:
        return [], "no_texts"

    # =========================
    # Step 1. 清洗文本
    # =========================
    cleaned_texts: list[str] = []
    invalid_indices: list[int] = []

    for i, text in enumerate(texts):
        try:
            # 处理 None 值
            if text is None:
                cleaned_texts.append("")
                invalid_indices.append(i)
                continue

            # 转换为字符串并清理
            text_str = str(text).strip()

            # 检查是否是浮点数的字符串表示（如 'nan', 'inf'）
            if not text_str or text_str.lower() in {"nan", "inf", "-inf"}:
                cleaned_texts.append("")
                invalid_indices.append(i)
            else:
                cleaned_texts.append(text_str)

        except Exception as e:
            logger.warning(
                f"Failed to process text at index {i}: {type(text)} - {text}. Error: {e}"
            )
            cleaned_texts.append("")
            invalid_indices.append(i)

    # 记录警告信息
    if invalid_indices:
        logger.warning(
            f"Found {len(invalid_indices)} invalid texts, "
            f"example indices: {invalid_indices[:10]}"
        )

    # 全是空文本
    if not any(cleaned_texts):
        return [0] * len(cleaned_texts), "all_texts_invalid"

    # 延迟导入，避免启动时加载 sklearn 占用大量内存
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import MiniBatchKMeans

    # =========================
    # Step 2. 自适应 TF-IDF
    # =========================
    tfidf_configs = [
        # 标准配置（标题常用）
        dict(ngram_range=(2, 3), min_df=2, max_df=0.9),

        # 放宽（短标题 / 少样本）
        dict(ngram_range=(2, 2), min_df=1, max_df=0.95),

        # 更宽（兜底）
        dict(ngram_range=(1, 2), min_df=1, max_df=1.0),

        # 最终兜底（unigram）
        dict(ngram_range=(1, 1), min_df=1, max_df=1.0),
    ]

    X = None
    tfidf_method = None

    for cfg in tfidf_configs:
        try:
            vectorizer = TfidfVectorizer(
                max_features=max_features,
                sublinear_tf=True,
                **cfg,
            )
            X_tmp = vectorizer.fit_transform(cleaned_texts)

            # 至少要有 1 个特征
            if X_tmp.shape[1] > 0:
                X = X_tmp
                tfidf_method = (
                    f"tfidf_ngram{cfg['ngram_range']}"
                    f"_min_df{cfg['min_df']}"
                    f"_max_df{cfg['max_df']}"
                )
                break

        except ValueError as e:
            logger.info(f"TF-IDF config failed {cfg}: {e}")
            continue

    if X is None:
        logger.error("TF-IDF failed for all configs, fallback to single cluster")
        return [0] * len(cleaned_texts), "tfidf_failed_fallback"

    # =========================
    # Step 3. 聚类
    # =========================
    n_samples = X.shape[0]
    actual_n_clusters = min(n_clusters, n_samples)

    if actual_n_clusters < 2:
        return [0] * n_samples, f"{tfidf_method}_single_cluster"

    try:
        kmeans = MiniBatchKMeans(
            n_clusters=actual_n_clusters,
            batch_size=min(64, n_samples),
            random_state=random_state,
            max_iter=100,
        )
        cluster_ids = kmeans.fit_predict(X).tolist()

        cluster_method = (
            f"{tfidf_method}_kmeans_{actual_n_clusters}clusters"
        )

        return cluster_ids, cluster_method

    except Exception as e:
        logger.error("KMeans failed, fallback to single cluster", e, exc_info=True)
        return [0] * n_samples, f"{tfidf_method}_kmeans_failed"


async def list_news_events(
        **params,
):
    async with AsyncSessionLocal() as session:
        async with session.begin():   # ← ★ 事务开始
            items = await query_news_events(session, **params)
            total = await count_news_events(
                session,
                status=params.get("status"),
                start_date=params.get("start_date"),
                end_date=params.get("end_date"),
            )

            return {
                "items": [
                    {
                        **dict(row),
                        "event_date": row["event_date"].isoformat() if row["event_date"] else None,
                    }
                    for row in items
                ],
                "page": params["page"],
                "pageSize": params["page_size"],
                "totalCount": total,
            }


async def get_news_event_detail(
        event_id: int,
        page: int = 1,
        page_size: int = 20,
):
    async with AsyncSessionLocal() as session:
        async with session.begin():   # ← ★ 事务开始
            event = await get_news_event_by_id(session, event_id)
            if event is None:
                return None

            offset = (page - 1) * page_size
            items = await list_news_items_by_event(session, event_id, limit=page_size, offset=offset)
            total = await count_news_items_by_event(session, event_id)

            return {
                "event": {
                    **dict(event),
                    "event_date": event["event_date"].isoformat() if event["event_date"] else None,
                },
                "news_items": [
                    {
                        **dict(item),
                        "published_at": item["published_at"].isoformat() if item["published_at"] else None,
                    }
                    for item in items
                ],
                "page": page,
                "pageSize": page_size,
                "totalCount": total,
            }


async def merge_cross_day_events_task(
        event_date,
        lookback_days: int = 2,
):
    async with AsyncSessionLocal() as session:
        async with session.begin():   # ← ★ 事务开始
            await merge_cross_day_events(session, event_date, lookback_days)