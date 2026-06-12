import json
import re

import httpx

from app.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    RERANK_TOP_K,
    MIN_RELEVANCE_SCORE,
    USE_SERVER_API_KEY,
)
from app.services import llm
from app.services.app_mode import LLMCredentials, TIER_FULL
from app.services.relevance import relevance_label


def _ensure_document_coverage(
    hits: list[dict], document_ids: list[str] | None, top_k: int
) -> list[dict]:
    if not document_ids or len(document_ids) <= 1:
        return hits[:top_k]

    selected = list(hits[:top_k])
    represented = {h.get("document_id") for h in selected}
    pool_by_doc: dict[str, list[dict]] = {}
    for hit in hits:
        doc_id = hit.get("document_id")
        if doc_id:
            pool_by_doc.setdefault(doc_id, []).append(hit)

    for doc_id in document_ids:
        if doc_id in represented:
            continue
        candidates = pool_by_doc.get(doc_id, [])
        if not candidates:
            continue
        best = candidates[0]
        if len(selected) < top_k:
            selected.append(best)
        else:
            doc_counts: dict[str, int] = {}
            for item in selected:
                did = item.get("document_id")
                doc_counts[did] = doc_counts.get(did, 0) + 1
            replace_idx = next(
                (
                    i
                    for i in range(len(selected) - 1, -1, -1)
                    if doc_counts.get(selected[i].get("document_id"), 0) > 1
                ),
                len(selected) - 1,
            )
            selected[replace_idx] = best
        represented.add(doc_id)

    selected.sort(key=lambda h: h.get("score", 0), reverse=True)
    return selected[:top_k]


async def rerank_hits(
    question: str,
    hits: list[dict],
    document_ids: list[str] | None = None,
    credentials: LLMCredentials | None = None,
    tier: str | None = None,
) -> list[dict]:
    if not hits:
        return []

    use_llm = (
        tier == TIER_FULL
        and credentials
        and credentials.api_key
        and llm.llm_mode(credentials, tier) == "openai"
    )
    if not use_llm:
        if (
            not credentials
            and USE_SERVER_API_KEY
            and OPENAI_API_KEY
            and llm.llm_mode() == "openai"
        ):
            credentials = LLMCredentials(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
                model=OPENAI_MODEL,
                source="server",
            )
            use_llm = True
        else:
            return _ensure_document_coverage(hits, document_ids, RERANK_TOP_K)

    try:
        scores = await _llm_score_hits(question, hits, credentials)
        for hit, rerank_score in zip(hits, scores):
            hit["rerank_score"] = rerank_score
            vector_score = hit.get("score", 0.0)
            hit["score"] = round(vector_score * 0.35 + rerank_score * 0.65, 4)
            hit["relevance"] = relevance_label(hit["score"], MIN_RELEVANCE_SCORE)
        hits.sort(key=lambda h: h["score"], reverse=True)
    except Exception:
        hits.sort(key=lambda h: h.get("score", 0), reverse=True)

    return _ensure_document_coverage(hits, document_ids, RERANK_TOP_K)


async def _llm_score_hits(
    question: str, hits: list[dict], credentials: LLMCredentials | None = None
) -> list[float]:
    creds = credentials or LLMCredentials(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        model=OPENAI_MODEL,
    )
    blocks = []
    for i, hit in enumerate(hits):
        path = hit.get("heading_path") or ""
        summary = hit.get("summary") or ""
        snippet = hit["snippet"][:450]
        blocks.append(
            f"[{i}] 文件:{hit['document']}\n"
            f"章节:{path or '无'}\n"
            f"摘要:{summary or '无'}\n"
            f"正文:{snippet}"
        )

    prompt = (
        f"用户问题：{question}\n\n"
        "请判断每段资料对回答该问题的帮助程度，返回 JSON 数组：\n"
        '[{"index":0,"score":0.85}]\n'
        "score 范围 0~1，0.5 以下表示基本无法回答。只输出 JSON。\n\n"
        + "\n\n".join(blocks)
    )

    payload = {
        "model": creds.model,
        "messages": [
            {"role": "system", "content": "你是检索重排助手，只输出合法 JSON 数组。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
    }
    headers = {
        "Authorization": f"Bearer {creds.api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{creds.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

    data = _parse_json_array(content)
    scores = [0.0] * len(hits)
    for item in data:
        idx = int(item.get("index", -1))
        if 0 <= idx < len(hits):
            scores[idx] = max(0.0, min(1.0, float(item.get("score", 0))))
    return scores


def _parse_json_array(text: str) -> list[dict]:
    text = text.strip()
    if "```" in text:
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)
