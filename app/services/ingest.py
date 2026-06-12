import asyncio
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def ingest_file(workspace_id: str, filename: str, content: bytes) -> dict:
    text = await asyncio.to_thread(parse_file, filename, content)
    if not text.strip():
        raise ValueError("文件中没有可提取的文本内容")

    document_id = uuid.uuid4().hex[:12]
    chunk_records = vs.vector_store.build_chunk_records(text)
    if not chunk_records:
        raise ValueError("文件中没有可提取的文本内容")

    await enrich_chunks(chunk_records)
    embeddings = embed_texts([record["embed_text"] for record in chunk_records])
    chunk_count = vs.vector_store.add_document(
        workspace_id, document_id, filename, chunk_records, embeddings
    )

    upload_dir = UPLOAD_DIR / workspace_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{document_id}_{Path(filename).name}"
    file_path = upload_dir / safe_name
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    meta = {
        "id": document_id,
        "filename": filename,
        "size": len(content),
        "uploaded_at": _now(),
        "chunk_count": chunk_count,
        "stored_path": str(file_path),
        "hash": vs.file_hash(content),
    }
    vs.add_document_meta(workspace_id, meta)
    update_document_count(workspace_id, 1)
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
