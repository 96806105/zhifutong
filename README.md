<p align="center">
  <img src="docs/logo.svg" width="96" alt="智服通 logo">
</p>

<h1 align="center">智服通 · 企业 IT 技术支持智能客服</h1>

<p align="center">
  基于 <b>FastAPI + GLM + RAG</b> 的可私有化部署企业智能客服系统<br>
  <b>本地向量检索 · 流式对话 · 自动转人工 · 全链路工程化</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/RAG-ChromaDB-6149cb?logo=chromadb" alt="RAG">
  <img src="https://img.shields.io/badge/LLM-GLM--4--Flash-blue" alt="LLM">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>

---

> **智服通** 是一个开箱即用的企业 IT 技术支持智能客服项目。它把 LLM 的对话能力
> 与**企业私有知识库的检索增强生成（RAG）**结合起来：员工可以像聊天一样提问
> 「如何重置密码 / WiFi 连不上 / 安装 Office」，机器人依据企业知识库流式作答，
> 并在解答不了时**自动转接人工**、生成工单。全程数据可私有化、可审计。

## ✨ 核心亮点

| 亮点 | 说明 |
|---|---|
| 🧠 **本地 RAG，检索不说谎** | 中文语义模型 `bge-small-zh-v1.5` 本地向量化，完全离线，零 API 额度；答案**强制溯源**，附知识库来源与置信度 |
| 🔀 **混合检索** | 向量余弦相似度 + 简化 BM25 关键词加权融合，双保险召回（评测 Top-3 命中 100%） |
| ⏱️ **SSE 流式对话** | 打字机式逐字输出，体验与主流大模型一致 |
| 🤝 **智能转人工** | 明确要求 / 负面情绪 / 敏感操作 / 连续 3 次低置信度 → 自动开单转人工，绝不硬答 |
| 🖥️ **Apple 风精致界面** | 液态玻璃设计语言，桌面 / 移动端自适应，管理台可视化运营 |
| 🔒 **企业级工程化** | 统一错误码、接口鉴权、IP 限流、请求日志、SQLite 事务、Docker 一键部署 |
| 🧪 **可评估可回归** | 内置检索质量离线评测脚本 + 15 项单元测试（pytest）+ ruff 静态检查 |

## 🧰 技术栈

- **后端**：Python 3.12+ / FastAPI / Uvicorn / SQLAlchemy + SQLite
- **RAG**：ChromaDB 向量库 / sentence-transformers（bge-small-zh-v1.5）/ 自研混合检索
- **LLM**：GLM-4-Flash（OpenAI 兼容，可无缝切换任意兼容模型）
- **前端**：原生 HTML/CSS/JS · Jinja2 服务端渲染（无构建依赖，开箱即用）

## 📦 快速开始

### 1. 环境要求

- Python 3.12+
- 一个 [智谱 AI](https://open.bigmodel.cn/) 的 API Key（可申请免费额度的 GLM-4-Flash）

### 2. 克隆与安装

```bash
git clone https://github.com/96806105/zhifutong.git
cd zhifutong
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入你的智谱 API Key：

```ini
ZHIPU_API_KEY=你的Key
LLM_MODEL=glm-4-flash
```

### 4. 下载本地 embedding 模型（约 100MB，仅一次）

```bash
python scripts/download_model.py
```

> 国内网络自动走 `hf-mirror.com` 镜像。下载后完全离线运行。

### 5. 构建知识库索引

```bash
python scripts/build_kb.py
# 输出：重建完成：6 个文档，62 个片段
```

### 6. 启动

```bash
python scripts/run.py
# 等价于: uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

打开浏览器访问：

- 🗨️ **客服对话**：<http://localhost:8000>
- 🛠️ **管理台**：<http://localhost:8000/admin>
- 📚 **API 文档**：<http://localhost:8000/docs>

### 7. 测试与评测（可选）

```bash
pytest tests -q          # 15 项单元测试
python scripts/eval.py   # 检索质量离线评测
ruff check backend scripts tests
```

## 🐳 Docker 一键部署

```bash
docker compose up --build
# 访问 http://localhost:8000
```

需要先把本地模型目录放入 `models/bge-small-zh-v1.5`（见上第 4 步），容器会将其挂载进来。

## 🗂️ 项目结构

```
zhifutong/
├── backend/
│   └── app/
│       ├── core/          # 配置 / LLM / Embedding / 日志 / 异常
│       ├── rag/           # 加载、分块、索引、混合检索、RAG 链
│       ├── dialog/        # 意图识别、记忆、转人工、对话编排
│       ├── api/           # chat / history / kb / admin 路由
│       ├── middleware/    # 鉴权 / 限流 / 日志
│       └── main.py        # FastAPI 入口
├── templates/             # 服务端渲染界面（聊天 / 管理台）
├── knowledge_base/        # 企业 IT 知识库（markdown，可替换）
├── scripts/               # 构建索引 / 下载模型 / 评测 / 启动
├── tests/                 # 单元测试
└── docs/                  # 需求分析 / 架构设计 / 技术选型 / 质量保障
```

## 🧠 RAG 与转人工流程

```
员工提问
  │
  ▼
意图识别 ──┬─ 问候 ──────────────────► 固定欢迎语
           ├─ 明确转人工 / 敏感 / 负面 ──► 立即转人工 + 工单
           └─ 普通问题
                │
                ▼
       混合检索（向量 + BM25）
                │
        ├─ 未命中 ────────────► 兜底话术（拒绝硬答）
        ├─ 低置信度 × 3 次 ────► 自动转人工
        └─ 命中 ────► GLM 流式作答 + 溯源 + 置信度
```

## 📖 文档

位于 [`docs/`](docs/)，完整记录工程设计与决策过程：

| 文档 | 内容 |
|---|---|
| `01-需求分析.md` | EARS 需求规格（R1–R10） |
| `02-架构设计.md` | 分层架构、数据模型、接口契约、ADR |
| `03-技术选型.md` | 框架 / 模型 / 数据库选型对比与理由 |
| `04-错误处理与质量保障.md` | 4 层错误防线、幻觉防护、质量清单 |

## 🚧 路线图

- [x] 检索增强生成 + 流式对话
- [x] 自动转人工 + 工单
- [x] 会话历史 + 管理台
- [x] 单元测试 / 检索评测 / Docker
- [ ] 知识库内容在线写入 / 删除
- [ ] 多会话同屏比对（人工工作台）
- [ ] 接入企业微信 / 飞书 webhook

## 📄 License

MIT License。可自由用于学习、演示与商业集成的二次开发。