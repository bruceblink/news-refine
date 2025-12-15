import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from wordfreq_cn import generate_trend_wordcloud, extract_keywords_tfidf_per_doc

from ..config import settings
from ..dao import query_news_events, count_news_events
from ..db import AsyncSessionLocal
from ..utils.cleaner import clean_html

logger = logging.getLogger(__name__)

executor = ThreadPoolExecutor(max_workers=2)


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


def build_news_item_from_news_info1(news: list[dict]) -> list[dict]:
    """
     列表生成式优化
    :param news:
    :return:
    """
    return [
        {
            "item_id": item.get("id", ""),
            "news_info_id": data.get("id", 0),
            "title": item.get("title", ""),
            "url": data.get("url", ""),
            "published_at": data.get("news_date", ""),
            "source": data.get("name", ""),
        }
        for news_item in news if (data := news_item.get("data"))
        for item in data.get("items", [])
    ]


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


from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans


def embedding_cluster_pipeline(
        texts: list[str | Any],  # 放宽类型提示，允许任何类型
        n_clusters: int = 50,
        max_features: int = 512,
        random_state: int = 42,
) -> tuple[list[int], str]:
    """
    文本 → 聚类流水线

    返回：
    - cluster_ids: 每条文本对应的 cluster_id
    - cluster_method: 本次使用的聚类方法描述
    """

    if not texts:
        return [], "no_texts"

    # 1. 数据清洗和验证
    cleaned_texts = []
    invalid_indices = []  # 记录无效文本的索引

    for i, text in enumerate(texts):
        try:
            # 处理 None 值
            if text is None:
                cleaned_texts.append('')
                invalid_indices.append(i)
                continue

            # 转换为字符串并清理
            text_str = str(text).strip()

            # 检查是否是浮点数的字符串表示（如 'nan', 'inf'）
            if text_str.lower() in ['nan', 'inf', '-inf'] or text_str == '':
                cleaned_texts.append('')
                invalid_indices.append(i)
            else:
                cleaned_texts.append(text_str)

        except Exception as e:
            logger.warning(f"Failed to process text at index {i}: {type(text)} - {text}. Error: {e}")
            cleaned_texts.append('')
            invalid_indices.append(i)

    # 记录警告信息
    if invalid_indices:
        logger.warning(f"Found {len(invalid_indices)} invalid/non-string texts at indices: {invalid_indices[:10]}...")

    # 2. 如果所有文本都无效，返回空结果
    if not any(cleaned_texts):  # 所有文本都是空字符串
        return [], "all_texts_invalid"

    # 3. TF-IDF embedding
    try:
        vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=(2, 3),
            min_df=2,
            max_df=0.9,
            sublinear_tf=True,
        )
        X = vectorizer.fit_transform(cleaned_texts)

        # 4. MiniBatchKMeans 聚类
        # 确保聚类数不超过样本数
        n_samples = X.shape[0]
        actual_n_clusters = min(n_clusters, n_samples)

        if actual_n_clusters < 2:
            logger.warning(f"Not enough samples for clustering. Samples: {n_samples}, Requested clusters: {n_clusters}")
            # 返回所有样本为同一簇或空簇
            if n_samples > 0:
                cluster_ids = [0] * n_samples
                return cluster_ids, "single_cluster_due_to_insufficient_samples"
            else:
                return [], "no_samples"

        kmeans = MiniBatchKMeans(
            n_clusters=actual_n_clusters,
            batch_size=min(64, n_samples),
            random_state=random_state,
            max_iter=100,
        )
        cluster_ids = kmeans.fit_predict(X).tolist()

        # 5. 方法标识
        cluster_method = f"tfidf-{max_features}-kmeans-{actual_n_clusters}clusters"

        return cluster_ids, cluster_method

    except Exception as e:
        logger.error(f"Error in embedding_cluster_pipeline: {e}", exc_info=True)
        # 返回默认值而不是抛出异常，避免整个API崩溃
        if cleaned_texts:
            return [0] * len(cleaned_texts), f"error_fallback_{type(e).__name__}"
        else:
            return [], f"error_{type(e).__name__}"


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
                "items": items,
                "page": params["page"],
                "page_size": params["page_size"],
                "total": total,
            }
