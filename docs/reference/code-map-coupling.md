# 代码地图：耦合视图

给 agent 的最小耦合地图：回答“改这里通常还要一起看哪些地方”。

## Bridge 协议
通常联动：
- `frontend/src/bridge/protocol/`
- `frontend/src/bridge/client.rs`
- `backend/alice/infrastructure/bridge/protocol/`
- `backend/alice/infrastructure/bridge/server.py`
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
- `backend/alice/application/workflow/`
- `backend/tests/integration/test_agent.py`

## 结构化日志
通常联动：
- `backend/alice/core/logging/`
- `scripts/validate_logs.py`
- `backend/tests/integration/test_logging_e2e.py`
- `backend/tests/performance/test_log_write_speed.py`
- `docs/operations/logging/README.md`

## 技能系统
通常联动：
- `skills/`
- `backend/alice/domain/skills/`
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
