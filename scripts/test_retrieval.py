import asyncio

from app.services.app_mode import TIER_DEMO, ResolvedMode
from app.services.rag import filter_relevant_hits, is_relevant, retrieve_hits
from app.services.relevance import keyword_overlap_score

DEMO = ResolvedMode(
    tier=TIER_DEMO,
    credentials=None,
    provider_label="demo",
    features={},
)


async def test(ws: str, q: str) -> None:
    hits = await retrieve_hits(ws, q, resolved=DEMO)
    tier = DEMO.tier
    print(f"=== {ws}: {q} ===")
    for h in hits[:3]:
        print(
            f"  score={h['score']} sem={h.get('semantic_score')} "
            f"kw={h.get('keyword_score')} doc={h.get('document')}"
        )
        print(f"    snippet={h['snippet'][:100]}")
    print(
        f"  is_relevant={is_relevant(hits, tier)} "
        f"filter={len(filter_relevant_hits(hits, tier))}"
    )
    print()


def test_kw(q: str, text: str) -> None:
    print(f"kw({q!r}, ...) = {keyword_overlap_score(q, text)}")


async def main() -> None:
    test_kw(
        "系统使用什么向量数据库？",
        "默认使用 ChromaDB 本地持久化，每个资料库对应独立 collection。",
    )
    test_kw(
        "专业版定价多少",
        "## 定价\n- 专业版：99 元/月",
    )
    await test("ws_tech", "系统使用什么向量数据库？")
    await test("ws_product", "专业版定价多少")
    await test("ws_product", "专业版定价是多少？")


if __name__ == "__main__":
    asyncio.run(main())
