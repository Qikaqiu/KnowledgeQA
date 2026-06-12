from functools import lru_cache

import numpy as np
import torch
from FlagEmbedding import FlagModel

from app.config import EMBEDDING_MODEL, EMBEDDING_QUERY_INSTRUCTION


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
    model = get_embedder()
    vectors = model.encode_corpus(texts, batch_size=32)
    return _to_vectors(vectors)


def embed_query(text: str) -> list[float]:
    model = get_embedder()
    vectors = model.encode_queries([text])
    return _to_vectors(vectors)[0]
