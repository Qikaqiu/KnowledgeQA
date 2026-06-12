"""演示模式：示例资料库与默认提问。"""

from pathlib import Path

from app.config import BASE_DIR
from app.services.document_parser import SUPPORTED_SUFFIXES
from app.services.ingest import ingest_file_sync
from app.storage import vector_store as vs
from app.storage.workspaces import get_workspace, list_workspaces
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_demo_workspaces() -> None:
    """确保演示用资料库存在（不删除用户自建资料库）。"""
    from app.config import WORKSPACES_FILE
    import json

    defaults = [
        ("ws_tech", "技术文档", "技术栈、RAG 流程与部署指南"),
        ("ws_product", "产品手册", "产品能力、运行模式与常见问题"),
        ("ws_policy", "使用规范", "数据安全、演示限制与合规建议"),
    ]
    workspaces = list_workspaces()
    by_id = {ws["id"]: ws for ws in workspaces}
    changed = False
    for ws_id, name, desc in defaults:
        existing = by_id.get(ws_id)
        if existing:
            if existing.get("name") != name or existing.get("description") != desc:
                existing["name"] = name
                existing["description"] = desc
                changed = True
            continue
        workspaces.append(
            {
                "id": ws_id,
                "name": name,
                "description": desc,
                "created_at": _now(),
                "document_count": 0,
            }
        )
        changed = True
    if changed:
        WORKSPACES_FILE.parent.mkdir(parents=True, exist_ok=True)
        WORKSPACES_FILE.write_text(
            json.dumps(workspaces, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

SAMPLE_ROOT = BASE_DIR / "sample_docs"
DEMO_WORKSPACE_IDS = frozenset({"ws_tech", "ws_product", "ws_policy"})

DEMO_CATALOG = {
    "default_workspace_id": "ws_tech",
    "prompts": [
        {
            "workspace_id": "ws_tech",
            "label": "技术栈",
            "question": "这个项目用了哪些技术？",
        },
        {
            "workspace_id": "ws_tech",
            "label": "向量数据库",
            "question": "系统使用什么向量数据库？",
        },
        {
            "workspace_id": "ws_product",
            "label": "运行模式",
            "question": "系统有哪几种运行模式？",
        },
        {
            "workspace_id": "ws_policy",
            "label": "演示限制",
            "question": "演示模式有什么限制？",
        },
    ],
}

async def seed_from_sample_dirs() -> int:
    """从 sample_docs 同步示例文档（新增或内容变更时自动重新导入）。"""
    if not SAMPLE_ROOT.exists():
        return 0

    from app.services.ingest import delete_document

    imported = 0
    for ws in list_workspaces():
        ws_id = ws["id"]
        ws_dir = SAMPLE_ROOT / ws_id
        if not ws_dir.exists():
            continue

        sample_files = sorted(
            path
            for path in ws_dir.glob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        )
        sample_names = {path.name for path in sample_files}
        documents = vs.load_documents(ws_id)

        if ws_id in DEMO_WORKSPACE_IDS:
            for doc in list(documents):
                if doc["filename"] not in sample_names:
                    await delete_document(ws_id, doc["id"])
            documents = vs.load_documents(ws_id)

        for file_path in sample_files:
            content = file_path.read_bytes()
            content_hash = vs.file_hash(content)
            matches = [doc for doc in documents if doc["filename"] == file_path.name]
            if len(matches) == 1 and matches[0].get("hash") == content_hash:
                continue
            for doc in matches:
                await delete_document(ws_id, doc["id"])
            await ingest_file_sync(ws_id, file_path.name, content)
            imported += 1
            documents = vs.load_documents(ws_id)
    return imported


async def ensure_demo_data() -> dict:
    ensure_demo_workspaces()
    from_disk = await seed_from_sample_dirs()
    default_ws = DEMO_CATALOG["default_workspace_id"]
    doc_count = 0
    if get_workspace(default_ws):
        doc_count = len(vs.load_documents(default_ws))
    default_question = next(
        (p["question"] for p in DEMO_CATALOG["prompts"] if p["workspace_id"] == default_ws),
        "系统使用什么向量数据库？",
    )
    return {
        "imported": from_disk,
        "default_workspace_id": default_ws,
        "default_question": default_question,
        "catalog": DEMO_CATALOG,
        "document_count": doc_count,
    }


def get_demo_catalog() -> dict:
    return DEMO_CATALOG
