import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATA_DIR, WORKSPACES_FILE

_workspaces_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> list[dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not WORKSPACES_FILE.exists():
        return []
    return json.loads(WORKSPACES_FILE.read_text(encoding="utf-8"))


def _save(workspaces: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACES_FILE.write_text(
        json.dumps(workspaces, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_workspaces() -> list[dict]:
    return _load()


def get_workspace(workspace_id: str) -> dict | None:
    for ws in _load():
        if ws["id"] == workspace_id:
            return ws
    return None


def create_workspace(name: str, description: str = "") -> dict:
    ws = {
        "id": uuid.uuid4().hex[:12],
        "name": name.strip(),
        "description": description.strip(),
        "created_at": _now(),
        "document_count": 0,
    }
    with _workspaces_lock:
        workspaces = _load()
        workspaces.append(ws)
        _save(workspaces)
    return ws


def update_workspace(
    workspace_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> dict | None:
    with _workspaces_lock:
        workspaces = _load()
        for ws in workspaces:
            if ws["id"] == workspace_id:
                if name is not None:
                    ws["name"] = name.strip()
                if description is not None:
                    ws["description"] = description.strip()
                _save(workspaces)
                return ws
    return None


def delete_workspace(workspace_id: str) -> bool:
    with _workspaces_lock:
        workspaces = _load()
        if not any(ws["id"] == workspace_id for ws in workspaces):
            return False

        from app.config import UPLOAD_DIR
        from app.storage import vector_store as vs
        import shutil

        for doc in vs.load_documents(workspace_id):
            stored = doc.get("stored_path")
            if stored:
                path = Path(stored)
                if path.exists():
                    path.unlink()

        docs_dir = DATA_DIR / "documents" / workspace_id
        if docs_dir.exists():
            shutil.rmtree(docs_dir, ignore_errors=True)

        upload_dir = UPLOAD_DIR / workspace_id
        if upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)

        vs.vector_store.delete_workspace(workspace_id)

        kept = [ws for ws in workspaces if ws["id"] != workspace_id]
        _save(kept)
    return True


def update_document_count(workspace_id: str, delta: int) -> None:
    with _workspaces_lock:
        workspaces = _load()
        for ws in workspaces:
            if ws["id"] == workspace_id:
                ws["document_count"] = max(0, ws.get("document_count", 0) + delta)
                break
        _save(workspaces)


def ensure_seed_workspaces() -> None:
    if _load():
        return
    defaults = [
        ("ws_product", "产品手册", "产品功能、定价与常见问题"),
        ("ws_tech", "技术文档", "架构设计、API 与部署说明"),
        ("ws_policy", "公司制度", "考勤、报销与信息安全规范"),
    ]
    workspaces = []
    for ws_id, name, desc in defaults:
        workspaces.append(
            {
                "id": ws_id,
                "name": name,
                "description": desc,
                "created_at": _now(),
                "document_count": 0,
            }
        )
    _save(workspaces)
