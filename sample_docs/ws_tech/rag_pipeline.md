# RAG 检索与问答流程

本文说明 KnowledgeQA 从用户提问到生成回答的完整链路。

## 1. 文档入库（Ingest）

1. 用户上传文件 → `document_parser` 解析为纯文本
2. `vector_store.build_chunk_records` 按标题与长度分块
3. `chunk_enricher` 为每块生成摘要与 `embed_text`（用于向量化的拼接文本）
4. `embedder.embed_texts` 调用 BGE `encode_corpus` 得到向量
5. 向量与元数据写入 ChromaDB，原文保存到 `data/uploads/`

## 2. 检索（Retrieve）

用户发送问题后：

1. `embed_query` 对问题调用 BGE `encode_queries`（带中文检索指令）
2. ChromaDB 在**当前资料库**内做 Top-K 召回（默认 `RECALL_TOP_K = 12`）
3. 若用户勾选了特定文件，则只在对应 `document_id` 范围内检索
4. 对每个命中片段计算**综合相关度**：
   - 语义分：由向量余弦距离换算（约 `1 - distance`）
   - 关键词分：中文 n-gram 与问句归一化匹配（弥补纯向量对中文问法不敏感）
   - 综合分 = 70% 语义 + 30% 关键词，命中明显关键词时额外加成

## 3. 相关度过滤

- **完整/检索模式**阈值：38%（`MIN_RELEVANCE_SCORE = 0.38`）
- **演示模式**阈值：28%，且关键词命中较好时可放宽
- 低于阈值时返回「未找到足够相关资料」，并提示最高相关度与阈值

## 4. 重排序（Rerank）

- **完整模式 + 有 API Key**：可用 LLM 对召回片段打分重排（`reranker.py`）
- **演示模式 / 检索模式**：按向量综合分排序，取 Top-6（`RERANK_TOP_K`）

## 5. 生成回答（Generate）

将过滤后的片段作为上下文，调用 LLM：

- **系统提示**：仅根据资料回答，必须标注引用编号（资料1、资料2…）
- **流式输出**：`POST /api/workspaces/{id}/chat/stream` 通过 SSE 逐 token 返回
- **来源展示**：响应中包含 `sources` 列表，前端展示引用片段与分数

## 6. 检索预览

演示模式与完整模式均支持「检索预览」接口，可查看命中片段、语义分、关键词分及是否过阈值，便于调试问法。

## 关键配置（config.py / .env）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| CHUNK_SIZE | 800 | 分块大小 |
| CHUNK_OVERLAP | 120 | 块间重叠 |
| RECALL_TOP_K | 12 | 向量召回数 |
| RERANK_TOP_K | 6 | 送入 LLM 的片段数 |
| MIN_RELEVANCE_SCORE | 0.38 | 相关度阈值 |
| DEMO_MIN_RELEVANCE_SCORE | 0.28 | 演示模式阈值 |
