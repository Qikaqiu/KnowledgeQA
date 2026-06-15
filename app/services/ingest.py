import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles

from app.config import UPLOAD_DIR
from app.services.chunk_enricher import enrich_chunks
from app.services.doc_classifier import detect_doc_type
from app.services.document_parser import parse_file
from app.services.embedder import embed_texts
from app.storage import vector_store as vs
from app.storage.workspaces import list_workspaces, update_document_count

logger = logging.getLogger(__name__)

INGEST_TIMEOUT_SECONDS = 900
_ingest_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _save_upload_file(
    workspace_id: str, document_id: str, filename: str, content: bytes
) -> Path:
    upload_dir = UPLOAD_DIR / workspace_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{document_id}_{Path(filename).name}"
    file_path = upload_dir / safe_name
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    return file_path


async def _process_document(
    workspace_id: str, document_id: str, filename: str, content: bytes
) -> tuple[int, str]:
    text = await asyncio.to_thread(parse_file, filename, content)
    if not text.strip():
        raise ValueError("文件中没有可提取的文本内容")

    doc_type = detect_doc_type(text, filename)
    chunk_records = vs.vector_store.build_chunk_records(text, doc_type)
    if not chunk_records:
        raise ValueError("文件中没有可提取的文本内容")

    await enrich_chunks(chunk_records)
    embeddings = await asyncio.to_thread(
        embed_texts, [record["embed_text"] for record in chunk_records]
    )
    count = vs.vector_store.add_document(
        workspace_id, document_id, filename, chunk_records, embeddings, doc_type
    )
    return count, doc_type


async def _finish_ingest_worker(
    workspace_id: str, document_id: str, filename: str, content: bytes
) -> None:
    async with _ingest_lock:
        try:
            chunk_count, doc_type = await asyncio.wait_for(
                _process_document(workspace_id, document_id, filename, content),
                timeout=INGEST_TIMEOUT_SECONDS,
            )
            vs.update_document_meta(
                workspace_id,
                document_id,
                {"status": "ready", "chunk_count": chunk_count, "doc_type": doc_type, "error_message": ""},
            )
        except Exception as exc:
            logger.exception("Background ingest failed for %s/%s", workspace_id, document_id)
            vs.vector_store.delete_document(workspace_id, document_id)
            message = str(exc)
            if isinstance(exc, asyncio.TimeoutError):
                message = "向量化超时，请稍后重试或换更小文件"
            vs.update_document_meta(
                workspace_id,
                document_id,
                {
                    "status": "error",
                    "chunk_count": 0,
                    "error_message": message,
                },
            )


async def recover_processing_documents() -> None:
    """重启后恢复卡在 processing 的文档。"""
    for workspace in list_workspaces():
        workspace_id = workspace["id"]
        for doc in list(vs.load_documents(workspace_id)):
            if doc.get("status") != "processing":
                continue
            path = Path(doc.get("stored_path", ""))
            if not path.exists():
                vs.update_document_meta(
                    workspace_id,
                    doc["id"],
                    {
                        "status": "error",
                        "chunk_count": 0,
                        "error_message": "原始文件丢失，请重新上传",
                    },
                )
                continue
            content = path.read_bytes()
            logger.info("Recovering processing document %s/%s", workspace_id, doc["id"])
            await _finish_ingest_worker(workspace_id, doc["id"], doc["filename"], content)


async def ingest_file_sync(workspace_id: str, filename: str, content: bytes) -> dict:
    """同步入库（示例文档种子、重建索引等内部流程使用）。"""
    document_id = uuid.uuid4().hex[:12]
    file_path = await _save_upload_file(workspace_id, document_id, filename, content)
    async with _ingest_lock:
        chunk_count, doc_type = await _process_document(workspace_id, document_id, filename, content)

    meta = {
        "id": document_id,
        "filename": filename,
        "size": len(content),
        "uploaded_at": _now(),
        "chunk_count": chunk_count,
        "doc_type": doc_type,
        "stored_path": str(file_path),
        "hash": vs.file_hash(content),
        "status": "ready",
    }
    vs.add_document_meta(workspace_id, meta)
    update_document_count(workspace_id, 1)
    return meta


async def ingest_file(workspace_id: str, filename: str, content: bytes) -> dict:
    """用户上传：先落盘并立即返回，向量化在后台执行。"""
    document_id = uuid.uuid4().hex[:12]
    file_path = await _save_upload_file(workspace_id, document_id, filename, content)

    meta = {
        "id": document_id,
        "filename": filename,
        "size": len(content),
        "uploaded_at": _now(),
        "chunk_count": 0,
        "stored_path": str(file_path),
        "hash": vs.file_hash(content),
        "status": "processing",
    }
    vs.add_document_meta(workspace_id, meta)
    update_document_count(workspace_id, 1)
    asyncio.create_task(
        _finish_ingest_worker(workspace_id, document_id, filename, content)
    )
    return meta


async def delete_document(workspace_id: str, document_id: str) -> bool:
    removed = vs.remove_document_meta(workspace_id, document_id)
    if not removed:
        return False
    vs.vector_store.delete_document(workspace_id, document_id)
    stored = removed.get("stored_path")
    if stored:
        path = Path(stored)
        if path.exists():
            path.unlink()
    update_document_count(workspace_id, -1)
    return True
