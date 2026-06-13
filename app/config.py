from pathlib import Path

from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma"
WORKSPACES_FILE = DATA_DIR / "workspaces.json"

OPENAI_API_KEY = ""
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o-mini"

# Server-side demo key (deploy only — never commit a real key)
DEMO_API_KEY = ""
DEMO_BASE_URL = "https://api.deepseek.com/v1"
DEMO_MODEL = "deepseek-chat"
DEMO_DAILY_LIMIT = 10
DEMO_PER_MINUTE_LIMIT = 2
DEMO_MAX_CHARS = 500
DEMO_DELAY_SECONDS = 0.5

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3.2"
EMBEDDING_BACKEND = "keyword"  # keyword | fastembed | flag
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
EMBEDDING_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
KEYWORD_EMBED_DIM = 8
SKIP_DEMO_SEED = False
ALLOW_ENV_KEY_WRITE = True
# 仅自托管时开启：所有访客共用服务端 OPENAI_API_KEY（公开发布请保持 false）
USE_SERVER_API_KEY = False

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
MIN_SECTION_SIZE = 200
RECALL_TOP_K = 12
RERANK_TOP_K = 6
TOP_K = RERANK_TOP_K
MIN_RELEVANCE_SCORE = 0.38
DEMO_MIN_RELEVANCE_SCORE = 0.28
# keyword 专用后端：分数即关键词重合度，阈值需低于向量混合分
KEYWORD_MIN_RELEVANCE_SCORE = 0.15
DEMO_KEYWORD_MIN_RELEVANCE_SCORE = 0.10
INGEST_ENABLE_SUMMARY = True
ALLOWED_ORIGINS: list[str] = []


def reload_config() -> None:
    global OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
    global DEMO_API_KEY, DEMO_BASE_URL, DEMO_MODEL
    global DEMO_DAILY_LIMIT, DEMO_PER_MINUTE_LIMIT, DEMO_MAX_CHARS, DEMO_DELAY_SECONDS
    global OLLAMA_BASE_URL, OLLAMA_MODEL, EMBEDDING_BACKEND, EMBEDDING_MODEL
    global EMBEDDING_QUERY_INSTRUCTION, KEYWORD_EMBED_DIM, SKIP_DEMO_SEED
    global KEYWORD_MIN_RELEVANCE_SCORE, DEMO_KEYWORD_MIN_RELEVANCE_SCORE
    global ALLOW_ENV_KEY_WRITE, USE_SERVER_API_KEY, INGEST_ENABLE_SUMMARY
    global ALLOWED_ORIGINS

    load_dotenv(ENV_FILE, override=True)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    DEMO_API_KEY = os.getenv("DEMO_API_KEY", "").strip()
    DEMO_BASE_URL = os.getenv("DEMO_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    DEMO_MODEL = os.getenv("DEMO_MODEL", "deepseek-chat")
    DEMO_DAILY_LIMIT = int(os.getenv("DEMO_DAILY_LIMIT", "10"))
    DEMO_PER_MINUTE_LIMIT = int(os.getenv("DEMO_PER_MINUTE_LIMIT", "2"))
    DEMO_MAX_CHARS = int(os.getenv("DEMO_MAX_CHARS", "500"))
    DEMO_DELAY_SECONDS = float(os.getenv("DEMO_DELAY_SECONDS", "1.5"))
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
    EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "keyword").strip().lower()
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    EMBEDDING_QUERY_INSTRUCTION = os.getenv(
        "EMBEDDING_QUERY_INSTRUCTION",
        "为这个句子生成表示以用于检索相关文章：",
    )
    KEYWORD_EMBED_DIM = int(os.getenv("KEYWORD_EMBED_DIM", "8"))
    SKIP_DEMO_SEED = os.getenv("SKIP_DEMO_SEED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    ALLOW_ENV_KEY_WRITE = os.getenv("ALLOW_ENV_KEY_WRITE", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    USE_SERVER_API_KEY = os.getenv("USE_SERVER_API_KEY", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    INGEST_ENABLE_SUMMARY = os.getenv("INGEST_ENABLE_SUMMARY", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    KEYWORD_MIN_RELEVANCE_SCORE = float(
        os.getenv("KEYWORD_MIN_RELEVANCE_SCORE", "0.15")
    )
    DEMO_KEYWORD_MIN_RELEVANCE_SCORE = float(
        os.getenv("DEMO_KEYWORD_MIN_RELEVANCE_SCORE", "0.10")
    )
    raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
    ALLOWED_ORIGINS = [o.strip() for o in raw_origins.split(",") if o.strip()] if raw_origins else []


reload_config()
