# Danwa（辩论智能体）

可审计的多智能体辩论工作流系统，使用 AI 智能体通过结构化辩论来分析、批判和优化论点。现已支持 **DMS（文档管理系统）**，集成 **PaddleOCR**、**RAG（检索增强生成）** 管道、**项目隔离**、**A2A（智能体到智能体）协议** 以及 **实时 SSE 更新**。

## 快速开始

```bash
# 快速安装（安装 uv、创建虚拟环境、安装依赖）
bash setup.sh

# 设置 DMS 依赖（可选 PaddleOCR）
bash scripts/setup_dms.sh

# 启动应用（按需运行）
bash scripts/start.sh

# 检查状态
bash scripts/status.sh

# 停止应用
bash scripts/stop.sh
```

在浏览器中打开 `http://localhost:8000`。

无需 systemd — 通过简单脚本按需运行。

## 工作原理

四个专门的 AI 智能体在 **LangGraph 状态机** 的编排下协作进行结构化辩论：

```
输入 → [战略家] → [批评家] → [优化师] → [主持人]
        ↓            ↓           ↓           ↓
      策略        批评        综合        共识评分 (0.0-1.0)
```

1. **战略家** — 制定逻辑论证结构
2. **批评家** — 识别弱点和风险（魔鬼代言人）
3. **优化师** — 综合策略和批评，生成精炼输出
4. **主持人** — 评估共识并对结果打分

辩论运行可配置的轮数（1-20轮），当达到共识阈值时提前停止。

## 核心特性

- **多智能体审议** — 四个专门的智能体协作产生高质量分析
- **灵活的 LLM 后端** — 通过 LiteLLM 支持本地（LM Studio、Ollama）或云端（OpenRouter、OpenAI、Anthropic）
- **文档分析** — 上传 PDF、DOCX、ODT、ODS、ODP 文件，支持 OCR
- **网络事实核查** — 通过 SearXNG 或 DuckDuckGo 进行可选验证（关闭/可选/必需模式）
- **语义记忆** — 基于 ChromaDB 的先例检索
- **审计追踪** — 完整的 JSONL 跟踪日志，确保可重现性
- **报告生成** — 导出 DOCX 或 PDF 格式的结果
- **隐私保护** — PII 脱敏（邮箱、IP、电话号码）和可配置的数据保留策略
- **项目隔离** — 基于 SQLite 的项目系统，每个项目独立存储数据
- **文档管理系统（DMS）** — 基于项目的文档组织，SQLite + ChromaDB
- **PaddleOCR 集成** — 扫描 PDF 和图像的 OCR
- **RAG 管道** — 自动和手动文档检索，为辩论提供上下文
- **混合检索** — BM25 + 向量搜索 + 重排序，实现最佳检索效果
- **实时更新** — 服务器推送事件（SSE）实现实时辩论进度可视化
- **现代 Web UI** — Svelte 5 + Tailwind CSS + @xyflow/svelte 工作流图
- **国际化** — 完整的 i18n 支持（德语/英语）
- **带外输入** — 在辩论运行期间注入额外上下文
- **A2A 协议** — 通过 JSON-RPC 2.0 实现智能体到智能体通信（服务端 + 客户端）
- **外部智能体集成** — 将外部 AI 智能体作为辩论参与者
- **智能体卡片发现** — 标准的 `/.well-known/agent.json` 端点，供 A2A 客户端发现

