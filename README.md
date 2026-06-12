# KnowledgeQA · 私人知识问答库

借鉴 [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) 的多资料库体验，用 **Python + FastAPI + ChromaDB + BGE** 实现的轻量 RAG 问答应用。

## 功能

- 多资料库隔离，文档上传后自动分块、向量化
- 中文检索： [FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding) / `BAAI/bge-small-zh-v1.5`
- 流式问答 + 引用来源 + 检索预览
- 三种运行模式：完整模式（用户自带 Key）/ 演示模式（服务端 Key）/ 检索模式
- 支持 TXT、Markdown、PDF、Word、PPT、Excel 等（[MarkItDown](https://github.com/microsoft/markitdown)）

## 快速开始

```bash
git clone <your-repo-url>
cd KnowledgeQA   # 或你的仓库目录名

python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Linux/macOS: cp .env.example .env
# 编辑 .env，至少可配置 DEMO_API_KEY 开启演示模式

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Windows 也可直接运行 `run.bat`。

浏览器打开：http://127.0.0.1:8000

首次启动会自动下载 BGE 嵌入模型，并从 `sample_docs/` 导入演示文档。

## 配置说明

复制 `.env.example` 为 `.env`，**切勿将 `.env` 提交到 Git**。

| 变量 | 说明 |
|------|------|
| `DEMO_API_KEY` | 演示模式用 Key（公开发布时在服务器配置） |
| `DEMO_DAILY_LIMIT` | 每 IP 每日提问次数 |
| `OPENAI_API_KEY` | 仅 `USE_SERVER_API_KEY=true` 时对所有访客生效 |
| `EMBEDDING_MODEL` | 默认 `BAAI/bge-small-zh-v1.5` |
| `ALLOW_ENV_KEY_WRITE` | 公开发布建议 `false` |

用户自己的 API Key 保存在浏览器 `localStorage`，不经由仓库或服务端 `.env` 分发。

## 运行模式

| 模式 | 触发条件 |
|------|----------|
| 完整模式 | 用户在界面配置 API Key |
| 演示模式 | 服务端配置 `DEMO_API_KEY` |
| 检索模式 | 无 Key 且 Ollama 不可用 |

## 项目结构

```
├── app/                 # FastAPI 后端
│   ├── main.py
│   ├── config.py
│   ├── services/        # RAG、嵌入、LLM、演示种子等
│   └── storage/         # ChromaDB、资料库元数据
├── static/              # 单页前端
├── sample_docs/         # 演示示例文档（启动时同步）
├── data/                # 运行时数据（Git 忽略）
├── requirements.txt
├── .env.example
└── run.bat
```

## 演示资料库

| 资料库 | 示例问题 |
|--------|----------|
| 技术文档 | 这个项目用了哪些技术？ / 系统使用什么向量数据库？ |
| 产品手册 | 系统有哪几种运行模式？ |
| 使用规范 | 演示模式有什么限制？ |

## 部署提示

1. 生产环境去掉 `--reload`，前置 Nginx 做 HTTPS
2. 定期备份 `data/` 目录
3. `.env` 仅在服务器本地维护，通过 SCP / 密钥管理服务单独上传
4. 公开站点设置 `ALLOW_ENV_KEY_WRITE=false`、`USE_SERVER_API_KEY=false`

## 技术栈

- **后端**：FastAPI、Uvicorn、httpx、aiofiles
- **向量库**：ChromaDB（本地持久化）
- **嵌入**：FlagEmbedding · BGE 中文 v1.5
- **LLM**：OpenAI 兼容 API / Ollama / 检索摘要

## License

MIT — 见 [LICENSE](LICENSE)

## 参考

- [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm)
- [FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding)
- [MarkItDown](https://github.com/microsoft/markitdown)
