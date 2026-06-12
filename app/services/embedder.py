import threading
from functools import lru_cache

import numpy as np

from app.config import (
    EMBEDDING_BACKEND,
    EMBEDDING_MODEL,
    EMBEDDING_QUERY_INSTRUCTION,
    KEYWORD_EMBED_DIM,
)

_embed_lock = threading.Lock()


def is_keyword_backend() -> bool:
    return EMBEDDING_BACKEND == "keyword"


def backend_label() -> str:
    if EMBEDDING_BACKEND == "keyword":
        return "关键词检索（轻量）"
    if EMBEDDING_BACKEND == "flag":
        return f"FlagEmbedding · {EMBEDDING_MODEL}"
    return f"FastEmbed · {EMBEDDING_MODEL}"


@lru_cache(maxsize=1)
def _get_fastembed_model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def _get_flag_model():
    import torch
    from FlagEmbedding import FlagModel

    return FlagModel(
        EMBEDDING_MODEL,
        query_instruction_for_retrieval=EMBEDDING_QUERY_INSTRUCTION,
        use_fp16=torch.cuda.is_available(),
    )


def clear_embedder_cache() -> None:
    _get_fastembed_model.cache_clear()
    _get_flag_model.cache_clear()


def _to_vectors(vectors) -> list[list[float]]:
    if isinstance(vectors, np.ndarray):
        if vectors.ndim == 1:
            return [vectors.tolist()]
        return [row.tolist() for row in vectors]
    return [vector.tolist() for vector in vectors]


def _dummy_vectors(count: int) -> list[list[float]]:
    unit = [1.0] + [0.0] * (KEYWORD_EMBED_DIM - 1)
    return [unit[:] for _ in range(count)]


def _encode_fastembed(texts: list[str]) -> list[list[float]]:
    model = _get_fastembed_model()
    return [vector.tolist() for vector in model.embed(texts)]


def _encode_flag(texts: list[str], *, query: bool) -> list[list[float]]:
    model = _get_flag_model()
    if query:
        vectors = model.encode_queries(texts)
    else:
        vectors = model.encode_corpus(texts, batch_size=16)
    return _to_vectors(vectors)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    with _embed_lock:
        if EMBEDDING_BACKEND == "keyword":
            return _dummy_vectors(len(texts))
        if EMBEDDING_BACKEND == "flag":
            return _encode_flag(texts, query=False)
        return _encode_fastembed(texts)


def embed_query(text: str) -> list[float]:
    with _embed_lock:
        if EMBEDDING_BACKEND == "keyword":
            return _dummy_vectors(1)[0]
        if EMBEDDING_BACKEND == "flag":
            return _encode_flag([text], query=True)[0]
        return _encode_fastembed([text])[0]
