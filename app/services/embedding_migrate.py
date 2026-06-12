"""嵌入模型变更后，从已保存文件重建向量索引。"""

import asyncio
import json
from pathlib import Path

from app.config import DATA_DIR, EMBEDDING_MODEL, EMBEDDING_QUERY_INSTRUCTION
from app.services.chunk_enricher import enrich_chunks
from app.services.document_parser import parse_file
from app.services.embedder import clear_embedder_cache, embed_texts
from app.storage import vector_store as vs
from app.storage.workspaces import list_workspaces

EMBEDDING_META_FILE = DATA_DIR / "embedding_meta.json"


def _embedding_signature() -> dict[str, str]:
    return {
        "model": EMBEDDING_MODEL,
        "instruction": EMBEDDING_QUERY_INSTRUCTION,
    }


async def _reindex_document(workspace_id: str, doc: dict) -> None:
    path = Path(doc.get("stored_path", ""))
    if not path.exists():
        return
    content = path.read_bytes()
    text = await asyncio.to_thread(parse_file, doc["filename"], content)
    if not text.strip():
        return

    chunk_records = vs.vector_store.build_chunk_records(text)
    if not chunk_records:
        return

    await enrich_chunks(chunk_records)
    embeddings = await asyncio.to_thread(
        embed_texts, [record["embed_text"] for record in chunk_records]
    )
    vs.vector_store.add_document(
        workspace_id,
        doc["id"],
        doc["filename"],
        chunk_records,
        embeddings,
    )


async def ensure_embedding_index() -> bool:
    """若嵌入模型配置变更，清空并重建各资料库向量。返回是否执行了重建。"""
    signature = _embedding_signature()
    if EMBEDDING_META_FILE.exists():
        try:
            saved = json.loads(EMBEDDING_META_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            saved = {}
        if saved == signature:
            return False

    clear_embedder_cache()

    for workspace in list_workspaces():
        workspace_id = workspace["id"]
        documents = vs.load_documents(workspace_id)
        if not documents:
            continue
        vs.vector_store.delete_workspace(workspace_id)
        for doc in documents:
            await _reindex_document(workspace_id, doc)

    EMBEDDING_META_FILE.parent.mkdir(parents=True, exist_ok=True)
    EMBEDDING_META_FILE.write_text(
        json.dumps(signature, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return True
