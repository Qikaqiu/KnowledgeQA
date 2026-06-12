import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from app.config import (
    DEMO_DELAY_SECONDS,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
)
from app.services.app_mode import LLMCredentials, TIER_DEMO, TIER_FULL


SYSTEM_PROMPT = """你是私人知识库助手。只能根据提供的资料片段回答，不要编造。
如果资料不足以回答，请明确说明。回答使用中文，简洁准确。
引用资料时必须在句末标注编号，格式为（资料1）或（资料2、资料3），编号与提供的 [资料N] 一致。
只引用实际用到的资料，不要引用未使用的片段。"""


def llm_mode(
    credentials: LLMCredentials | None = None,
    tier: str | None = None,
) -> str:
    if credentials and credentials.api_key:
        return "openai"
    if tier not in (TIER_FULL, TIER_DEMO) and _ollama_available():
        return "ollama"
    return "retrieval"


def _ollama_available() -> bool:
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


def build_context(sources: list[dict]) -> str:
    blocks = []
    for i, src in enumerate(sources, start=1):
        path = src.get("heading_path") or ""
        summary = src.get("summary") or ""
        lines = [f"[资料{i}] 文件: {src['document']}"]
        if path:
            lines.append(f"章节: {path}")
        if summary:
            lines.append(f"摘要: {summary}")
        lines.append(f"内容: {src['snippet']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def build_user_prompt(
    question: str, sources: list[dict], scope_document: str | None = None
) -> str:
    context = build_context(sources)
    if scope_document and "、" in scope_document:
        scope_line = f"（仅参考以下文件：{scope_document}）\n"
    elif scope_document:
        scope_line = f"（仅参考文件《{scope_document}》）\n"
    else:
        scope_line = ""
    return f"{scope_line}资料片段:\n{context}\n\n用户问题: {question}"


def retrieval_answer(question: str, sources: list[dict]) -> str:
    if not sources:
        return (
            "当前资料库还没有足够相关的资料。请先上传文档，或换个问法后重试。"
            "（检索模式：请配置 API Key 或点击「免费试用」体验演示模式。）"
        )

    lines = [
        "以下回答基于资料库检索结果生成（检索模式，配置 API Key 后可获得完整 LLM 回答）：",
        "",
    ]
    for i, src in enumerate(sources[:3], start=1):
        snippet = src["snippet"].replace("\n", " ")
        if len(snippet) > 220:
            snippet = snippet[:220] + "..."
        relevance = src.get("relevance") or f"相关度 {src['score']:.0%}"
        chunk = src.get("chunk_index")
        chunk_label = f"，片段 #{int(chunk) + 1}" if chunk is not None else ""
        lines.append(f"资料{i}：《{src['document']}》（{relevance}{chunk_label}）")
        lines.append(f"   {snippet}")
        lines.append("")

    best = sources[0]["snippet"].replace("\n", " ")
    lines.append("综合摘要：")
    lines.append(best[:600] + ("..." if len(best) > 600 else ""))
    return "\n".join(lines)


async def stream_openai(
    question: str,
    sources: list[dict],
    scope_document: str | None = None,
    credentials: LLMCredentials | None = None,
) -> AsyncIterator[str]:
    creds = credentials or LLMCredentials(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        model=OPENAI_MODEL,
    )
    payload = {
        "model": creds.model,
        "stream": True,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_user_prompt(question, sources, scope_document),
            },
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {creds.api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{creds.base_url}/chat/completions",
            headers=headers,
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"].get("content")
                if delta:
                    yield delta


async def stream_ollama(
    question: str, sources: list[dict], scope_document: str | None = None
) -> AsyncIterator[str]:
    payload = {
        "model": OLLAMA_MODEL,
        "stream": True,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_user_prompt(question, sources, scope_document),
            },
        ],
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content")
                if content:
                    yield content


async def complete_answer(
    question: str,
    sources: list[dict],
    scope_document: str | None = None,
    credentials: LLMCredentials | None = None,
    tier: str | None = None,
) -> tuple[str, str]:
    mode = llm_mode(credentials, tier)
    if mode == "retrieval":
        return retrieval_answer(question, sources), mode

    parts: list[str] = []
    if mode == "openai":
        streamer = stream_openai(question, sources, scope_document, credentials)
    else:
        streamer = stream_ollama(question, sources, scope_document)
    async for token in streamer:
        parts.append(token)
    return "".join(parts), mode


def _openai_failure_message(
    exc: Exception, credentials: LLMCredentials | None
) -> str:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if credentials and credentials.source == "user" and status in (401, 403):
        return (
            "API Key 无效或已过期，无法调用大模型。请打开「AI 配置」重新验证 Key，"
            "或点击「清除 Key」回到演示模式。"
        )
    if status:
        return f"模型调用失败（HTTP {status}）。请检查 Key、Base URL 与模型名称。"
    return f"模型调用失败：{exc}"


async def stream_answer(
    question: str,
    sources: list[dict],
    scope_document: str | None = None,
    credentials: LLMCredentials | None = None,
    tier: str | None = None,
) -> AsyncIterator[str]:
    mode = llm_mode(credentials, tier)
    if mode == "retrieval":
        yield retrieval_answer(question, sources)
        return

    if tier == TIER_DEMO and DEMO_DELAY_SECONDS > 0:
        await asyncio.sleep(DEMO_DELAY_SECONDS)

    try:
        if mode == "openai":
            async for token in stream_openai(
                question, sources, scope_document, credentials
            ):
                yield token
        else:
            async for token in stream_ollama(question, sources, scope_document):
                yield token
    except httpx.HTTPError as exc:
        yield _openai_failure_message(exc, credentials)
    except Exception as exc:
        yield _openai_failure_message(exc, credentials)


async def validate_api_key(api_key: str, base_url: str, model: str) -> tuple[bool, str]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            if resp.status_code == 200:
                return True, "API Key 验证成功"
            detail = resp.text[:200]
            return False, f"验证失败 ({resp.status_code}): {detail}"
    except Exception as exc:
        return False, f"无法连接 API: {exc}"
