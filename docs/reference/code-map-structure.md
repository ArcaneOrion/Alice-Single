# 代码地图：结构视图

给 agent 的最小结构地图：回答“这个改动大概落在哪一层、哪个目录”。

## 仓库一级结构
- `frontend/src/`：Rust TUI。
- `backend/alice/`：Python 引擎。
- `backend/tests/`：后端测试。
- `protocols/`：跨语言协议与 schema。
- `prompts/`：prompt 资产。
- `skills/`：技能目录与 `SKILL.md`。
- `docs/`：结构化文档。

## Frontend
- `frontend/src/main.rs`：当前默认 TUI 入口；负责 BridgeClient 启动、事件循环、bridge 消息/错误 drain 与 `render_app()` 渲染。
- `frontend/src/app/`：App 状态、状态枚举、滚动状态、token 统计、布局/文案常量。
- `frontend/src/bridge/`：Bridge 客户端、协议编解码、stdio 传输；`client.rs` 管理 Python 子进程状态，`transport/stdio_transport.rs` 负责 `python3 -u ../backend/alice/cli/main.py` 的 stdin/stdout/stderr 线程桥接。
- `frontend/src/core/`：事件分发、事件类型、键盘/鼠标处理；`dispatcher.rs` 负责把 `BridgeMessage` 和 UI 输入映射到 `App` 状态。
- `frontend/src/ui/`：布局、组件、渲染；`screen.rs` 负责装配真实组件并把布局/滚动状态回写 `App`。
- `frontend/src/util/`：辅助工具与 runtime log。

## Backend
- `backend/alice/application/`：agent、workflow、services、DTO；canonical runtime context / request envelope 入口也在这一层；根包 `application/__init__.py` 采用惰性导出，避免 `runtime -> agent/services -> llm` 的循环导入。
- `backend/alice/application/runtime/`：定义 `RuntimeContext`、`RequestEnvelope`、`RequestMetadata`、`TimeProvider` 与 `RuntimeContextBuilder`；builder 同时负责 runtime 视图与 canonical model request envelope。
- `backend/alice/application/agent/`：请求入口与中断控制；`agent.py` 负责补齐 correlation ids、构建 `runtime_context` 与 `request_envelope`，并一并挂到 workflow。
- `backend/alice/application/workflow/`：工作流编排；`base_workflow.py` 的 `WorkflowContext` 同时携带 `runtime_context` 与 `request_envelope`，`chat_workflow.py` 是 canonical runtime event 与 tool loop 编排中心，`function_calling_orchestrator.py` 负责 structured tool call -> execution -> tool message 回注。
- `backend/alice/application/services/`：编排服务；`orchestration_service.py` 收敛 memory、skills、tool registry、stream service 与 function-calling orchestrator。
- `backend/alice/cli/`：当前默认 Python CLI / TUI bridge 入口；`main.py` 通过 `bootstrap.py` 收口 runtime logging、provider / skill / harness 装配与共享 backend owner。
- `backend/alice/domain/`：execution、llm、memory、skills 等业务逻辑。
- `backend/alice/domain/execution/services/`：`execution_service.py` 负责结构化工具执行与 snapshot manager，`tool_registry.py` 提供工具快照与模型 function schema。
- `backend/alice/domain/llm/services/`：`chat_service.py` 负责把 runtime context 投影成 model-visible system prompt 并组装 `RequestEnvelope`，`stream_service.py` 负责 runtime event、provider binding 与 structured tool-calling 流式输出。
- `backend/alice/infrastructure/`：legacy bridge、gateway、docker、cache、logging；其中 `bridge/server.py` 是 legacy bridge 兼容薄壳，`legacy_compatibility_serializer.py` 是 canonical/internal event -> legacy message 的兼容投影边界，`gateway/` 提供 websocket session、replay、projector 与 interrupt/request transport，`stream_manager.py` 仅保留为 heuristic 兼容资产。
- `backend/alice/core/`：config、container、event_bus、interfaces、registry；`logging/configure.py` 收口结构化日志 schema 与分类路由。

## 常见改动落点
- TUI 渲染或交互：`frontend/src/main.rs`、`frontend/src/app/`、`frontend/src/core/`、`frontend/src/ui/`。
- 前后端消息收发：`backend/alice/cli/`、`backend/alice/infrastructure/bridge/`、`backend/alice/infrastructure/gateway/`、`frontend/src/bridge/`、`frontend/src/core/dispatcher.rs`。
- Agent 编排：`backend/alice/application/`。
- Runtime Context / Request Envelope 收敛：`backend/alice/application/runtime/`、`backend/alice/application/agent/agent.py`、`backend/alice/application/workflow/`、`backend/alice/domain/llm/services/`。
- Tool Registry / 工具调用编排：`backend/alice/application/workflow/chat_workflow.py`、`backend/alice/application/workflow/function_calling_orchestrator.py`、`backend/alice/domain/execution/services/`、`backend/alice/domain/llm/services/`。
- 执行、记忆、技能：`backend/alice/domain/`。
- 容器、日志、配置：`backend/alice/infrastructure/`、`backend/alice/core/`（尤其 `logging/configure.py`）、`docs/operations/logging/`。
- 协议契约：`protocols/bridge_schema.json`。

## 配套阅读
- 总览入口：`docs/reference/code-map.md`
- 联动关系：`docs/reference/code-map-coupling.md`
