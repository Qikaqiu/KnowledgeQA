# 部署与运行指南

## 环境要求

- Python 3.10+
- Windows / macOS / Linux 均可
- 建议内存 4GB 以上（首次加载 BGE 嵌入模型需额外占用）
- 可选：NVIDIA GPU（加速 Embedding；无 GPU 时使用 CPU）
- 可选：本地 Ollama（检索模式之外的离线 LLM）

## 快速启动

```powershell
cd d:\test\LLM
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env，至少可配置 DEMO_API_KEY 以开启演示模式
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

也可直接双击 `run.bat`（Windows）。

浏览器访问：http://127.0.0.1:8000

## 目录说明

```
LLM/
├── app/              # 后端代码
├── static/           # 前端静态页
├── sample_docs/      # 演示用示例文档（启动时自动导入）
├── data/             # 运行时数据（勿提交 Git）
├── .env              # 本地配置（勿提交 Git）
└── requirements.txt
```

## .env 常用配置

### 演示模式（公开发布推荐）

```
DEMO_API_KEY=sk-xxx          # 服务端演示 Key
DEMO_BASE_URL=https://api.deepseek.com/v1
DEMO_MODEL=deepseek-chat
DEMO_DAILY_LIMIT=10          # 每 IP 每日次数
DEMO_PER_MINUTE_LIMIT=2      # 每分钟次数
DEMO_MAX_CHARS=500           # 单次提问字数上限
```

### 嵌入模型

```
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_QUERY_INSTRUCTION=为这个句子生成表示以用于检索相关文章：
```

可升级为 `BAAI/bge-base-zh-v1.5` 或 `bge-large-zh-v1.5`，修改后重启会自动重建向量索引。

### 自托管完整模式（可选）

```
USE_SERVER_API_KEY=false     # 公开发布请保持 false
OPENAI_API_KEY=              # 仅 USE_SERVER_API_KEY=true 时对所有访客生效
```

用户自己的 Key 保存在浏览器 `localStorage`，不经由服务端 `.env`。

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/workspaces | 资料库列表 |
| POST | /api/workspaces | 创建资料库 |
| POST | /api/workspaces/{id}/documents | 上传文档 |
| POST | /api/workspaces/{id}/chat/stream | 流式问答 |
| POST | /api/workspaces/{id}/retrieve | 检索预览 |
| GET | /api/mode | 当前运行模式与演示目录 |
| POST | /api/demo/ensure | 补全演示资料库与示例文档 |

## 生产部署建议

1. 去掉 `--reload`，使用多 worker 或进程管理器（如 systemd、Docker）
2. 前置 Nginx 做 HTTPS 与静态资源缓存
3. 定期备份 `data/` 目录
4. 切勿将 `.env` 中的真实 API Key 提交到 Git
5. 公开站点设置 `ALLOW_ENV_KEY_WRITE=false`

## 故障排查

- **端口占用**：Windows 上 `netstat -ano | findstr 8000` 查进程并结束
- **问答无结果**：检查资料库是否有文档；试用「检索预览」查看分数；换更具体的问法
- **换嵌入模型后检索异常**：确认 `data/embedding_meta.json` 已更新，必要时删除 `data/chroma/` 后重启
