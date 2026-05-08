# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作提供指导。

## 仓库概览

Alice 是一个智能体运行时，采用 Rust TUI 前端与 Python 后端。前端以后台子进程方式启动后端，通过 stdin/stdout 以 JSON Lines 格式通信。

## 常用命令

### 启动应用
```bash
# 1. 配置 LLM 凭证
${EDITOR:-vi} .alice/config.json        # 编辑 .alice/config.json；至少填写 llm.api_key 与 llm.model_name

# 2. 启动 TUI（自动启动 Python 后端）
cd frontend && cargo run --release
```

### 后端（Python）
```bash
# 运行全部测试
python -m pytest backend/tests

# 运行单个测试
python -m pytest backend/tests/unit/test_domain/test_chat_workflow.py -v

# 代码检查与类型检查
python -m ruff check backend/alice backend/tests
python -m mypy backend/alice

# 安装依赖（使用 hatchling）
cd backend && pip install -e ".[dev]"
```

### 前端（Rust）
```bash
cd frontend && cargo test
cd frontend && cargo clippy
cd frontend && cargo fmt --check
```

## 架构

### 依赖分层（严格）
```
application/ -> domain/       （业务规则）
             -> infrastructure/ （外部系统适配）
             -> core/          （共享框架工具）

domain/      -> core/
infrastructure/ -> core/
```
- **业务规则** 放在 `domain/`。
- **编排与请求流程** 放在 `application/`。
- **外部系统 / IO / 协议适配** 放在 `infrastructure/`。
- **可复用框架工具** 放在 `core/`。
- 严禁 **跨层直接引用**（例如 `domain/` 不应导入 `application/`）。

### 高耦合区域 —— 改动其中一个文件时，必须检查其他关联文件
1. **桥接协议**：修改任何字段 / 状态 / 中断语义时，`frontend/` 与 `backend/` 必须同步联调。
2. **执行后端**：修改执行器时必须检查 `command_registry.py`、`lifecycle_service.py`、`execution_service.py` 与 `executors/`。
3. **智能体工作流**：`chat_workflow.py` <-> `chat_service.py` <-> `stream_service.py` <-> `function_calling_orchestrator.py`。
4. **配置系统**：修改 `Settings` 字段时必须检查 `loader.py`、`bootstrap.py` 与 `orchestration_service.py`。

### 运行时拓扑
```
┌──────────────────────────────┐
│   前端（Rust TUI）            │  ratatui + crossterm
│   stdin/stdout JSON Lines    │
└──────────┬───────────────────┘
           │ 生成子进程
┌──────────▼───────────────────┐
│   后端（Python）              │  backend/alice/cli/main.py
│   TUIBridge 类               │
└──────────────────────────────┘
```
- 前端通过 `BridgeClient::spawn_default`（`frontend/src/bridge/client.rs`）生成后端进程。
- 通信格式为每行一个 JSON 对象，经 stdin/stdout 传输。

### 桥接协议（stdin/stdout JSON Lines）
- Schema 参考：`protocols/bridge_schema.json`
- 每条消息 **必须** 包含 `"type"` 字段。
- 核心消息类型：
  - `status` — `{"type":"status","content":"ready|thinking|executing_tool|done"}`
  - `thinking` — `{"type":"thinking","content":"..."}`
  - `content` — `{"type":"content","content":"..."}`
  - `tokens` — `{"type":"tokens","total":int,"prompt":int,"completion":int}`
  - `error` — `{"type":"error","content":"...","code":"..."}`
  - `interrupt` — `{"type":"interrupt"}`
- 处理该协议的后端入口：`backend/alice/cli/main.py`（`TUIBridge` 类）。
- 旧版桥接服务器（`backend/alice/infrastructure/bridge/server.py`）已 **废弃**；新功能请勿使用。

### 前端主循环（`frontend/src/main.rs`）
- `TerminalGuard` 结构体利用 `Drop` 特性，即使在 panic 时也能保证终端状态恢复。
- 每个 tick（约 100 ms）的事件循环顺序：
  1. `drain_bridge_messages` —— 读取后端 stdout 中所有待处理行。
  2. 通过 `render_app` 渲染 UI。
  3. 轮询 crossterm 事件（键盘、鼠标、粘贴），最小超时 5 ms。
  4. `app.on_tick()` 执行基于定时器的更新。
- 粘贴事件（`Event::Paste`）原生处理，内容追加到输入缓冲区。

## 关键边界
1. 默认用户配置源为 `.alice/config.json`。
2. 运行时提示词边界为 `.alice/prompt/*.xml` 与 `.alice/prompt/prompt.xml`。
3. 默认 Python CLI / 桥接入口为 `backend/alice/cli/main.py`。
4. `backend/alice/infrastructure/bridge/server.py` 已 **废弃（旧版）**。
5. 修改执行后端时，至少需联动：`command_registry.py`、`lifecycle_service.py`、`execution_service.py` 与 `executors/`。

## 调试
- **TUI 渲染问题**：查看 `frontend/frontend.log` 与终端 stderr。
- **流式与任务日志**：`.alice/logs/tasks.jsonl`、`alice_runtime.log`。
- **容器状态**：`docker ps -a --filter name=alice-sandbox-instance`。
- **技能刷新**：在 TUI 中发送 `toolkit refresh`。

## 工作约束
- 修改代码前先运行针对性检查（测试 / lint / 类型检查），修改后再运行同样的检查。
- 不要新建顶层杂项目录；优先扩展现有包。
