import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles

from app.config import UPLOAD_DIR
from app.services.chunk_enricher import enrich_chunks
from app.services.document_parser import parse_file
from app.services.embedder import embed_texts
from app.storage import vector_store as vs
from app.storage.workspaces import update_document_count

logger = logging.getLogger(__name__)


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
) -> int:
    text = await asyncio.to_thread(parse_file, filename, content)
    if not text.strip():
        raise ValueError("文件中没有可提取的文本内容")

    chunk_records = vs.vector_store.build_chunk_records(text)
    if not chunk_records:
        raise ValueError("文件中没有可提取的文本内容")

    await enrich_chunks(chunk_records)
    embeddings = await asyncio.to_thread(
        embed_texts, [record["embed_text"] for record in chunk_records]
    )
    return vs.vector_store.add_document(
        workspace_id, document_id, filename, chunk_records, embeddings
    )


async def ingest_file_sync(workspace_id: str, filename: str, content: bytes) -> dict:
    """同步入库（示例文档种子、重建索引等内部流程使用）。"""
    document_id = uuid.uuid4().hex[:12]
    file_path = await _save_upload_file(workspace_id, document_id, filename, content)
    chunk_count = await _process_document(workspace_id, document_id, filename, content)

    meta = {
        "id": document_id,
        "filename": filename,
        "size": len(content),
        "uploaded_at": _now(),
        "chunk_count": chunk_count,
        "stored_path": str(file_path),
        "hash": vs.file_hash(content),
        "status": "ready",
    }
    vs.add_document_meta(workspace_id, meta)
    update_document_count(workspace_id, 1)
    return meta


async def ingest_file(workspace_id: str, filename: str, content: bytes) -> dict:
    """用户上传：先落盘并立即返回，向量化在后台执行，避免网关超时。"""
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
        _finish_ingest_background(workspace_id, document_id, filename, content)
    )
    return meta


async def _finish_ingest_background(
    workspace_id: str, document_id: str, filename: str, content: bytes
) -> None:
    try:
        chunk_count = await _process_document(
            workspace_id, document_id, filename, content
        )
        vs.update_document_meta(
            workspace_id,
            document_id,
            {"status": "ready", "chunk_count": chunk_count, "error_message": ""},
        )
    except Exception as exc:
        logger.exception("Background ingest failed for %s/%s", workspace_id, document_id)
        vs.vector_store.delete_document(workspace_id, document_id)
        vs.update_document_meta(
            workspace_id,
            document_id,
            {
                "status": "error",
                "chunk_count": 0,
                "error_message": str(exc),
            },
        )


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
