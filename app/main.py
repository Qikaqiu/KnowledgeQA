import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, DATA_DIR, DEMO_MAX_CHARS, UPLOAD_DIR
from app.config import (
    ALLOWED_ORIGINS,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    MIN_RELEVANCE_SCORE,
    MIN_SECTION_SIZE,
    RECALL_TOP_K,
    RERANK_TOP_K,
    TOP_K,
)
from app.models import (
    ChatRequest,
    ChatResponse,
    ChunkInfo,
    DocumentInfo,
    ModeInfo,
    RetrievePreviewResponse,
    RetrieveRequest,
    SettingsUpdate,
    SettingsView,
    UploadResponse,
    ValidateKeyRequest,
    ValidateKeyResponse,
    Workspace,
    WorkspaceCreate,
    WorkspaceUpdate,
)
from app.services.app_mode import TIER_DEMO, mode_info, resolve_mode
from app.services.settings_manager import get_settings, update_settings
from app.services.document_parser import SUPPORTED_SUFFIXES, SUPPORTED_FORMATS_LABEL, is_supported
from app.services.ingest import delete_document, ingest_file
from app.services.demo_seed import ensure_demo_data, get_demo_catalog
from app.services.rag import ask, ask_stream, preview_retrieve
from app.storage.workspaces import (
    create_workspace,
    delete_workspace,
    ensure_seed_workspaces,
    get_workspace,
    list_workspaces,
    update_workspace,
)
from app.storage import vector_store as vs
from app.services import llm

logger = logging.getLogger(__name__)
_startup_ready = False


def _resolve_document_ids(document_id: str | None, document_ids: list[str] | None) -> list[str] | None:
    if document_ids:
        unique = list(dict.fromkeys(document_ids))
        return unique or None
    if document_id:
        return [document_id]
    return None


app = FastAPI(title="私人知识问答库", version="0.1.0")

app.add_middleware(GZipMiddleware, minimum_size=500)

if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

STATIC_DIR = BASE_DIR / "static"


@app.middleware("http")
async def add_static_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/"):
        if any(path.endswith(ext) for ext in (".js", ".css", ".png", ".svg", ".woff2")):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=86400"
    return response


def _ensure_data_dir_writable() -> None:
    probe = DATA_DIR / ".write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise RuntimeError(
            f"数据目录不可写: {DATA_DIR}。请挂载持久卷或将 DATA_DIR 指向可写路径。"
        ) from exc


async def seed_sample_documents() -> None:
    from app.services.demo_seed import seed_from_sample_dirs

    await seed_from_sample_dirs()


async def _background_startup() -> None:
    global _startup_ready
    try:
        from app.config import SKIP_DEMO_SEED
        from app.services.embedding_migrate import ensure_embedding_index
        from app.services.embedder import embed_texts, is_keyword_backend

        from app.services.ingest import recover_processing_documents

        await ensure_embedding_index()
        await recover_processing_documents()
        if not SKIP_DEMO_SEED:
            await seed_sample_documents()
        if not is_keyword_backend():
            await asyncio.to_thread(embed_texts, ["预热"])
        logger.info("Background startup complete")
        _startup_ready = True
    except Exception:
        logger.exception("Background startup failed")


@app.on_event("startup")
async def startup() -> None:
    global _startup_ready
    _startup_ready = False
    for path in (DATA_DIR, UPLOAD_DIR, STATIC_DIR):
        path.mkdir(parents=True, exist_ok=True)
    _ensure_data_dir_writable()
    ensure_seed_workspaces()
    asyncio.create_task(_background_startup())


@app.get("/api/health")
def health(request: Request):
    settings = get_settings()
    mode = mode_info(request)
    return {
        "status": "ok",
        "startup_ready": _startup_ready,
        "embedding_backend": mode.get("embedding_backend", ""),
        "llm_mode": settings["llm_mode"],
        "provider_label": mode["provider_label"],
        "tier": mode["tier"],
        "demo_available": mode["demo_available"],
        "workspaces": len(list_workspaces()),
    }


