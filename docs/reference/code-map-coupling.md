# 代码地图：耦合视图

给 agent 的最小耦合地图：回答“改这里通常还要一起看哪些地方”。

## Bridge 协议
通常联动：
- `backend/alice/cli/main.py`
- `backend/alice/application/dto/responses.py`
- `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`
- `backend/alice/infrastructure/bridge/protocol/`
- `backend/alice/infrastructure/bridge/server.py`
- `frontend/src/bridge/protocol/`
- `frontend/src/bridge/client.rs`
- `protocols/bridge_schema.json`
- `backend/tests/integration/test_bridge.py`

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
- `backend/alice/application/agent/agent.py`
- `backend/alice/application/workflow/base_workflow.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/domain/llm/services/chat_service.py`
- `backend/tests/unit/test_domain/test_runtime_context_phase2.py`
- `backend/tests/integration/test_agent.py`

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
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `scripts/validate_logs.py`
- `backend/tests/integration/test_logging_e2e.py`
- `backend/tests/performance/test_log_write_speed.py`
- `docs/operations/logging/README.md`

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
