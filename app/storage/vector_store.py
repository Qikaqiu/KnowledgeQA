import hashlib
import json
import re
from pathlib import Path

import chromadb
from chromadb.config import Settings

from app.config import CHROMA_DIR, CHUNK_OVERLAP, CHUNK_SIZE, MIN_SECTION_SIZE, RECALL_TOP_K

HEADING_PARSE = re.compile(r"^(#{1,6})\s+(.+)$")


def _split_by_headings_with_paths(text: str) -> list[dict]:
  lines = text.split("\n")
  heading_stack: list[tuple[int, str]] = []
  sections: list[dict] = []
  current_lines: list[str] = []
  current_path = ""

  def flush() -> None:
    nonlocal current_lines, current_path
    if not current_lines:
      return
    block = "\n".join(current_lines).strip()
    if block:
      sections.append({"path": current_path, "text": block})
    current_lines = []

  for line in lines:
    match = HEADING_PARSE.match(line)
    if match:
      flush()
      level = len(match.group(1))
      title = match.group(2).strip()
      while heading_stack and heading_stack[-1][0] >= level:
        heading_stack.pop()
      heading_stack.append((level, title))
      current_path = " > ".join(item[1] for item in heading_stack)
      current_lines = [line]
    else:
      current_lines.append(line)

  flush()
  return sections if sections else [{"path": "", "text": text}]


def _merge_small_sections(sections: list[dict], min_size: int) -> list[dict]:
  if not sections:
    return []
  if len(sections) == 1:
    return sections

  merged: list[dict] = []
  buffer = sections[0]

  for section in sections[1:]:
    if len(buffer["text"]) < min_size:
      paths = [p for p in (buffer["path"], section["path"]) if p]
      buffer = {
        "path": " > ".join(paths) if paths else "",
        "text": f"{buffer['text']}\n\n{section['text']}",
      }
    else:
      merged.append(buffer)
      buffer = section

  merged.append(buffer)
  return merged


def _split_section_by_size(section: dict, chunk_size: int, overlap: int) -> list[dict]:
  text = section["text"].strip()
  path = section["path"]
  if not text:
    return []
  if len(text) <= chunk_size:
    return [{"path": path, "text": text}]

  parts = _split_by_size(text, chunk_size, overlap)
  return [{"path": path, "text": part} for part in parts]


def _split_by_size(text: str, chunk_size: int, overlap: int) -> list[str]:
  text = text.strip()
  if not text:
    return []
  if len(text) <= chunk_size:
    return [text]

  chunks: list[str] = []
  start = 0
  while start < len(text):
    end = min(start + chunk_size, len(text))
    chunk = text[start:end].strip()
    if chunk:
      chunks.append(chunk)
    if end >= len(text):
      break
    start = max(end - overlap, start + 1)
  return chunks


