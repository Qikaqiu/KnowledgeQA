# KnowledgeQA 技术栈总览

KnowledgeQA（私人知识问答库）是一个轻量级 RAG 应用，借鉴 AnythingLLM 的多资料库体验，使用 Python 技术栈在本地即可运行。

## 后端

- **Web 框架**：FastAPI，提供 REST API 与 SSE 流式聊天接口
- **ASGI 服务器**：Uvicorn（开发环境可用 `--reload` 热重载）
- **HTTP 客户端**：httpx，用于调用 OpenAI 兼容 API 与 Ollama
- **异步文件 IO**：aiofiles

## 向量检索

- **向量数据库**：ChromaDB，本地持久化，数据目录为 `data/chroma/`
- **隔离策略**：每个资料库（workspace）对应独立的 Chroma collection，命名格式 `ws_{id}`
- **相似度**：余弦距离（cosine），向量已 L2 归一化

## 嵌入模型（Embedding）

- **框架**：[FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding)（BGE 系列）
- **默认模型**：`BAAI/bge-small-zh-v1.5`（中文检索优化）
- **问句编码**：`encode_queries`，自动附加检索指令「为这个句子生成表示以用于检索相关文章：」
- **文档编码**：`encode_corpus`，不加指令
- **配置项**：`.env` 中的 `EMBEDDING_MODEL`、`EMBEDDING_QUERY_INSTRUCTION`
- **模型切换**：启动时检测 `data/embedding_meta.json`，若模型变更则自动从已上传文件重建向量

## 大语言模型（LLM）

支持三种运行层级，按优先级解析：

1. **完整模式**：用户在浏览器配置 API Key（`localStorage`），通过请求头 `X-User-Api-Key` 传入
2. **演示模式**：服务端配置 `DEMO_API_KEY`，访客免费试用（有每日/每分钟次数与字数限制）
3. **检索模式**：无可用 Key 时，仅根据检索片段生成摘要式回答

可选接入：OpenAI 兼容 API（含 DeepSeek）、本地 Ollama。

## 文档解析

- **库**：Microsoft MarkItDown
- **支持格式**：TXT、Markdown、PDF、Word、PPT、Excel 等（转为文本后入库）
- **分块参数**：默认 800 字符/块，重叠 120 字符；按 Markdown 标题切分后再合并过小段落

## 前端

- **形态**：单页应用，静态文件位于 `static/`（`index.html`、`app.js`、`style.css`）
- **无独立前端构建**：纯 HTML + 原生 JavaScript
- **模式 UI**：演示配额条、欢迎引导、API Key 本地保存、检索预览

## 数据持久化

| 数据 | 存储位置 |
|------|----------|
| 资料库元数据 | `data/workspaces.json` |
| 文档索引 | `data/documents/{workspace_id}/index.json` |
| 原始上传文件 | `data/uploads/{workspace_id}/` |
| 向量 | `data/chroma/` |
| 演示配额 | `data/demo_quotas.json` |

## 主要依赖（requirements.txt）

```
fastapi, uvicorn, chromadb, FlagEmbedding, markitdown, httpx, aiofiles, python-dotenv
```
