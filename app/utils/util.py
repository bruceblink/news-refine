import re


def clean_html(text: str) -> str:
    if not text:
        return ""
    # remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # remove URLs
    text = re.sub(r"https?://\S+", " ", text)
    # normalize whitespace
    text = re.sub(r"\s+", " ", text)
    # filter / , % - char
    text = re.sub(r"[^\w\u4e00-\u9fff\s]", "", text).strip()
    return text


def simple_tokenize(text: str) -> set[str]:
    if not text:
        return set()
    text = text.lower()
    tokens = re.findall(r"[\u4e00-\u9fa5a-z0-9]{2,}", text)
    return set(tokens)


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def is_same_event(
        e1_title: str,
        e1_summary: str | None,
        e2_title: str,
        e2_summary: str | None,
        threshold: float = 0.4,
) -> bool:
    t1 = simple_tokenize(e1_title + " " + (e1_summary or ""))
    t2 = simple_tokenize(e2_title + " " + (e2_summary or ""))
    return jaccard_similarity(t1, t2) >= threshold
