from app.config import (
    ALLOW_ENV_KEY_WRITE,
    ENV_FILE,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    reload_config,
)
from app.services import llm
from app.services.app_mode import demo_available, resolve_server_credentials


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


def _provider_label() -> str:
    server = resolve_server_credentials()
    if server:
        url = server.base_url.lower()
        if "deepseek" in url:
            return f"DeepSeek · {server.model}"
        return f"API · {server.model}"
    if demo_available():
        return "演示模式可用 · 请配置 API Key 解锁完整功能"
    return "检索模式"


def get_settings() -> dict:
    return {
        "openai_api_key_set": bool(OPENAI_API_KEY),
        "openai_api_key_masked": _mask_key(OPENAI_API_KEY),
        "openai_base_url": OPENAI_BASE_URL,
        "openai_model": OPENAI_MODEL,
        "ollama_base_url": OLLAMA_BASE_URL,
        "ollama_model": OLLAMA_MODEL,
        "llm_mode": llm.llm_mode(),
        "provider_label": _provider_label(),
        "allow_env_key_write": ALLOW_ENV_KEY_WRITE,
        "demo_available": demo_available(),
    }


def _read_env_lines() -> list[str]:
    if not ENV_FILE.exists():
        return []
    return ENV_FILE.read_text(encoding="utf-8").splitlines()


def _write_env_value(key: str, value: str) -> None:
    lines = _read_env_lines()
    prefix = f"{key}="
    replaced = False
    new_lines: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            new_lines.append(f"{prefix}{value}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{prefix}{value}")
    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def update_settings(
    *,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    openai_model: str | None = None,
    ollama_base_url: str | None = None,
    ollama_model: str | None = None,
    clear_api_key: bool = False,
) -> dict:
    if not ALLOW_ENV_KEY_WRITE:
        raise ValueError("当前部署不允许通过网页写入服务端 API Key，请在浏览器中配置个人 Key")

    if not ENV_FILE.exists():
        ENV_FILE.write_text("", encoding="utf-8")

    if clear_api_key:
        _write_env_value("OPENAI_API_KEY", "")
    elif openai_api_key is not None and openai_api_key.strip():
        _write_env_value("OPENAI_API_KEY", openai_api_key.strip())

    if openai_base_url is not None:
        _write_env_value("OPENAI_BASE_URL", openai_base_url.strip().rstrip("/"))
    if openai_model is not None:
        _write_env_value("OPENAI_MODEL", openai_model.strip())
    if ollama_base_url is not None:
        _write_env_value("OLLAMA_BASE_URL", ollama_base_url.strip().rstrip("/"))
    if ollama_model is not None:
        _write_env_value("OLLAMA_MODEL", ollama_model.strip())

    reload_config()
    return get_settings()