## 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| 后端框架 | [FastAPI](https://fastapi.tiangolo.com) + [LangGraph](https://langchain-ai.github.io/langgraph/) |
| LLM 集成 | [LiteLLM](https://litellm.ai) |
| UI 框架 | [Svelte 5](https://svelte.dev) + [Tailwind CSS](https://tailwindcss.com) |
| 工作流可视化 | [@xyflow/svelte](https://svelteflow.dev) + [ELK.js](https://github.com/kieler/elkjs) |
| 前端构建 | [Vite](https://vitejs.dev) 5 |
| 向量数据库 | [ChromaDB](https://www.trychroma.com) |
| 网络搜索 | SearXNG / DuckDuckGo |
| 文档解析 | pdfplumber、pypdf、python-docx、odfpy |
| 报告生成 | python-docx、[WeasyPrint](https://weasyprint.org) |
| 数据库 | SQLite（辩论、会话、项目） |
| DMS 模块 | 自定义（SQLite + ChromaDB + PaddleOCR） |
| OCR 引擎 | [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)（可选） |
| Python 包管理 | [uv](https://github.com/astral-sh/uv) |
| Node 包管理 | npm |
| 后端测试 | pytest 8+ |
| 前端测试 | [Playwright](https://playwright.dev) 1.59+（E2E、视觉、无障碍、i18n） |
| 代码检查 | [ruff](https://github.com/astral-sh/ruff) 0.4+ |
| 数据验证 | [Pydantic](https://docs.pydantic.dev) 2.7+ |
| SSE 支持 | [sse-starlette](https://github.com/syroegkin/sse-starlette) |
| 前端 i18n | 自定义加载器（德语/英语） |
| A2A 协议 | [Google A2A](https://github.com/google/A2A)（JSON-RPC 2.0 over HTTP） |
| A2A HTTP 客户端 | [httpx](https://www.python-httpx.org) |

## 项目结构

```
danwa/
├── backend/                     # FastAPI + LangGraph 后端
│   ├── main.py                  # 应用工厂（uvicorn 入口）
│   ├── api/
│   │   ├── deps.py             # 依赖注入（get_project_id、stores）
│   │   └── routers/            # API 路由处理器
│   │       ├── debate.py       # 辩论 CRUD + SSE 流
│   │       ├── profiles.py     # LLM、智能体、提示词管理
│   │       ├── dms.py         # 文档管理系统
│   │       ├── projects.py    # 项目隔离
│   │       ├── audit.py       # 审计追踪访问
│   │       ├── config.py      # 应用设置
│   │       ├── sessions.py    # 会话管理
│   │       ├── health.py      # 健康检查端点
│   │       └── system.py      # 系统操作（重载、日志）
│   ├── core/
│   │   ├── config.py         # Pydantic Settings（环境变量）
│   │   └── profiles.py       # LLMProfile、AgentPersona、PromptVariant 模式
│   ├── models/
│   │   └── schemas.py        # API 请求/响应 Pydantic 模型
│   ├── workflow/
│   │   ├── debate_graph.py   # LangGraph 状态机构建器
│   │   ├── nodes.py          # 节点函数（initialize、run_agent 等）
│   │   └── state.py         # DebateState TypedDict 定义
│   ├── services/
│   │   ├── llm_service.py   # LLM 调用（LiteLLM + 本地 HTTP）
│   │   ├── profile_service.py # YAML 配置文件 CRUD + 验证
│   │   ├── prompt_service.py # Markdown 模板渲染
│   │   ├── web_search.py    # SearXNG / DuckDuckGo 集成
│   │   └── dms/            # 文档管理系统服务
│   │       ├── service.py   # DMS 门面（编排器）
│   │       ├── database.py  # DMS 的 SQLite 模式
│   │       ├── document_processor.py # 文件解析 + OCR
│   │       ├── chunker.py   # 文本分块（512 token）
│   │       ├── vector_store.py # ChromaDB 接口
│   │       ├── metadata_index.py # 分块元数据索引
│   │       ├── rag_pipeline.py # RAG 管道
│   │       ├── hybrid_retriever.py # BM25 + 向量 + 重排序
│   │       └── rag_context_formatter.py # RAG 上下文格式化
│   ├── a2a/                    # A2A 协议（智能体到智能体）
│   │   ├── schemas.py        # A2A JSON-RPC 模式（Task、Message、Part）
│   │   ├── config.py         # A2A 配置加载器
│   │   ├── agent_card.py     # 智能体卡片（发现用）
│   │   ├── task_manager.py   # SQLite 支持的持久化任务
│   │   ├── server.py         # A2A 服务端（接收任务）
│   │   ├── router.py         # FastAPI 路由（JSON-RPC + Agent Card）
│   │   ├── client.py         # A2A 客户端（发起调用）
│   │   └── node.py           # A2A 智能体的 LangGraph 节点
│   ├── persistence/
│   │   ├── project_store.py # 基于 JSON 文件的项目存储
│   │   ├── debate_store.py  # SQLite 辩论存储
│   │   └── audit.py         # 审计事件记录
│   └── migrations/
│       └── migrate_projects.py # 项目隔离迁移
├── frontend/                    # Svelte 5 SPA
│   ├── src/
│   │   ├── main.js           # 入口点
│   │   ├── App.svelte        # 根组件（哈希路由）
│   │   ├── views/            # 页面级组件
│   │   │   ├── Dashboard.svelte
│   │   │   ├── DebateView.svelte
│   │   │   ├── AuditView.svelte
│   │   │   ├── ConfigView.svelte
│   │   │   ├── ProjectsView.svelte
│   │   │   ├── DocumentsView.svelte
│   │   │   └── ArchiveView.svelte
│   │   ├── components/       # 可复用 UI 组件
│   │   │   ├── Layout.svelte
│   │   │   ├── Sidebar.svelte
│   │   │   ├── WorkflowGraph.svelte
│   │   │   ├── DebateTimeline.svelte
│   │   │   ├── ConsensusPanel.svelte
│   │   │   └── workflow/      # 工作流可视化
│   │   │       ├── WorkflowCanvas.svelte
│   │   │       ├── nodes/     # AgentNode、InputNode 等
│   │   │       ├── edges/     # FlowEdge、FeedbackEdge 等
│   │   │       └── panels/   # TimelinePanel、NodeDetailPanel
│   │   ├── lib/              # 工具和状态管理
│   │   │   ├── api.js        # API 客户端（fetch 封装）
│   │   │   ├── stores.js     # Svelte writable stores
│   │   │   ├── sse.js        # SSE 客户端（实时更新）
│   │   │   ├── i18n/        # 国际化
│   │   │   └── workflow/     # 工作流状态管理
│   │   └── tests/           # Playwright E2E 测试
│   ├── package.json          # Node 依赖
│   ├── vite.config.js        # Vite 配置
│   ├── tailwind.config.js    # Tailwind CSS 配置
│   └── postcss.config.js     # PostCSS 配置
├── profiles/                    # 配置文件（YAML + Markdown）
│   ├── llm/                     # LLM 配置文件定义
│   │   ├── openrouter-claude.yaml
│   │   ├── openrouter-gpt4.yaml
│   │   ├── openrouter-grok.yaml
│   │   ├── xiaomi-mimo.yaml
│   │   └── local-qwen.yaml
│   ├── agents/                  # 智能体角色定义
│   │   ├── strategist-default.yaml
│   │   ├── critic-default.yaml
│   │   ├── optimizer-default.yaml
│   │   ├── moderator-default.yaml
│   │   ├── critic-stoic.yaml
│   │   └── strategist-german-law.yaml
│   └── prompts/                 # 提示词模板（Markdown）
│       ├── default/             # 默认变体
│       │   ├── strategist.md
│       │   ├── strategist-en.md
│       │   ├── critic.md
│       │   ├── critic-en.md
│       │   ├── optimizer.md
│       │   ├── optimizer-en.md
│       │   ├── moderator.md
│       │   └── moderator-en.md
│       └── variants/            # 命名提示词变体
│           ├── kantian/          # 康德伦理学变体
│           └── steiner/          # 斯坦纳变体
├── config/                       # 应用设置
│   └── settings.yaml           # 应用设置（搜索、隐私、DMS、UI）
├── data/                        # 运行时数据（运行时创建）
│   ├── audit.db                # 审计事件 SQLite 数据库
│   └── projects/              # 每个项目的数据
│       ├── _default/           # 系统默认项目
│       └── {project_id}/
├── logs/                         # 辩论跟踪日志（JSONL）
│   └── debate-agent.log         # 应用日志文件
├── tests/                        # Pytest 测试套件
│   ├── backend/                 # 后端特定测试
│   └── ...
├── docs/                         # 文档
│   ├── user_manual.md          # 用户手册
│   └── technical_documentation.md # 技术文档
├── scripts/                      # 工具脚本
│   ├── setup.sh                # 快速安装（uv、venv、依赖）
│   ├── start.sh                # 启动应用
│   ├── stop.sh                 # 停止应用
│   └── status.sh              # 检查应用状态
├── plans/                       # 开发计划和冲刺文档
├── pyproject.toml               # Python 项目元数据和依赖
├── Makefile                     # 开发工作流（安装、测试、检查、格式化）
└── setup.sh                     # 快速安装脚本
```

## 配置

配置文件系统使用类型化的 Pydantic 模式和 YAML 文件。所有配置文件通过 `/api/v1/profiles/` API 和配置 UI 进行管理。

### LLM 配置文件（`profiles/llm/*.yaml`）

每个 LLM 配置文件是一个独立的 YAML 文件，包含类型化字段：

```yaml
# profiles/llm/openrouter-claude.yaml
id: openrouter-claude-3.6-sonnet
name: Claude 3.6 Sonnet (OpenRouter)
provider: openrouter          # openrouter | openai | anthropic | local | ollama
model: anthropic/claude-3.6-sonnet
api_base: https://openrouter.ai/api/v1
api_key_env: OPENROUTER_API_KEY
max_tokens: 4096
context_window: 200000
temperature: 0.7
timeout: 600
cost_per_1k_input: 0.003
cost_per_1k_output: 0.015
```

可用的 LLM 配置文件：`openrouter-claude`、`openrouter-gpt4`、`openrouter-grok-4.2`、`xiaomi-mimo-v2.5-pro` 以及多个本地模型。

### 智能体角色（`profiles/agents/*.yaml`）

每个智能体角色定义角色、系统提示词和关联的 LLM 配置文件：

```yaml
# profiles/agents/strategist-default.yaml
id: strategist-default
name: 默认战略家
role: strategist              # strategist | critic | optimizer | moderator
system_prompt: |
  你是多智能体辩论系统中的战略家智能体。
  ...
llm_profile_id: openrouter-claude-3.6-sonnet
max_rounds: 5
consensus_threshold: 0.9
tags: [default, balanced]
```

默认角色：`strategist-default`、`critic-default`、`optimizer-default`、`moderator-default`。还提供了带 `-example` 后缀的额外角色。

### 提示词变体（`profiles/prompts/`）

提示词模板是按变体组织的 Markdown 文件，支持特定语言覆盖（`*-en.md`）：

```
profiles/prompts/
├── default/              # 默认变体
│   ├── strategist.md     # 德语
│   ├── strategist-en.md  # 英语
│   ├── critic.md
│   ├── critic-en.md
│   ├── optimizer.md
│   ├── optimizer-en.md
│   ├── moderator.md
│   └── moderator-en.md
└── variants/
    ├── kantian/          # 康德伦理学变体
    │   ├── strategist.md
    │   └── critic.md
    └── steiner/          # 斯坦纳变体
        ├── strategist.md
        └── critic.md
```

### 配置文件 API 端点

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/v1/profiles/llm` | 列出所有 LLM 配置文件 |
| GET | `/api/v1/profiles/llm/{id}` | 获取特定 LLM 配置文件 |
| POST | `/api/v1/profiles/llm` | 创建 LLM 配置文件 |
| PUT | `/api/v1/profiles/llm/{id}` | 更新 LLM 配置文件 |
| DELETE | `/api/v1/profiles/llm/{id}` | 删除 LLM 配置文件 |
| GET | `/api/v1/profiles/agents` | 列出智能体角色（`?role=` 过滤） |
| GET | `/api/v1/profiles/agents/{id}` | 获取特定角色 |
| POST | `/api/v1/profiles/agents` | 创建智能体角色 |
| PUT | `/api/v1/profiles/agents/{id}` | 更新智能体角色 |
| DELETE | `/api/v1/profiles/agents/{id}` | 删除智能体角色 |
| GET | `/api/v1/profiles/prompts` | 列出提示词变体 |
| GET | `/api/v1/profiles/prompts/{id}/preview` | 预览智能体角色的提示词 |
| POST | `/api/v1/profiles/prompts` | 创建提示词变体 |
| DELETE | `/api/v1/profiles/prompts/{id}` | 删除提示词变体 |

### 应用设置（`config/settings.yaml`）

```yaml
ui:
  language: en                   # 默认 UI 语言（en | de）

search:
  engine: duckduckgo             # searxng | duckduckgo（默认：duckduckgo）
  max_results: 5

privacy:
  strict_mode: false             # 阻止所有外部调用
  redact_traces: true            # 日志中的 PII 脱敏
  retention_days: 90             # 自动清理旧数据
```

### A2A 配置（`config/a2a.json`）

A2A（智能体到智能体）协议使 Danwa 能够与外部 AI 智能体参与多智能体工作流。

```json
{
  "enabled": false,
  "server": {
    "enabled": true,
    "path": "/a2a"
  },
  "external_agents": []
}
```

| 字段 | 描述 |
|------|------|
| `enabled` | 全局启用/禁用 A2A 集成 |
| `server.enabled` | 启用 A2A 服务端（接收传入任务） |
| `server.path` | JSON-RPC 端点路径（默认：`/a2a`） |
| `external_agents` | 外部智能体 URL 列表，用于发起调用 |

#### A2A 端点

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/.well-known/agent.json` | 智能体卡片发现（A2A 规范） |
| POST | `/a2a` | JSON-RPC 端点（`tasks/send`、`tasks/get`、`tasks/cancel`） |

#### 在辩论中使用 A2A

创建辩论时，在请求体中包含 `a2a_agents`：

```json
{
  "case": { "text": "我们应该采用微服务吗？" },
  "a2a_agents": [
    {
      "url": "https://external-agent.example.com/a2a",
      "role": "external_reviewer",
      "position": "after:moderator"
    }
  ]
}
```

外部智能体将作为额外的辩论参与者在标准智能体（战略家、批评家、优化师、主持人）完成轮次后被调用。

#### A2A 架构

```
Danwa 作为服务端（接收）：          Danwa 作为客户端（发起）：
┌─────────────┐                      ┌─────────────┐
│ 外部 A2A    │──tasks/send──▶      │   Danwa     │
│   客户端    │◀──result────        │   工作流    │
└─────────────┘                      │   引擎     │
       │                             └──────┬──────┘
       ▼                                    │
┌─────────────┐                      ┌──────▼──────┐
│  Danwa A2A  │                      │  A2A 客户端 │
│   服务端    │──creates──▶         │  (httpx)    │──tasks/send──▶
│  (FastAPI)  │   debate              └─────────────┘  外部智能体
└─────────────┘
```

## 开发

### 前置要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) 包管理器
- Node.js 18+ 和 npm（前端开发用）
- （可选）[LM Studio](https://lmstudio.ai) 用于本地 LLM 托管
- （可选）[SearXNG](https://searxng.org) 用于网络搜索

### 快速安装

```bash
# 克隆/下载项目
cd /media/data/coding/danwa

# 运行安装脚本（安装 uv、创建虚拟环境、安装依赖）
bash setup.sh

# 设置 DMS 依赖（可选，用于 PaddleOCR）
bash scripts/setup_dms.sh
```

### 前端安装

```bash
cd frontend

# 安装依赖
npm install

# 启动 Vite 开发服务器（http://localhost:5173）
npm run dev

# 构建生产版本（输出到 frontend/dist/）
npm run build

# 预览生产构建
npm run preview
```

### 运行应用

#### 开发模式

```bash
# 终端 1：启动后端
cd /media/data/coding/danwa
bash scripts/start.sh

# 终端 2：启动前端（可选，用于开发）
cd /media/data/coding/danwa/frontend
npm run dev
```

- 后端：`http://localhost:8000`（FastAPI，交互式文档在 `/docs`）
- 前端开发服务器：`http://localhost:5173`

#### 生产模式

```bash
# 构建前端
cd /media/data/coding/danwa/frontend
npm run build

# 启动后端（提供前端静态文件）
cd ..
bash scripts/start.sh
```

在 `http://localhost:8000` 访问应用。

### 测试

#### 后端测试（pytest）

```bash
# 运行所有测试
make test
# 或
uv run pytest tests/ -v

# 运行特定测试文件
uv run pytest tests/backend/test_debate_api.py -v

# 使用 asyncio 模式运行
uv run pytest tests/backend/ -v --asyncio-mode=auto
```

#### 前端测试（Playwright）

```bash
cd frontend

# 运行所有 E2E 测试
npm run test:e2e

# 使用 UI 模式运行
npm run test:e2e:ui

# 使用有头浏览器运行
npm run test:e2e:headed

# 运行特定测试套件
npm run test:contracts    # API 契约测试
npm run test:visual       # 视觉回归测试
npm run test:a11y          # 无障碍测试
npm run test:i18n          # 国际化测试
```

### 代码检查和格式化

#### 后端（ruff）

```bash
# 检查
make lint
# 或
uv run ruff check .

# 格式化
make format
# 或
uv run ruff format .

# 运行 CI 检查（检查 + 测试）
make check
```

## 项目依赖（`pyproject.toml`）

```toml
[project]
name = "debate-agent"
version = "2.0.0"
requires-python = ">=3.11"

[dependencies]
litellm>=1.40.0
pydantic>=2.7.0
pydantic-settings>=2.0.0
pyyaml>=6.0.0
httpx>=0.27.0
duckduckgo-search>=6.0.0
pdfplumber>=0.10.0
pypdf>=4.0.0
python-docx>=1.1.0
odfpy>=1.4.1
chromadb>=0.5.0
weasyprint>=61.0
tiktoken>=0.7.0
rank-bm25>=0.2.1
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9
langgraph>=0.2.0
langchain-core>=0.3.0
jinja2>=3.1.0
sse-starlette>=2.0.0
python-dotenv>=1.0.0

[project.optional-dependencies]
test = ["pytest>=8.0", "pytest-asyncio>=0.23", "ruff>=0.4"]
dms = ["paddlepaddle>=3.0", "paddleocr>=3.5.0"]
```

## 文档

- **用户手册**：`docs/user_manual.md` — 涵盖所有功能、配置选项、隐私设置和故障排除
- **技术文档**：`docs/technical_documentation.md` — 面向开发者的综合深入技术文档

---

## 缺失环节（功能尚未在 UI 中暴露）

> **什么是"缺失环节"？** 这些是在后端中完全实现但**尚未通过用户界面访问**的功能。
>
> **最后审计时间**：2026-05-10 — 全面代码库扫描。
>
> **近期已暴露（此前迭代中已接线）**：
> - 报告生成 — 下载 500 错误已修复
> - 应用设置 — 已在 ConfigView + ProjectSettings 中接线
> - 手动 RAG 搜索 — 已在 DocumentsView 中接线
> - A2A 智能体发现 — 已在 DebateView 中接线
> - 会话归档/恢复 — 已在 ArchiveView 中接线
> - 工作流执行控制 — 已在 ExecutionPanel 中接线
> - 蓝图编译/克隆 — 已在 BlueprintCanvasView 中接线
> - 画布布局 CRUD — 已在 Palette + BlueprintCanvas 中接线
> - 角色类型 CRUD — 已在 RoleTypeForm + ConfigView 中接线
> - 语言 API — 已在 LanguageSwitcher 中接线

### 历史会话管理 — 低影响
- **后端**：旧版 `backend/api/routers/sessions.py` 路由（已被新路由替代）
- **缺失**：没有该旧版路由的前端 API 函数或 UI

### 报告 SSE 进度流 — 低影响
- **后端**：`GET /api/v1/sessions/{session_id}/report/stream`
- **API 客户端**：`createReportSSE()` 存在于 `api.js` 但**从未被调用**
- **缺失**：没有视图使用报告生成的 SSE 进度流

### 汇总表

| 功能 | 后端 | API 客户端 | UI | 状态 |
|------|------|------------|-----|------|
| 历史会话管理 | ✅ | ❌ 缺失 | ❌ 缺失 | **未暴露** |
| 报告 SSE 进度流 | ✅ | ✅ 存在 | ❌ 缺失 | **未暴露** |
| 辩论工作流 | ✅ | ✅ | ✅ | 已暴露 |
| HITL 交互 | ✅ | ✅ | ✅ | 已暴露 |
| 辩论中的 A2A | ✅ | ✅ | ✅ | 已暴露 |
| 蓝图画布 | ✅ | ✅ | ✅ | 已暴露 |
| 回放和对比视图 | ✅ | ✅ | ✅ | 已暴露 |

*详细信息请参阅 `docs/technical_documentation.md` 和 `docs/user_manual.md` 中的"缺失环节"部分。*

---

## 许可证

[在此添加您的许可证]

---

*Danwa v2.0.0 | 基于 FastAPI + LangGraph + LiteLLM + Svelte 5 + @xyflow/svelte 构建*
