from functools import lru_cache
from io import BytesIO
from pathlib import Path

from markitdown import MarkItDown

PLAIN_TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
MARKITDOWN_SUFFIXES = {
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".xlsx",
    ".xls",
    ".html",
    ".htm",
    ".csv",
    ".json",
    ".xml",
}

SUPPORTED_SUFFIXES = PLAIN_TEXT_SUFFIXES | MARKITDOWN_SUFFIXES

SUPPORTED_FORMATS_LABEL = (
    "TXT, MD, PDF, Word(.docx), PowerPoint(.pptx), Excel(.xlsx), HTML, CSV, JSON, XML"
)


@lru_cache(maxsize=1)
def _get_markitdown() -> MarkItDown:
    return MarkItDown(enable_plugins=False)


def is_supported(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_SUFFIXES


def parse_file(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"不支持的文件类型: {suffix or '(无扩展名)'}。"
            f"支持: {SUPPORTED_FORMATS_LABEL}"
        )

    if suffix in PLAIN_TEXT_SUFFIXES:
        text = _decode_text(content)
    else:
        text = _convert_with_markitdown(content, suffix, filename)

    if not text.strip():
        raise ValueError(f"文件 {filename} 中没有可提取的文本内容")
    return text


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _convert_with_markitdown(content: bytes, suffix: str, filename: str) -> str:
    md = _get_markitdown()
    try:
        result = md.convert_stream(BytesIO(content), file_extension=suffix)
    except Exception as exc:
        raise ValueError(f"无法解析文件 {filename}: {exc}") from exc

    text = (result.markdown or result.text_content or "").strip()
    if not text:
        raise ValueError(f"文件 {filename} 中没有可提取的文本内容")
    return text