@app.get("/api/mode", response_model=ModeInfo)
def api_mode(request: Request):
    info = mode_info(request)
    info["startup_ready"] = _startup_ready
    if info["tier"] == "demo" or info.get("demo_available"):
        info["demo_catalog"] = get_demo_catalog()
    return ModeInfo(**info)


@app.post("/api/demo/ensure")
async def api_demo_ensure():
    return await ensure_demo_data()


@app.get("/api/settings", response_model=SettingsView)
def api_get_settings():
    return SettingsView(**get_settings())


@app.put("/api/settings", response_model=SettingsView)
def api_update_settings(body: SettingsUpdate):
    try:
        return SettingsView(**update_settings(**body.model_dump(exclude_unset=True)))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/api/settings/validate", response_model=ValidateKeyResponse)
async def api_validate_key(body: ValidateKeyRequest):
    ok, message = await llm.validate_api_key(
        body.api_key.strip(),
        body.base_url.strip().rstrip("/"),
        body.model.strip(),
    )
    return ValidateKeyResponse(ok=ok, message=message)


@app.get("/api/workspaces", response_model=list[Workspace])
def api_list_workspaces():
    return [Workspace(**ws) for ws in list_workspaces()]


@app.post("/api/workspaces", response_model=Workspace)
def api_create_workspace(body: WorkspaceCreate):
    ws = create_workspace(body.name, body.description)
    return Workspace(**ws)


@app.put("/api/workspaces/{workspace_id}", response_model=Workspace)
def api_update_workspace(workspace_id: str, body: WorkspaceUpdate):
    if not get_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="资料库不存在")
    ws = update_workspace(
        workspace_id,
        name=body.name,
        description=body.description,
    )
    if not ws:
        raise HTTPException(status_code=404, detail="资料库不存在")
    return Workspace(**ws)


@app.delete("/api/workspaces/{workspace_id}")
def api_delete_workspace(workspace_id: str):
    if not get_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="资料库不存在")
    if not delete_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="资料库不存在")
    return {"ok": True}


@app.get("/api/workspaces/{workspace_id}/documents", response_model=list[DocumentInfo])
def api_list_documents(workspace_id: str):
    if not get_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="资料库不存在")
    return [DocumentInfo(**doc) for doc in vs.load_documents(workspace_id)]


