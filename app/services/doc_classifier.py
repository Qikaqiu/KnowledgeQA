import re


CHAPTER_PATTERNS = [
    re.compile(r"第[一二三四五六七八九十百千零\d]+[章节回幕]"),
    re.compile(r"Chapter\s+\d+", re.IGNORECASE),
    re.compile(r"CHAPTER\s+\d+"),
]

ACADEMIC_PATTERNS = [
    re.compile(r"(摘要|摘\s*要)"),
    re.compile(r"(Abstract)"),
    re.compile(r"(引言|绪论)"),
    re.compile(r"(Introduction)"),
    re.compile(r"(方法|实验|实验方法|Method)"),
    re.compile(r"(结果与分析|Results)"),
    re.compile(r"(结论|Conclusion)"),
    re.compile(r"(参考文献|References?)"),
]


def detect_doc_type(text: str, filename: str = "") -> str:
    """检测文档类型：novel / paper / manual / short

    纯规则检测，不调 LLM，毫秒级完成。
    """
    if len(text) < 800:
        return "short"

    for pat in CHAPTER_PATTERNS:
        if pat.search(text):
            return "novel"

    academic_hits = sum(1 for pat in ACADEMIC_PATTERNS if pat.search(text[:3000]))
    if academic_hits >= 3:
        return "paper"

    heading_count = len(re.findall(r"^#{1,6}\s+", text, re.MULTILINE))
    if heading_count >= 5:
        return "manual"

    if len(text) < 2000:
        return "short"

    return "manual"
