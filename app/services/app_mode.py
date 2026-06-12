"""Deployment tier detection, demo quota, and LLM credential resolution."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from fastapi import HTTPException, Request

from app.config import (
    DATA_DIR,
    DEMO_API_KEY,
    DEMO_BASE_URL,
    DEMO_DAILY_LIMIT,
    DEMO_DELAY_SECONDS,
    DEMO_MAX_CHARS,
    DEMO_MODEL,
    DEMO_PER_MINUTE_LIMIT,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    USE_SERVER_API_KEY,
)

QUOTA_FILE = DATA_DIR / "demo_quotas.json"

TIER_DEMO = "demo"
TIER_FULL = "full"
TIER_RETRIEVAL = "retrieval"


@dataclass
class LLMCredentials:
    api_key: str
    base_url: str
    model: str
    source: str = "none"  # user | demo | server | none


@dataclass
class ResolvedMode:
    tier: str
    credentials: LLMCredentials | None
    provider_label: str
    demo_remaining: int | None = None
    demo_daily_limit: int | None = None
    features: dict[str, bool] | None = None


def demo_available() -> bool:
    return bool(DEMO_API_KEY)


def _default_features(tier: str) -> dict[str, bool]:
    if tier == TIER_FULL:
        return {
            "llm_chat": True,
            "llm_rerank": True,
            "retrieve_preview": True,
            "chat_history": True,
            "batch_upload": True,
            "advanced_settings": True,
        }
    if tier == TIER_DEMO:
        return {
            "llm_chat": True,
            "llm_rerank": False,
            "retrieve_preview": True,
            "chat_history": False,
            "batch_upload": False,
            "advanced_settings": False,
        }
    return {
        "llm_chat": False,
        "llm_rerank": False,
        "retrieve_preview": True,
        "chat_history": True,
        "batch_upload": True,
        "advanced_settings": False,
    }


def _provider_label(credentials: LLMCredentials | None, tier: str) -> str:
    if tier == TIER_DEMO:
        return f"演示模式 · {credentials.model if credentials else DEMO_MODEL}"
    if tier == TIER_FULL and credentials:
        url = credentials.base_url.lower()
        if "deepseek" in url:
            return f"完整模式 · DeepSeek · {credentials.model}"
        return f"完整模式 · {credentials.model}"
    return "检索模式 · 请配置 API Key 或试用演示"


def parse_user_headers(request: Request) -> LLMCredentials | None:
    key = (request.headers.get("X-User-Api-Key") or "").strip()
    if not key:
        return None
    base_url = (request.headers.get("X-User-Base-Url") or OPENAI_BASE_URL).strip().rstrip("/")
    model = (request.headers.get("X-User-Model") or OPENAI_MODEL).strip()
    return LLMCredentials(api_key=key, base_url=base_url, model=model, source="user")


def resolve_server_credentials() -> LLMCredentials | None:
    if USE_SERVER_API_KEY and OPENAI_API_KEY:
        return LLMCredentials(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            model=OPENAI_MODEL,
            source="server",
        )
    return None


def resolve_demo_credentials() -> LLMCredentials | None:
    if not DEMO_API_KEY:
        return None
    return LLMCredentials(
        api_key=DEMO_API_KEY,
        base_url=DEMO_BASE_URL,
        model=DEMO_MODEL,
        source="demo",
    )


def client_id(request: Request) -> str:
    session = (request.headers.get("X-Session-Id") or "").strip() or "anonymous"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    else:
        ip = "unknown"
    return f"{ip}:{session}"


def _load_quota_store() -> dict:
    if not QUOTA_FILE.exists():
        return {}
    try:
        return json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_quota_store(store: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    QUOTA_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def get_demo_quota(client: str) -> dict:
    today = date.today().isoformat()
    store = _load_quota_store()
    entry = store.get(client, {})
    if entry.get("date") != today:
        entry = {"date": today, "daily_count": 0, "minute_timestamps": []}
    minute_ts = [t for t in entry.get("minute_timestamps", []) if time.time() - t < 60]
    remaining = max(0, DEMO_DAILY_LIMIT - int(entry.get("daily_count", 0)))
    return {
        "daily_limit": DEMO_DAILY_LIMIT,
        "daily_used": int(entry.get("daily_count", 0)),
        "remaining": remaining,
        "per_minute_limit": DEMO_PER_MINUTE_LIMIT,
        "minute_used": len(minute_ts),
        "max_chars": DEMO_MAX_CHARS,
    }


def check_demo_quota(client: str) -> None:
    quota = get_demo_quota(client)
    if quota["remaining"] <= 0:
        raise HTTPException(
            status_code=429,
            detail=f"演示模式今日试用次数已用完（{DEMO_DAILY_LIMIT} 次/天）。请配置自己的 API Key 解锁完整功能。",
        )
    if quota["minute_used"] >= DEMO_PER_MINUTE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"演示模式请求过于频繁，请 {60} 秒后再试，或配置 API Key 获得完整体验。",
        )


def consume_demo_quota(client: str) -> dict:
    check_demo_quota(client)
    today = date.today().isoformat()
    store = _load_quota_store()
    entry = store.get(client, {})
    if entry.get("date") != today:
        entry = {"date": today, "daily_count": 0, "minute_timestamps": []}
    minute_ts = [t for t in entry.get("minute_timestamps", []) if time.time() - t < 60]
    entry["daily_count"] = int(entry.get("daily_count", 0)) + 1
    minute_ts.append(time.time())
    entry["minute_timestamps"] = minute_ts[-20:]
    entry["date"] = today
    store[client] = entry
    _save_quota_store(store)
    return get_demo_quota(client)


def resolve_mode(request: Request, *, consume_demo: bool = False) -> ResolvedMode:
    user_creds = parse_user_headers(request)
    if user_creds:
        mode = ResolvedMode(
            tier=TIER_FULL,
            credentials=user_creds,
            provider_label="",
            features=_default_features(TIER_FULL),
        )
        mode.provider_label = _provider_label(user_creds, TIER_FULL)
        return mode

    server_creds = resolve_server_credentials()
    if server_creds:
        mode = ResolvedMode(
            tier=TIER_FULL,
            credentials=server_creds,
            provider_label="",
            features=_default_features(TIER_FULL),
        )
        mode.provider_label = _provider_label(server_creds, TIER_FULL)
        return mode

    demo_creds = resolve_demo_credentials()
    if demo_creds:
        cid = client_id(request)
        quota = consume_demo_quota(cid) if consume_demo else get_demo_quota(cid)
        mode = ResolvedMode(
            tier=TIER_DEMO,
            credentials=demo_creds,
            provider_label="",
            demo_remaining=quota["remaining"],
            demo_daily_limit=quota["daily_limit"],
            features=_default_features(TIER_DEMO),
        )
        mode.provider_label = _provider_label(demo_creds, TIER_DEMO)
        return mode

    return ResolvedMode(
        tier=TIER_RETRIEVAL,
        credentials=None,
        provider_label=_provider_label(None, TIER_RETRIEVAL),
        features=_default_features(TIER_RETRIEVAL),
    )


def mode_info(request: Request) -> dict:
    user_creds = parse_user_headers(request)
    has_user_key = bool(user_creds)
    resolved = resolve_mode(request)
    quota = get_demo_quota(client_id(request)) if demo_available() else None
    tier_source = "retrieval"
    if has_user_key:
        tier_source = "user"
    elif resolved.tier == TIER_DEMO:
        tier_source = "demo"
    elif resolved.tier == TIER_FULL:
        tier_source = "server"
    return {
        "tier": resolved.tier,
        "tier_source": tier_source,
        "provider_label": resolved.provider_label,
        "demo_available": demo_available(),
        "has_user_api_key": has_user_key,
        "demo_quota": quota,
        "features": resolved.features,
        "limits": {
            "demo_max_chars": DEMO_MAX_CHARS,
            "demo_delay_seconds": DEMO_DELAY_SECONDS,
        },
    }
