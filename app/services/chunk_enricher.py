import json
import re

import httpx

from app.config import (
    DEMO_API_KEY,
    DEMO_BASE_URL,
    DEMO_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    USE_SERVER_API_KEY,
)


def _ingest_credentials() -> tuple[str, str, str]:
    if USE_SERVER_API_KEY and OPENAI_API_KEY:
        return OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
    if DEMO_API_KEY:
        return DEMO_API_KEY, DEMO_BASE_URL, DEMO_MODEL
    return "", OPENAI_BASE_URL, OPENAI_MODEL

HEADING_PARSE = re.compile(r"^(#{1,6})\s+(.+)$")


def build_embed_text(body: str, heading_path: str = "", summary: str = "") -> str:
    parts: list[str] = []
    if heading_path:
        parts.append(f"章节: {heading_path}")
    if summary:
        parts.append(f"摘要: {summary}")
    parts.append(body)
    return "\n".join(parts)


async def enrich_chunks(chunks: list[dict]) -> None:
    """为每个片段生成摘要并构造用于向量化的文本。"""
    if not chunks:
        return
    if not _ingest_credentials()[0]:
        for chunk in chunks:
            chunk["summary"] = ""
            chunk["embed_text"] = build_embed_text(
                chunk["body"], chunk.get("heading_path", "")
            )
        return

    batch_size = 6
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        summaries = await _summarize_batch(batch)
        for chunk, summary in zip(batch, summaries):
            chunk["summary"] = summary
            chunk["embed_text"] = build_embed_text(
                chunk["body"],
                chunk.get("heading_path", ""),
                summary,
            )


async def _summarize_batch(chunks: list[dict]) -> list[str]:
    lines = []
    for i, chunk in enumerate(chunks):
        path = chunk.get("heading_path") or "（无标题）"
        body = chunk["body"][:500]
        lines.append(f"[{i}] 章节:{path}\n{body}")

    prompt = (
        "为每段资料写一句中文摘要（不超过60字），概括这段的核心主题。\n"
        "只返回 JSON 数组，格式: [{\"index\":0,\"summary\":\"...\"}]\n\n"
        + "\n\n".join(lines)
    )

    try:
        content = await _chat_completion(prompt, temperature=0.1)
        data = _parse_json_array(content)
        result = [""] * len(chunks)
        for item in data:
            idx = int(item.get("index", -1))
            if 0 <= idx < len(chunks):
                result[idx] = str(item.get("summary", "")).strip()
        return result
    except Exception:
        return [""] * len(chunks)


async def _chat_completion(prompt: str, temperature: float = 0.2) -> str:
    api_key, base_url, model = _ingest_credentials()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是文档摘要助手，只输出合法 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


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
