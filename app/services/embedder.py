import threading
from functools import lru_cache

import numpy as np
import torch
from FlagEmbedding import FlagModel

from app.config import EMBEDDING_MODEL, EMBEDDING_QUERY_INSTRUCTION

# 低配服务器（如 Railway）上并发向量化易 OOM，串行化所有嵌入调用
_embed_lock = threading.Lock()


@lru_cache(maxsize=1)
def get_embedder() -> FlagModel:
    return FlagModel(
        EMBEDDING_MODEL,
        query_instruction_for_retrieval=EMBEDDING_QUERY_INSTRUCTION,
        use_fp16=torch.cuda.is_available(),
    )


def clear_embedder_cache() -> None:
    get_embedder.cache_clear()


def _to_vectors(embeddings) -> list[list[float]]:
    if isinstance(embeddings, np.ndarray):
        if embeddings.ndim == 1:
            return [embeddings.tolist()]
        return [row.tolist() for row in embeddings]
    return [vector.tolist() for vector in embeddings]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    with _embed_lock:
        model = get_embedder()
        vectors = model.encode_corpus(texts, batch_size=16)
        return _to_vectors(vectors)


def embed_query(text: str) -> list[float]:
    with _embed_lock:
        model = get_embedder()
        vectors = model.encode_queries([text])
        return _to_vectors(vectors)[0]
