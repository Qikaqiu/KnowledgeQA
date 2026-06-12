import re

# ChromaDB cosine 空间：distance ≈ 1 - 余弦相似度（向量已归一化）
# semantic_score = 1 - distance，范围大致 0~1

_CHINESE_FILLER_CHARS = frozenset("什么如何哪些是否的了在吗呢吧啊呀么个这就请告诉我想知道一下可以")
_QUERY_FILLER_PHRASES = (
    "请问",
    "告诉我",
    "想知道",
    "能不能",
    "是否可以",
    "系统",
    "使用",
    "采用",
)


def semantic_score_from_distance(distance: float) -> float:
    return max(0.0, 1.0 - float(distance))


def _normalize_query(query: str) -> str:
    query = query.strip().lower().rstrip("?？.!！")
    for suffix in (
        "是多久",
        "多长时间",
        "是多少",
        "有多少",
        "是什么",
        "有哪些",
        "怎么样",
        "如何",
        "多少钱",
        "价格多少",
        "定价多少",
        "多少",
    ):
        if query.endswith(suffix) and len(query) > len(suffix):
            return query[: -len(suffix)]
    return query


def _chinese_core(query: str) -> str:
    """去掉口语虚词与常见问句前缀，保留名词性核心。"""
    text = query
    for phrase in _QUERY_FILLER_PHRASES:
        text = text.replace(phrase, "")
    chars = [
        ch
        for ch in text
        if "\u4e00" <= ch <= "\u9fff" and ch not in _CHINESE_FILLER_CHARS
    ]
    return "".join(chars)


def _english_terms(query: str) -> list[str]:
    return re.findall(r"[a-z0-9]{2,}", query.lower())


def _chinese_ngram_score(core: str, text: str) -> float:
    if not core:
        return 0.0
    if core in text:
        return 1.0

    best = 0.0
    for size in range(len(core), 1, -1):
        for start in range(len(core) - size + 1):
            gram = core[start : start + size]
            if gram in text:
                best = max(best, size / len(core))
        if best >= 0.6:
            break
    return best


def _chinese_bigrams(text: str) -> set[str]:
    chars = [ch for ch in text if "\u4e00" <= ch <= "\u9fff"]
    if len(chars) < 2:
        return set(chars)
    return {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}


def _char_coverage(core: str, text: str) -> float:
    if not core:
        return 0.0
    matched = sum(1 for ch in core if ch in text)
    return matched / len(core)


def keyword_overlap_score(query: str, text: str) -> float:
    """中文/英文关键词重合度，弥补纯向量模型对中文问法不敏感的问题。"""
    query = _normalize_query(query)
    text = text.lower()
    if not query or not text:
        return 0.0

    scores: list[float] = []

    core = _chinese_core(query)
    if len(core) >= 2:
        scores.append(_chinese_ngram_score(core, text))
        scores.append(_char_coverage(core, text))

    for run in re.findall(r"[\u4e00-\u9fff]{2,}", query):
        run_core = "".join(ch for ch in run if ch not in _CHINESE_FILLER_CHARS)
        if len(run_core) >= 2:
            scores.append(_chinese_ngram_score(run_core, text))

    english = _english_terms(query)
    if english:
        matched = sum(1 for token in english if token in text)
        scores.append(matched / len(english))

    q_bigrams = _chinese_bigrams(query)
    t_bigrams = _chinese_bigrams(text)
    if q_bigrams and t_bigrams:
        union = q_bigrams | t_bigrams
        scores.append(len(q_bigrams & t_bigrams) / len(union))

    if not scores:
        return 0.0
    return round(max(scores), 4)


def keyword_retrieval_score(query: str, text: str) -> float:
    """关键词专用检索分：用于 EMBEDDING_BACKEND=keyword，不混入向量语义权重。"""
    return keyword_overlap_score(query, text)


def combined_score(semantic: float, keyword: float) -> float:
    """综合分 = 70% 语义 + 30% 关键词，有明显关键词命中时再小幅加成。"""
    base = semantic * 0.7 + keyword * 0.3
    if keyword >= 0.25:
        base += 0.08
    if keyword >= 0.5:
        base += 0.07
    return round(min(1.0, base), 4)


def relevance_label(score: float, min_score: float) -> str:
    if score >= 0.72:
        return "高相关"
    if score >= min_score:
        return "中相关"
    return "低相关"
