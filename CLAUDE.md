# CLAUDE.md

本文件为 Claude Code 在此代码库中工作时提供指导。

> **项目状态**：Alice 已完成从单文件到分层架构的重构。旧入口 (`agent.py`/`tui_bridge.py`) 保留但已由新架构替代。

---

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 API_KEY 和 MODEL_NAME

# 2. 运行（首次启动自动构建 Docker 镜像）
cd frontend && cargo run --release
```

| 操作 | 命令 |
|------|------|
| 构建运行 | `cd frontend && cargo run --release` |
| 列出/刷新技能 | 在 TUI 中发送 `toolkit list` / `toolkit refresh` |
| 检查容器 | `docker ps -a --filter name=alice-sandbox-instance` |
| 更新代码地图 | `/code-map` |

**TUI 快捷键**：`Enter` 发送 | `Esc` 中断 | `Ctrl+O` 切换思考侧边栏 | `Ctrl+C` 退出

---

## 项目概述

Alice 是基于 **ReAct 模式**的智能体框架，采用三层隔离架构：

```
┌──────────────────────────────────────────────────────┐
│  TUI 层 (Rust, frontend/)     — 界面、交互、渲染      │
├──────────────────────────────────────────────────────┤
│  引擎层 (Python, backend/alice/) — 状态机、内存、命令  │
├──────────────────────────────────────────────────────┤
│  沙盒层 (Docker)               — 安全执行环境          │
└──────────────────────────────────────────────────────┘
```

### 目录结构

```
Alice/
├── frontend/src/           # Rust TUI (37 个 .rs 文件)
│   ├── main.rs             # 入口 + 主事件循环
│   ├── app/                # App 状态、常量、消息队列
│   ├── bridge/             # Bridge 客户端、协议编解码、stdio 传输
│   ├── core/               # 事件分发器、事件总线、键盘/鼠标处理
│   ├── ui/                 # 屏幕布局、组件(chat/header/input/sidebar)
│   └── util/               # runtime_log
├── backend/alice/          # Python 引擎 (~85 个 .py 文件)
│   ├── cli/                # 入口: main.py (TUIBridge)
│   ├── application/        # Agent、工作流链、编排服务、DTO
│   ├── domain/             # 内存、LLM、执行、技能 (业务逻辑)
│   ├── infrastructure/     # Bridge 协议、Docker 管理、日志
│   └── core/               # 配置、事件总线、IoC 容器、接口
├── skills/                 # 19 个技能 (akshare, playwright_browser, docx, pdf, ...)
├── prompts/alice.md        # 系统提示词
├── protocols/              # bridge_schema.json 通信协议定义
├── Dockerfile.sandbox      # 沙盒镜像 (ubuntu:24.04 + Node + Python venv + Playwright)
└── docs/                   # logging_schema.md, migration_guide.md
```

---

## 核心架构

### 通信协议

**Rust → Python (stdin)**：原始文本 + 换行，中断信号为 `__INTERRUPT__`

**Python → Rust (stdout)**：JSON Lines，字段 `type` 区分消息类型：

```json
{"type": "status", "content": "thinking"}       // ready/thinking/executing_tool/done
{"type": "thinking", "content": "..."}           // 侧边栏思考流
{"type": "content", "content": "..."}            // 主聊天区正文流
{"type": "tokens", "total": 1234, "prompt": 800, "completion": 434}
{"type": "error", "content": "..."}
```

协议正式定义：`protocols/bridge_schema.json`

### 数据流

```
Rust TUI 按键事件
  → KeyboardHandler → KeyAction::SendMessage
  → StdioTransport.send_text(input) ──stdin──→ Python StdioTransport
  → BridgeServer/MessageHandler
    → AliceAgent.chat() → WorkflowChain → ChatWorkflow
      → ChatService.stream_chat() → OpenAIProvider (流式)
      → StreamManager (思考/内容分流)
      → 工具检测 (正则) → ExecutionService → DockerExecutor
    → 迭代直到无工具调用
  ← JSON Lines ──stdout──← Rust BridgeClient (stdout 读取线程)
  → EventDispatcher.handle_bridge_message() → App 状态更新 → 渲染
