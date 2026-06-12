from collections.abc import AsyncIterator

from app.config import (
    DEMO_KEYWORD_MIN_RELEVANCE_SCORE,
    DEMO_MIN_RELEVANCE_SCORE,
    KEYWORD_MIN_RELEVANCE_SCORE,
    MIN_RELEVANCE_SCORE,
    RECALL_TOP_K,
)
from app.services.app_mode import TIER_DEMO
from app.models import SourceChunk
from app.services.embedder import embed_query, is_keyword_backend
from app.services import llm
from app.services.app_mode import ResolvedMode
from app.services.reranker import rerank_hits
from app.services.relevance import (
    combined_score,
    keyword_overlap_score,
    keyword_retrieval_score,
    relevance_label,
    semantic_score_from_distance,
)
from app.storage.vector_store import vector_store

UNKNOWN_ANSWER_TEMPLATE = (
    "在当前资料库中没有找到足够相关的资料，无法回答该问题。"
    "（最高相关度 {score_hint}，阈值 {threshold}）"
    "建议换个问法、补充文档，或使用「检索预览」查看命中片段与分数构成。"
)


def _min_relevance_score(tier: str | None = None) -> float:
    if is_keyword_backend():
        if tier == TIER_DEMO:
            return DEMO_KEYWORD_MIN_RELEVANCE_SCORE
        return KEYWORD_MIN_RELEVANCE_SCORE
    if tier == TIER_DEMO:
        return DEMO_MIN_RELEVANCE_SCORE
    return MIN_RELEVANCE_SCORE


def _unknown_message(top_score: float | None, tier: str | None = None) -> str:
    threshold = _min_relevance_score(tier)
    hint = f"{top_score:.0%}" if top_score is not None else "—"
    return UNKNOWN_ANSWER_TEMPLATE.format(
        score_hint=hint,
        threshold=f"{threshold:.0%}",
    )


def _annotate_vector_hits(question: str, raw_hits: list[dict]) -> list[dict]:
    hits: list[dict] = []
    for hit in raw_hits:
        distance = hit.get("distance")
        semantic = semantic_score_from_distance(
            distance if distance is not None else (1.0 - hit.get("score", 0))
        )
        keyword = keyword_overlap_score(
            question,
            f"{hit.get('heading_path', '')} {hit.get('summary', '')} {hit['snippet']}",
        )
        final = combined_score(semantic, keyword)
        hit = dict(hit)
        hit["semantic_score"] = round(semantic, 4)
        hit["keyword_score"] = round(keyword, 4)
        hit["vector_score"] = final
        hit["score"] = final
        hit["relevance"] = relevance_label(final, MIN_RELEVANCE_SCORE)
        hits.append(hit)
    return sorted(hits, key=lambda h: h["score"], reverse=True)


def _merge_raw_hits(batches: list[list[dict]]) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for batch in batches:
        for hit in batch:
            key = (hit.get("document_id") or "", int(hit.get("chunk_index") or 0))
            if key in seen:
                continue
            seen.add(key)
            merged.append(hit)
    return merged


def _annotate_keyword_hits(question: str, raw_hits: list[dict]) -> list[dict]:
    min_score = KEYWORD_MIN_RELEVANCE_SCORE
    hits: list[dict] = []
    for hit in raw_hits:
        text = f"{hit.get('heading_path', '')} {hit.get('summary', '')} {hit['snippet']}"
        keyword = hit.get("keyword_score")
        if keyword is None:
            keyword = keyword_retrieval_score(question, text)
        hit = dict(hit)
        hit["semantic_score"] = 0.0
        hit["keyword_score"] = round(keyword, 4)
        hit["vector_score"] = keyword
        hit["score"] = keyword
        hit["relevance"] = relevance_label(keyword, min_score)
        hits.append(hit)
    return sorted(hits, key=lambda h: h["score"], reverse=True)