@app.post("/api/workspaces/{workspace_id}/documents", response_model=UploadResponse)
async def api_upload_document(workspace_id: str, file: UploadFile = File(...)):
    if not get_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="资料库不存在")
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件不能超过 20MB")
    if not is_supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型。支持: {SUPPORTED_FORMATS_LABEL}",
        )

    try:
        meta = await ingest_file(workspace_id, file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("Upload storage failed for workspace %s", workspace_id)
        raise HTTPException(
            status_code=507,
            detail=f"文件保存失败，请确认已挂载持久卷到 data 目录: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Upload failed for workspace %s", workspace_id)
        raise HTTPException(status_code=500, detail=f"上传处理失败: {exc}") from exc

    if meta.get("status") == "processing":
        message = "文件已接收，正在后台解析与向量化，请稍候刷新列表"
    else:
        message = f"已入库 {meta['chunk_count']} 个片段（含章节路径与 AI 摘要）"

    return UploadResponse(
        document=DocumentInfo(**meta),
        message=message,
    )


@app.get(
    "/api/workspaces/{workspace_id}/documents/{document_id}/chunks",
    response_model=list[ChunkInfo],
)
def api_list_document_chunks(workspace_id: str, document_id: str):
    if not get_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="资料库不存在")
    doc = next((d for d in vs.load_documents(workspace_id) if d["id"] == document_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    chunks = vs.vector_store.list_document_chunks(workspace_id, document_id)
    return [ChunkInfo(**chunk) for chunk in chunks]


@app.post(
    "/api/workspaces/{workspace_id}/retrieve",
    response_model=RetrievePreviewResponse,
)
async def api_retrieve_preview(workspace_id: str, body: RetrieveRequest, request: Request):
    if not get_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="资料库不存在")
    resolved = resolve_mode(request)
    if not resolved.features.get("retrieve_preview", True):
        raise HTTPException(
            status_code=403,
            detail="演示模式不支持检索预览，请配置 API Key 解锁完整功能。",
        )
    query = body.query.strip()
    doc_ids = _resolve_document_ids(body.document_id, body.document_ids)
    hits = await preview_retrieve(
        workspace_id, query, document_ids=doc_ids, resolved=resolved
    )
    return RetrievePreviewResponse(query=query, hits=hits)


@app.get("/api/rag-config")
def api_rag_config():
    return {
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "min_section_size": MIN_SECTION_SIZE,
        "recall_top_k": RECALL_TOP_K,
        "rerank_top_k": RERANK_TOP_K,
        "top_k": TOP_K,
        "min_relevance_score": MIN_RELEVANCE_SCORE,
        "score_formula": "向量召回 → DeepSeek重排(65%) + 向量分(35%)，入库嵌入含章节路径与摘要",
    }


@app.get("/api/workspaces/{workspace_id}/documents/{document_id}/file")
def api_download_document(workspace_id: str, document_id: str):
    if not get_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="资料库不存在")

    doc = next((d for d in vs.load_documents(workspace_id) if d["id"] == document_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    path = Path(doc["stored_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件已丢失")

    return FileResponse(path, filename=doc["filename"], media_type="application/octet-stream")


@app.delete("/api/workspaces/{workspace_id}/documents/{document_id}")
async def api_delete_document(workspace_id: str, document_id: str):
    if not get_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="资料库不存在")
    ok = await delete_document(workspace_id, document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"ok": True}


@app.post("/api/workspaces/{workspace_id}/chat", response_model=ChatResponse)
async def api_chat(workspace_id: str, body: ChatRequest, request: Request):
    if not get_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="资料库不存在")

    message = body.message.strip()
    resolved = resolve_mode(request, consume_demo=True)
    if resolved.tier == TIER_DEMO and len(message) > DEMO_MAX_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"演示模式单次提问不超过 {DEMO_MAX_CHARS} 字，请配置 API Key 解锁完整功能。",
        )

    doc_ids = _resolve_document_ids(body.document_id, body.document_ids)
    answer, sources, mode = await ask(
        workspace_id, message, document_ids=doc_ids, resolved=resolved
    )
    return ChatResponse(answer=answer, sources=sources, mode=mode)


@app.post("/api/workspaces/{workspace_id}/chat/stream")
async def api_chat_stream(workspace_id: str, body: ChatRequest, request: Request):
    if not get_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="资料库不存在")

    message = body.message.strip()
    resolved = resolve_mode(request, consume_demo=True)
    if resolved.tier == TIER_DEMO and len(message) > DEMO_MAX_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"演示模式单次提问不超过 {DEMO_MAX_CHARS} 字，请配置 API Key 解锁完整功能。",
        )

    doc_ids = _resolve_document_ids(body.document_id, body.document_ids)
    token_stream, sources, mode = await ask_stream(
        workspace_id, message, document_ids=doc_ids, resolved=resolved
    )

    async def event_generator():
        meta = {
            "type": "meta",
            "sources": [s.model_dump() for s in sources],
            "mode": mode,
            "tier": resolved.tier,
            "demo_remaining": resolved.demo_remaining,
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"
        try:
            async for token in token_stream:
                payload = {"type": "token", "content": token}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("Chat stream failed")
            err = {"type": "token", "content": f"\n\n出错了：{exc}"}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/")
def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "UI not found. Put static files in /static"}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