```

### 内存系统

| 层级 | 文件 | 用途 | 保留策略 |
|------|------|------|----------|
| **Working** | `memory/working_memory.md` | 对话历史 | 最近 30 轮，代码块过滤，FIFO |
| **STM** | `memory/short_term_memory.md` | 短期事实 | 7 天滚动，过期 LLM 提炼到 LTM |
| **LTM** | `memory/alice_memory.md` | 经验教训 | 永久存储 |
| **Todo** | `memory/todo.md` | 任务追踪 | 手动管理 |

### 内置命令（宿主机执行，非沙盒）

```bash
memory "内容" / memory "内容" --ltm    # STM / LTM
todo "任务描述"                         # 任务追踪
update_prompt "新内容"                  # 修改系统提示词
toolkit list / toolkit refresh          # 技能管理
```

### 技能系统

`skills/` 目录下 19 个技能，每个含 `SKILL.md`（YAML frontmatter + Markdown）。通过 `SkillRegistry` 自动发现，`CacheSkillLoader` 基于 mtime 缓存。调用前必须阅读 `SKILL.md`。

### StreamManager 思考/内容分流

标记对：`` ```python/bash/ `` ``、`<thought>/<reasoning>/<thinking>/<python>` — 识别为思考内容（侧边栏）。裸关键词 `python `、`cat ` 等同。滑动窗口防标记截断，10MB 溢出保护。

---

## 配置

### 环境变量 (`.env`)

| 变量 | 必需 | 说明 |
|------|------|------|
| `API_KEY` | ✅ | LLM API 密钥 |
| `MODEL_NAME` | ✅ | 模型标识符 |
| `API_BASE_URL` | ❌ | API 端点 |
| `WORKING_MEMORY_MAX_ROUNDS` | ❌ | 工作内存轮数 (默认 30) |
| `REQUEST_HEADER_PROFILES` | ❌ | JSON 请求头轮询配置 |

### 关键配置类

- `Settings` (backend/alice/core/config/settings.py)：LLMConfig, MemoryConfig, DockerConfig, LoggingConfig, BridgeConfig, SecurityConfig
- `DockerConfig` (backend/alice/infrastructure/docker/config.py)：镜像、容器、挂载点
- Rust 侧常量 (frontend/src/app/constants.rs)：UI 布局尺寸、tick rate、spinner

---

## Docker 沙盒

**Dockerfile.sandbox** 7 阶段构建：`ubuntu:24.04` → 系统工具 → Node.js LTS → Python venv (`/opt/alice_env`) → Playwright + Chromium → 项目依赖 (`requirements.txt`, 32 包) → 环境变量

**挂载**：`skills/` → `/app/skills`，`alice_output/` → `/app/alice_output`。prompts/memory/源代码**未挂载**。

**安全**：`shell=False`、120s 超时、基础命令拦截。⚠️ 容器以 root 运行、无网络/资源限制。

---

## 日志系统

双模式：JSONL 结构化（默认）+ Legacy 文本（`USE_LEGACY_LOGGING=1`）

三文件路由（`.alice/logs/`）：`system.jsonl`（生命周期）、`tasks.jsonl`（执行/LLM）、`changes.jsonl`（内存/技能/配置）

Schema v2.0，含 `trace_id`/`request_id`/`span_id` 分布式追踪字段、三级脱敏策略。详见 `docs/logging_schema.md`。

---

## 开发指南

### 添加技能

```bash
mkdir skills/my-skill
cat > skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: 技能描述
---
# 技能说明
EOF
# TUI 中运行: toolkit refresh
```

### 测试

```bash
# Python 测试
cd backend && pytest tests/          # unit/ + integration/ + performance/

# Rust 测试
cd frontend && cargo test && cargo clippy && cargo fmt
```

### 调试

| 问题 | 排查 |
|------|------|
| TUI 渲染 | 检查 `frontend/frontend.log`、终端 stderr |
| 流式解析 | 检查 `.alice/logs/tasks.jsonl`、`alice_runtime.log` |
| Docker 执行 | `docker ps -a --filter name=alice-sandbox-instance` |
| 技能未加载 | `toolkit refresh` |

---

## 重要约束

1. **双入口并存**：`cli/main.py`（新，AliceAgent + WorkflowChain）和 `bridge/server.py`（旧，BridgeServer + MessageHandler）并行存在
2. **三处容器初始化重复**：`LifecycleService`、`DockerExecutor`、`ContainerManager` 各自实现三阶段初始化
3. **类型重复定义**：`AgentStatus`、`Author`、`Message` 在 Rust app/core/ui 层各有独立定义，通过转换函数互转
4. **`MessageQueue` 未使用**：已定义但 `App` 直接用 `Vec<Message>`
5. **`EventBus` 基本空转**：创建后未实际用于事件分发
6. **安全审查弱**：仅拦截 `rm` 命令
7. **修改代码后**请运行 `/code-map` 更新 `CODE_MAP.md`

---
