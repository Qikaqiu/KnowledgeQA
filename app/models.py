from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)


class Workspace(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    document_count: int = 0


class DocumentInfo(BaseModel):
    id: str
    filename: str
    size: int
    uploaded_at: str
    chunk_count: int
    status: Literal["processing", "ready", "error"] = "ready"
    error_message: str = ""


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    stream: bool = True
    document_id: str | None = None
    document_ids: list[str] | None = None


class SourceChunk(BaseModel):
    document_id: str = ""
    document: str
    snippet: str
    score: float
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    rerank_score: float | None = None
    heading_path: str = ""
    summary: str = ""
    chunk_index: int = 0
    relevance: str = ""


class SettingsView(BaseModel):
    openai_api_key_set: bool
    openai_api_key_masked: str
    openai_base_url: str
    openai_model: str
    ollama_base_url: str
    ollama_model: str
    llm_mode: str
    provider_label: str
    allow_env_key_write: bool = True
    demo_available: bool = False


class ValidateKeyRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=512)
    base_url: str = Field(default="https://api.deepseek.com/v1")
    model: str = Field(default="deepseek-chat")


class ValidateKeyResponse(BaseModel):
    ok: bool
    message: str


class ModeInfo(BaseModel):
    tier: str
    tier_source: str = "retrieval"
    provider_label: str
    demo_available: bool
    has_user_api_key: bool
    startup_ready: bool = True
    demo_quota: dict | None = None
    demo_catalog: dict | None = None
    features: dict[str, bool]
    limits: dict[str, float | int]


class SettingsUpdate(BaseModel):
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    clear_api_key: bool = False


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    mode: Literal["openai", "ollama", "retrieval"]


class UploadResponse(BaseModel):
    document: DocumentInfo
    message: str


class ChunkInfo(BaseModel):
    chunk_index: int
    char_count: int
    text: str
    filename: str
    heading_path: str = ""
    summary: str = ""


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    document_id: str | None = None
    document_ids: list[str] | None = None


class RetrievePreviewResponse(BaseModel):
    query: str
    hits: list[SourceChunk]
