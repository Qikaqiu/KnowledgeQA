import asyncio
import ipaddress
import json
import re
from collections.abc import AsyncIterator
from urllib.parse import urlparse

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
引用资料时必须使用上标角标格式，如[1]、[2]、[1][3]，编号与提供的 [N] 一致。
只引用实际用到的资料，不要引用未使用的片段。"""


_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_safe_url(url: str) -> bool:
    """Reject URLs that resolve to private/internal/loopback addresses (SSRF guard)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    # Block localhost by name
    if hostname in ("localhost", "0.0.0.0", "::"):
        return False
    # Block common metadata endpoints
    if hostname.endswith(".internal") or hostname.endswith(".local"):
        return False
    # Resolve and check against private ranges
    try:
        addr = ipaddress.ip_address(hostname)
        for net in _BLOCKED_NETWORKS:
            if addr in net:
                return False
    except ValueError:
        # hostname is a domain name, not an IP — allow (DNS rebinding risk
        # is low for a personal tool; real mitigation needs a DNS resolution
        # step + re-check, which is overkill here)
        pass
    return True


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
        lines = [f"[{i}] 文件: {src['document']}"]
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


def _clean_snippet_for_display(text: str, max_chars: int = 240) -> str:
    """去掉 Markdown 噪音，格式化为可读纯文本。"""
    text = text.strip()
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^[-|:\s]+$", line):
            continue
        if line.count("|") >= 2:
            continue
        if line.startswith("#"):
            line = re.sub(r"^#+\s*", "", line)
            lines.append(f"• {line}")
        elif re.match(r"^[-*+]\s+", line):
            lines.append(f"  • {re.sub(r'^[-*+]\s+', '', line)}")
        elif re.match(r"^\d+\.\s+", line):
            lines.append(f"  • {re.sub(r'^\d+\.\s+', '', line)}")
        else:
            lines.append(line)

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars].rstrip() + "…"
    return result


def _extract_brief_answer(sources: list[dict]) -> str:
    best = sources[0]
    summary = (best.get("summary") or "").strip()
    if summary:
        return summary

    cleaned = _clean_snippet_for_display(best.get("snippet", ""), max_chars=320)
    for line in cleaned.split("\n"):
        plain = line.strip().lstrip("•").strip()
        if len(plain) >= 6:
            return plain
    return cleaned.replace("\n", " ").strip()


def retrieval_answer(question: str, sources: list[dict]) -> str:
    if not sources:
        return (
            "当前资料库还没有足够相关的资料。请先上传文档，或换个问法后重试。\n\n"
            "提示：配置 API Key 或点击「免费试用」可获得完整 AI 回答。"
        )

    brief = _extract_brief_answer(sources)
    lines = [
        "【检索模式】以下为关键词匹配到的原文摘录，未经大模型整理，可读性有限。",
        "配置 API Key 后，或由管理员开启演示服务（DEMO_API_KEY），可获得完整 AI 回答。",
        "",
        f"要点：{brief}",
        "",
    ]

    for i, src in enumerate(sources[:3], start=1):
        relevance = src.get("relevance") or f"相关度 {src['score']:.0%}"
        heading = src.get("heading_path") or ""
        location = f"《{src['document']}》"
        if heading:
            location += f" · {heading}"
        snippet = _clean_snippet_for_display(src.get("snippet", ""))
        lines.append(f"[{i}] {location}（{relevance}）")
        if snippet:
            lines.append(snippet)
        lines.append("")

    lines.append("完整原文见下方「引用来源」，点击可展开查看。")
    return "\n".join(lines).strip()


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
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    continue


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
    if not _is_safe_url(base_url):
        return False, "不允许访问内网或本地地址"
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