async def retrieve_hits(
    workspace_id: str,
    question: str,
    document_ids: list[str] | None = None,
    resolved: ResolvedMode | None = None,
) -> list[dict]:
    unique_ids = list(dict.fromkeys(document_ids or []))

    if is_keyword_backend():
        if len(unique_ids) > 1:
            per_doc_k = max(4, (RECALL_TOP_K + len(unique_ids) - 1) // len(unique_ids))
            batches = [
                vector_store.keyword_search(
                    workspace_id, question, top_k=per_doc_k, document_ids=[doc_id]
                )
                for doc_id in unique_ids
            ]
            raw_hits = _merge_raw_hits(batches)
        else:
            raw_hits = vector_store.keyword_search(
                workspace_id, question, document_ids=unique_ids or None
            )
        hits = _annotate_keyword_hits(question, raw_hits)
    else:
        embedding = embed_query(question)
        if len(unique_ids) > 1:
            per_doc_k = max(4, (RECALL_TOP_K + len(unique_ids) - 1) // len(unique_ids))
            batches = [
                vector_store.query(
                    workspace_id, embedding, top_k=per_doc_k, document_ids=[doc_id]
                )
                for doc_id in unique_ids
            ]
            raw_hits = _merge_raw_hits(batches)
        else:
            raw_hits = vector_store.query(
                workspace_id, embedding, document_ids=unique_ids or None
            )
        hits = _annotate_vector_hits(question, raw_hits)
    creds = resolved.credentials if resolved else None
    tier = resolved.tier if resolved else None
    return await rerank_hits(
        question,
        hits,
        document_ids=unique_ids or None,
        credentials=creds,
        tier=tier,
    )


def filter_relevant_hits(hits: list[dict], tier: str | None = None) -> list[dict]:
    min_score = _min_relevance_score(tier)
    return [hit for hit in hits if hit["score"] >= min_score]


def is_relevant(hits: list[dict], tier: str | None = None) -> bool:
    if not hits:
        return False
    min_score = _min_relevance_score(tier)
    top = hits[0]
    score = top.get("keyword_score", top["score"]) if is_keyword_backend() else top["score"]
    if score >= min_score:
        return True
    if tier == TIER_DEMO and not is_keyword_backend() and top.get("keyword_score", 0) >= 0.34:
        return True
    return False


def _to_sources(hits: list[dict]) -> list[SourceChunk]:
    return [
        SourceChunk(
            document_id=hit.get("document_id") or "",
            document=hit["document"],
            snippet=hit["snippet"],
            score=hit["score"],
            semantic_score=hit.get("semantic_score", hit["score"]),
            keyword_score=hit.get("keyword_score", 0.0),
            rerank_score=hit.get("rerank_score"),
            heading_path=hit.get("heading_path", ""),
            summary=hit.get("summary", ""),
            chunk_index=int(hit.get("chunk_index") or 0),
            relevance=hit.get("relevance", relevance_label(hit["score"], MIN_RELEVANCE_SCORE)),
        )
        for hit in hits
    ]


def _scope_document_label(relevant: list[dict], document_ids: list[str] | None) -> str | None:
    if not document_ids or not relevant:
        return None
    names: list[str] = []
    for hit in relevant:
        name = hit.get("document")
        if name and name not in names:
            names.append(name)
    return "、".join(names) if names else None


async def ask(
    workspace_id: str,
    question: str,
    document_ids: list[str] | None = None,
    resolved: ResolvedMode | None = None,
) -> tuple[str, list[SourceChunk], str]:
    creds = resolved.credentials if resolved else None
    tier = resolved.tier if resolved else None
    mode = llm.llm_mode(creds, tier)
    hits = await retrieve_hits(
        workspace_id, question, document_ids=document_ids, resolved=resolved
    )
    if not is_relevant(hits, tier):
        top = hits[0]["score"] if hits else None
        return _unknown_message(top, tier), [], mode

    relevant = filter_relevant_hits(hits, tier)
    if tier == TIER_DEMO and not relevant and hits:
        relevant = hits[:3]
    sources = _to_sources(relevant)
    scope_document = _scope_document_label(relevant, document_ids)
    answer, mode = await llm.complete_answer(
        question, relevant, scope_document, credentials=creds, tier=tier
    )
    return answer, sources, mode


async def ask_stream(
    workspace_id: str,
    question: str,
    document_ids: list[str] | None = None,
    resolved: ResolvedMode | None = None,
) -> tuple[AsyncIterator[str], list[SourceChunk], str]:
    creds = resolved.credentials if resolved else None
    tier = resolved.tier if resolved else None
    mode = llm.llm_mode(creds, tier)
    hits = await retrieve_hits(
        workspace_id, question, document_ids=document_ids, resolved=resolved
    )

    if not is_relevant(hits, tier):
        top = hits[0]["score"] if hits else None
        msg = _unknown_message(top, tier)

        async def unknown() -> AsyncIterator[str]:
            yield msg

        return unknown(), [], mode

    relevant = filter_relevant_hits(hits, tier)
    if tier == TIER_DEMO and not relevant and hits:
        relevant = hits[:3]
    sources = _to_sources(relevant)
    scope_document = _scope_document_label(relevant, document_ids)

    async def tokens() -> AsyncIterator[str]:
        async for token in llm.stream_answer(
            question,
            relevant,
            scope_document,
            credentials=creds,
            tier=tier,
        ):
            yield token

    return tokens(), sources, mode


async def preview_retrieve(
    workspace_id: str,
    question: str,
    document_ids: list[str] | None = None,
    resolved: ResolvedMode | None = None,
) -> list[SourceChunk]:
    hits = await retrieve_hits(
        workspace_id, question, document_ids=document_ids, resolved=resolved
    )
    tier = resolved.tier if resolved else None
    return _to_sources(
        filter_relevant_hits(hits, tier) if is_relevant(hits, tier) else hits[:5]
    )
