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
- `frontend/src/app/`：App 状态、常量、消息容器。
- `frontend/src/bridge/`：Bridge 客户端、协议编解码、stdio 传输。
- `frontend/src/core/`：事件分发、事件总线、键盘/鼠标处理。
- `frontend/src/ui/`：布局、组件、渲染。
- `frontend/src/util/`：辅助工具与 runtime log。

## Backend
- `backend/alice/application/`：agent、workflow、services、DTO；canonical runtime context 入口也在这一层。
- `backend/alice/application/runtime/`：phase-2 Runtime Context 入口，定义 runtime models、`TimeProvider` 与 `RuntimeContextBuilder`。
- `backend/alice/application/agent/`：请求入口与中断控制；`agent.py` 负责构建 runtime context 并挂到 workflow。
- `backend/alice/application/workflow/`：工作流编排；`base_workflow.py` 暴露带 `runtime_context` 的 `WorkflowContext`，`function_calling_orchestrator.py` 负责 structured tool call -> execution -> tool message 回注。
- `backend/alice/application/services/`：编排服务；`orchestration_service.py` 收敛 memory、skills、tool registry、stream service 与 function-calling orchestrator。
- `backend/alice/domain/`：execution、llm、memory、skills 等业务逻辑。
- `backend/alice/domain/execution/services/`：`execution_service.py` 负责结构化工具执行与 snapshot manager，`tool_registry.py` 提供四类工具快照与模型 function schema。
- `backend/alice/domain/llm/services/`：`chat_service.py` 负责 `<runtime_context>` 请求投影，`stream_service.py` 负责 runtime event 与 structured tool-calling 流式输出。
- `backend/alice/infrastructure/`：legacy bridge、docker、cache、logging。
- `backend/alice/core/`：config、container、event_bus、interfaces、registry。
- `backend/alice/cli/`：当前默认 CLI / TUI 入口。

## 常见改动落点
- TUI 渲染或交互：`frontend/src/ui/`、`frontend/src/core/`。
- 前后端消息收发：`backend/alice/cli/`、`backend/alice/application/dto/`、`backend/alice/infrastructure/bridge/`、`frontend/src/bridge/`。
- Agent 编排：`backend/alice/application/`。
- Runtime Context 收敛：`backend/alice/application/runtime/`、`backend/alice/application/agent/agent.py`、`backend/alice/application/services/orchestration_service.py`、`backend/alice/application/workflow/base_workflow.py`。
- Tool Registry / 工具调用编排：`backend/alice/application/workflow/chat_workflow.py`、`backend/alice/application/workflow/function_calling_orchestrator.py`、`backend/alice/domain/execution/services/`、`backend/alice/domain/llm/services/`。
- 执行、记忆、技能：`backend/alice/domain/`。
- 容器、日志、配置：`backend/alice/infrastructure/`、`backend/alice/core/`、`docs/operations/logging/`。
- 协议契约：`protocols/bridge_schema.json`。

## 配套阅读
- 总览入口：`docs/reference/code-map.md`
- 联动关系：`docs/reference/code-map-coupling.md`
