# Danwa - 多智能体辩论平台

<div align="center">

[![版本](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/danwa/frontend)
[![Svelte](https://img.shields.io/badge/Svelte-5-orange.svg)](https://svelte.dev)
[![许可证](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

用于协调多个AI智能体讨论的可视化多智能体辩论平台。

</div>

## 概述

Danwa是一个多智能体辩论系统的前端应用，提供可视化界面用于：

- 使用多个AI智能体创建和运行辩论
- 使用蓝图画布进行可视化工作流设计
- 文档管理与RAG（检索增强生成）集成
- 通过服务器发送事件（SSE）实时监控辩论
- 人工介入（HITL）上下文注入
- A2A协议支持外部智能体
- 会话回放与对比分析
- 基于项目的多租户支持

## 功能特性

### 核心辩论系统
- 多智能体辩论编排（战略家、批评者、优化者、主持人）
- 可配置的一致性阈值和最大轮数
- 网络搜索集成（可选/必需模式）
- 实时状态更新和时间线可视化

### 蓝图画布
- 基于节点的可视化工作流构建器
- 拖放界面，基于SvelteFlow
- 两种模式：蓝图（设计）和工作流（执行）
- 资产节点：智能体蓝图、LLM配置文件、角色定义、提示词模板
- 工作流节点：输入、初始化、智能体节点、用户注入、门控
- 边类型：语义边（UsesLlm、ImplementsRole）和控制流边（Sequential、Conditional、Interjection、Feedback）

### 配置管理
- LLM配置文件管理（OpenRouter、OpenAI、Anthropic、Ollama等）
- 按角色创建智能体人格
- 提示词变体管理
- 成本估算计算器

### 文档管理
- 文件上传（PDF、DOCX、ODT、TXT、MD、图像含OCR）
- RAG索引和检索
- 文档分配给辩论

### 项目管理
- 多项目支持
- 项目级配置
- 语言偏好

### 分析与调试
- 审计跟踪查看器
- 带逐步控制功能的会话回放
- 会话对比分析
- 后端日志查看器

## 技术栈

- **框架**: [Svelte 5](https://svelte.dev)（使用 runes：`$state`、`$derived`、`$effect`）
- **样式**: [TailwindCSS](https://tailwindcss.com) 3.4 + @tailwindcss/typography
- **流程图**: [@xyflow/svelte](https://xyflow.com)（SvelteFlow）1.5.2
- **自动布局**: [ELKjs](https://github.com/kieler/elkjs) 0.11.1
- **Markdown**: [marked](https://marked.js.org) 18.0.3
- **验证**: [zod](https://zod.dev) 4.4.2
- **构建**: [Vite](https://vitejs.dev) 5
- **测试**: [Vitest](https://vitest.dev) + [Playwright](https://playwright.dev)

## 快速开始

### 环境要求

- Node.js 18+
- npm 9+
- 运行中的Danwa后端（默认：`http://localhost:8000`）

### 安装

```bash
# 克隆仓库
git clone https://github.com/danwa/frontend.git
cd frontend

# 安装依赖
npm install

# 创建环境文件
cp .env.example .env
# 编辑 .env 并设置 VITE_API_URL 为您的后端URL
```

### 开发

```bash
# 启动开发服务器
npm run dev

# 运行测试
npm run test:unit        # 单元测试
npm run test:e2e         # 端到端测试
npm run test:visual      # 视觉回归测试
npm run test:a11y       # 可访问性测试
npm run test:i18n       # 国际化测试
```

### 生产构建

```bash
# 为生产构建
npm run preview

# 预览生产构建
npm run preview
```

## 项目结构

```
src/
├── components/           # 可复用UI组件
│   ├── blueprint/        # 蓝图画布组件
│   ├── workflow/         # 工作流执行组件
│   ├── hitl/            # 人工介入组件
│   └── *.svelte         # 共享组件
├── views/                # 页面级组件（路由）
│   ├── Dashboard.svelte
│   ├── DebateView.svelte
│   ├── BlueprintCanvasView.svelte
│   └── ...
├── lib/                  # 核心库
│   ├── api.js           # API客户端
│   ├── stores.js        # Svelte存储
│   ├── blueprint/       # 蓝图系统
│   └── i18n/            # 国际化
└── App.svelte           # 根组件
```

## 导航

| 路由 | 描述 |
|-------|-------------|
| `#/dashboard` | 概览与统计数据 |
| `#/debate` | 创建和管理辩论 |
| `#/blueprint` | 可视化工作流构建器 |
| `#/documents` | 文档管理与RAG |
| `#/archive` | 已完成辩论存档 |
| `#/audit` | 审计跟踪查看器 |
| `#/projects` | 项目管理 |
| `#/config` | 配置（配置文件、智能体） |
| `#/replay` | 会话回放 |
| `#/diff` | 会话对比 |

## 国际化

支持的语言：
- 英语（en）
- 德语（de）- 默认

通过URL参数切换：`?lang=en` 或 `?lang=de`

## API集成

前端通过REST API和SSE与后端通信：

- **REST**：所有CRUD操作
- **SSE**：实时辩论更新
- **项目作用域**：自动注入`X-Project-Id`头

## 缺失链接

以下功能在代码库中已存在（API或组件），但尚未在UI中完全暴露：

### 1. 报告生成
- **状态**：API已实现（`generateReport`、`getReportStatus`、`downloadReport`）
- **UI状态**：未实现 - 没有独立的报告视图
- **位置**：`src/lib/api.js` 第385-398行
- **变通方案**：直接使用API

### 2. A2A智能体管理页面
- **状态**：组件已存在，无导航入口
- **UI状态**：部分 - `A2ACapabilities.svelte`存在但无法通过主UI访问
- **位置**：`src/components/blueprint/A2ACapabilities.svelte`
- **变通方案**：通过蓝图画布添加A2A节点时配置

### 3. 独立工作流执行面板
- **状态**：API和组件已实现
- **UI状态**：仅集成在DebateView中
- **位置**：`src/components/workflow/ExecutionPanel.svelte`
- **变通方案**：执行期间使用DebateView

### 4. 蓝图布局持久化
- **状态**：ELKjs自动布局已实现
- **UI状态**：部分 - 保存/加载存在但未完全持久化
- **位置**：`src/lib/blueprint/layout.js`
- **变通方案**：使用画布工具栏的保存/加载按钮

### 5. 会话存档管理UI
- **状态**：API已实现（`softDeleteSession`、`restoreSession`）
- **UI状态**：部分 - 仅可通过回放/对比访问
- **位置**：`src/lib/api.js` 第404-410行
- **变通方案**：通过回放视图访问

### 6. 独立后端日志视图
- **状态**：API已实现（`getBackendLogs`）
- **UI状态**：部分 - 仅在配置 → 系统选项卡中
- **位置**：`src/views/ConfigView.svelte`（系统选项卡）
- **变通方案**：使用配置 → 系统 → 后端日志

### 7. 带UI反馈的配置热重载
- **状态**：API已实现（`reloadProfiles`）
- **UI状态**：部分 - 仅在配置 → 系统选项卡中
- **位置**：`src/views/ConfigView.svelte`
- **变通方案**：使用配置 → 系统 → 配置重载

### 8. 多配置成本对比
- **状态**：API已实现（`estimateCost`）
- **UI状态**：基本表单存在，无对比视图
- **位置**：`src/views/ConfigView.svelte`（成本选项卡）
- **变通方案**：使用配置 → 成本选项卡并手动对比

## 贡献

欢迎贡献！请在提交PR之前阅读我们的贡献指南。

## 许可证

MIT许可证 - 详见[LICENSE](LICENSE)。

## 相关文档

- [技术文档](docs/technical_documentation.md) - 详细技术规格
- [用户手册](docs/user_manual.md) - 终端用户指南

---

*Danwa v2.0 - 基于Svelte 5构建*