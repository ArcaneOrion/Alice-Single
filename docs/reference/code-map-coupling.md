# 代码地图：耦合视图

给 agent 的最小耦合地图：回答“改这里通常还要一起看哪些地方”。

## Bridge 协议
通常联动：
- `backend/alice/cli/main.py`
- `backend/alice/application/dto/responses.py`
- `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`
- `backend/alice/infrastructure/bridge/protocol/`
- `backend/alice/infrastructure/bridge/server.py`
- `backend/alice/infrastructure/bridge/__init__.py`
- `backend/alice/core/logging/configure.py`
- `frontend/src/bridge/protocol/`
- `frontend/src/bridge/client.rs`
- `protocols/bridge_schema.json`
- `backend/tests/integration/test_bridge.py`
- `backend/tests/integration/test_logging_e2e.py`
- `backend/tests/unit/test_core/test_logging_schema.py`

当前边界：
- `bridge/server.py` 是 legacy bridge 兼容薄壳，正式输出应统一经过 compatibility serializer。
- `legacy_compatibility_serializer.py` 不只负责协议投影；它还是 canonical/internal event -> legacy message 的显式 compatibility 边界，并记录 `bridge.compatibility_serializer_used` / `bridge.event_dropped_by_legacy_projection` 两类日志事件。
- 旧协议无法表达的 canonical event 会被显式丢弃并记日志，而不是继续扩展 legacy 顶层消息类型。
- `bridge/stream_manager.py` 仍存在，但仅是 heuristic 兼容资产；若修改其行为，至少联动 `backend/tests/unit/test_core/test_stream_manager.py`。
- `StreamManager` 已不是 `BridgeServer` 构造参数，也不是 `bridge` 包级正式导出。
- 如果改 legacy projection，不要只看 bridge 目录；还要同步核对 logging schema、bridge integration test 与 logging e2e。

## Bridge compatibility logging
通常联动：
- `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`
- `backend/alice/core/logging/configure.py`
- `backend/tests/integration/test_bridge.py`
- `backend/tests/integration/test_logging_e2e.py`
- `backend/tests/unit/test_core/test_logging_schema.py`
- `docs/operations/logging/README.md`

当前边界：
- `bridge.compatibility_serializer_used` 与 `bridge.event_dropped_by_legacy_projection` 属于 `tasks` 类别，而不是 `system` / `changes`。
- 修改 canonical event 到 legacy message 的映射时，必须同步看 serializer、日志 schema、测试与 logging 文档。
## 前端状态流
通常联动：
- `frontend/src/app/state.rs`
- `frontend/src/core/dispatcher.rs`
- `frontend/src/bridge/protocol/message.rs`

## Agent 工作流
通常联动：
- `backend/alice/application/agent/`
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/application/workflow/`
- `backend/alice/domain/llm/services/chat_service.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `backend/tests/integration/test_agent.py`

## Runtime Context 管线
通常联动：
- `backend/alice/application/runtime/`
- `backend/alice/application/__init__.py`
- `backend/alice/application/agent/agent.py`
- `backend/alice/application/workflow/base_workflow.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/domain/llm/services/chat_service.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/domain/llm/providers/base.py`
- `backend/tests/unit/test_domain/test_runtime_context_phase2.py`
- `backend/tests/unit/test_domain/test_stream_service.py`
- `backend/tests/integration/test_agent.py`

当前边界：
- `application/__init__.py` 是包级导出面，不应再通过 eager import 把 `runtime -> agent/services -> ChatService` 拉成循环依赖。
- 现在存在两条相关但不同的输入边界：`runtime_context` 负责 runtime 聚合视图，`request_envelope` 负责发给 provider 的 canonical request 载荷。
- `RequestEnvelope` 的主链路是 `agent.py` -> `WorkflowContext` -> `chat_workflow.py` -> `chat_service.py` -> `stream_service.py` / provider。
- request / trace / span metadata 会沿 `request_envelope.request_metadata` 继续向 provider logging 透传。
- 如果改动 `application/runtime/`、`chat_service.py`、`stream_service.py`、`orchestration_service.py` 或根包导出面，至少联动 `test_stream_service.py`、`test_runtime_context_phase2.py`、`test_agent.py`、`test_logging_e2e.py`。
## Tool Registry / Function Calling
通常联动：
- `backend/alice/domain/execution/models/tool_calling.py`
- `backend/alice/domain/execution/services/tool_registry.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `backend/alice/application/workflow/function_calling_orchestrator.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/tests/unit/test_domain/test_runtime_context_phase2.py`

## 结构化日志
通常联动：
- `backend/alice/core/logging/`
- `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `scripts/validate_logs.py`
- `backend/tests/integration/test_logging_e2e.py`
- `backend/tests/unit/test_core/test_logging_schema.py`
- `backend/tests/performance/test_log_write_speed.py`
- `docs/operations/logging/README.md`

当前边界：
- bridge compatibility 事件也属于结构化日志的一部分，并落到 `tasks` 时间线。
- 如果新增或修改 `bridge.*` / `workflow.*` / `model.*` 事件，要同步检查 schema 文件生成、分类路由与测试断言。

## 技能系统
通常联动：
- `skills/`
- `backend/alice/domain/skills/`
- `backend/alice/domain/execution/services/execution_service.py` 中的 `SkillSnapshotManager`
- `toolkit refresh` 对应加载逻辑

## 何时扩展搜索面
出现下面情况时，不要只改单点：
- 改了协议字段或消息类型。
- 改了 workflow 阶段或状态枚举。
- 改了日志 schema、trace 字段或校验规则。
- 改了技能发现、缓存或 `SKILL.md` 约束。

## 配套阅读
- 总览入口：`docs/reference/code-map.md`
- 结构分层：`docs/reference/code-map-structure.md`
- 权威性说明：`docs/reference/sources-of-truth.md`