class VectorStore:
  def __init__(self) -> None:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    self.client = chromadb.PersistentClient(
      path=str(CHROMA_DIR),
      settings=Settings(anonymized_telemetry=False),
    )

  def _collection_name(self, workspace_id: str) -> str:
    return f"ws_{workspace_id}"

  def _collection(self, workspace_id: str):
    return self.client.get_or_create_collection(
      name=self._collection_name(workspace_id),
      metadata={"hnsw:space": "cosine"},
    )

  @staticmethod
  def build_chunk_records(text: str) -> list[dict]:
    text = text.replace("\r\n", "\n").strip()
    if not text:
      return []

    sections = _merge_small_sections(_split_by_headings_with_paths(text), MIN_SECTION_SIZE)
    records: list[dict] = []
    for section in sections:
      for part in _split_section_by_size(section, CHUNK_SIZE, CHUNK_OVERLAP):
        records.append(
          {
            "body": part["text"],
            "heading_path": part["path"],
            "summary": "",
            "embed_text": "",
          }
        )
    return records

  @staticmethod
  def chunk_text(text: str) -> list[str]:
    return [record["body"] for record in VectorStore.build_chunk_records(text)]

  def add_document(
    self,
    workspace_id: str,
    document_id: str,
    filename: str,
    chunk_records: list[dict],
    embeddings: list[list[float]],
  ) -> int:
    if not chunk_records:
      return 0
    if len(embeddings) != len(chunk_records):
      raise ValueError("Embedding count does not match chunk count")

    collection = self._collection(workspace_id)
    ids = [f"{document_id}_{i}" for i in range(len(chunk_records))]
    documents = [record["body"] for record in chunk_records]
    metadatas = [
      {
        "document_id": document_id,
        "filename": filename,
        "chunk_index": i,
        "heading_path": record.get("heading_path", ""),
        "summary": record.get("summary", ""),
      }
      for i, record in enumerate(chunk_records)
    ]
    collection.upsert(
      ids=ids,
      documents=documents,
      embeddings=embeddings,
      metadatas=metadatas,
    )
    return len(chunk_records)

  def delete_workspace(self, workspace_id: str) -> None:
    name = self._collection_name(workspace_id)
    try:
      self.client.delete_collection(name)
    except Exception:
      pass

  def delete_document(self, workspace_id: str, document_id: str) -> None:
    collection = self._collection(workspace_id)
    existing = collection.get(where={"document_id": document_id})
    if existing["ids"]:
      collection.delete(ids=existing["ids"])

  def _document_filter(self, document_ids: list[str] | None) -> dict | None:
    if not document_ids:
      return None
    unique_ids = list(dict.fromkeys(document_ids))
    if len(unique_ids) == 1:
      return {"document_id": unique_ids[0]}
    return {"document_id": {"$in": unique_ids}}

  def query(
    self,
    workspace_id: str,
    query_embedding: list[float],
    top_k: int = RECALL_TOP_K,
    document_ids: list[str] | None = None,
  ) -> list[dict]:
    collection = self._collection(workspace_id)
    if collection.count() == 0:
      return []

    where = self._document_filter(document_ids)
    if where:
      filtered = collection.get(where=where, include=[])
      available = len(filtered.get("ids", []))
      if available == 0:
        return []
      n_results = min(top_k, available)
    else:
      n_results = min(top_k, collection.count())

    query_kwargs: dict = {
      "query_embeddings": [query_embedding],
      "n_results": n_results,
      "include": ["documents", "metadatas", "distances"],
    }
    if where:
      query_kwargs["where"] = where

    result = collection.query(**query_kwargs)

    hits: list[dict] = []
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, distances):
      distance = float(dist)
      hits.append(
        {
          "document": meta.get("filename", "unknown"),
          "snippet": doc,
          "distance": distance,
          "score": round(max(0.0, 1.0 - distance), 4),
          "document_id": meta.get("document_id"),
          "chunk_index": meta.get("chunk_index", 0),
          "heading_path": meta.get("heading_path", ""),
          "summary": meta.get("summary", ""),
        }
      )
    return hits

  def keyword_search(
    self,
    workspace_id: str,
    question: str,
    top_k: int = RECALL_TOP_K,
    document_ids: list[str] | None = None,
  ) -> list[dict]:
    from app.services.relevance import keyword_retrieval_score

    collection = self._collection(workspace_id)
    if collection.count() == 0:
      return []

    where = self._document_filter(document_ids)
    kwargs: dict = {"include": ["documents", "metadatas"]}
    if where:
      kwargs["where"] = where
    result = collection.get(**kwargs)

    hits: list[dict] = []
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    for doc, meta in zip(documents, metadatas):
      text = f"{meta.get('heading_path', '')} {meta.get('summary', '')} {doc}"
      keyword = keyword_retrieval_score(question, text)
      hits.append(
        {
          "document": meta.get("filename", "unknown"),
          "snippet": doc,
          "distance": max(0.0, 1.0 - keyword),
          "score": keyword,
          "document_id": meta.get("document_id"),
          "chunk_index": meta.get("chunk_index", 0),
          "heading_path": meta.get("heading_path", ""),
          "summary": meta.get("summary", ""),
          "keyword_score": keyword,
          "semantic_score": 0.0,
        }
      )
    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[:top_k]

  def list_document_chunks(self, workspace_id: str, document_id: str) -> list[dict]:
    collection = self._collection(workspace_id)
    result = collection.get(
      where={"document_id": document_id},
      include=["documents", "metadatas"],
    )
    chunks: list[dict] = []
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    for text, meta in zip(documents, metadatas):
      chunk_index = int(meta.get("chunk_index") or 0)
      chunks.append(
        {
          "chunk_index": chunk_index,
          "char_count": len(text),
          "text": text,
          "filename": meta.get("filename", "unknown"),
          "heading_path": meta.get("heading_path", ""),
          "summary": meta.get("summary", ""),
        }
      )
    chunks.sort(key=lambda item: item["chunk_index"])
    return chunks


vector_store = VectorStore()


def documents_meta_path(workspace_id: str) -> Path:
  from app.config import DATA_DIR

  path = DATA_DIR / "documents" / workspace_id
  path.mkdir(parents=True, exist_ok=True)
  return path / "index.json"


def load_documents(workspace_id: str) -> list[dict]:
  path = documents_meta_path(workspace_id)
  if not path.exists():
    return []
  return json.loads(path.read_text(encoding="utf-8"))


def save_documents(workspace_id: str, docs: list[dict]) -> None:
  path = documents_meta_path(workspace_id)
  path.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")


def add_document_meta(workspace_id: str, meta: dict) -> None:
  docs = load_documents(workspace_id)
  docs.append(meta)
  save_documents(workspace_id, docs)


def update_document_meta(workspace_id: str, document_id: str, patch: dict) -> dict | None:
  docs = load_documents(workspace_id)
  updated = None
  for doc in docs:
    if doc["id"] == document_id:
      doc.update(patch)
      updated = doc
      break
  if updated:
    save_documents(workspace_id, docs)
  return updated


def remove_document_meta(workspace_id: str, document_id: str) -> dict | None:
  docs = load_documents(workspace_id)
  kept: list[dict] = []
  removed = None
  for doc in docs:
    if doc["id"] == document_id:
      removed = doc
    else:
      kept.append(doc)
  save_documents(workspace_id, kept)
  return removed


def file_hash(content: bytes) -> str:
  return hashlib.sha256(content).hexdigest()[:16]
