# Structured Logging

这是结构化日志专题首页。

如果你要修改日志 schema、字段命名、事件路由、JSONL handler、兼容策略或验证流程，请从这里进入，而不是直接依赖零散代码搜索。

## 先记住当前关注面

当前 logging 不只是记录旧式 `llm_call/llm_response`。在 backend runtime 与 function-calling 主链路里，更关键的是：
- 流式模型事件
- 工具决策与执行事件
- workflow 状态迁移事件
- legacy compatibility 相关字段

这些事件主要进入 `.alice/logs/tasks.jsonl`，用于串起一次请求从模型流式输出、工具决策、执行，到最终 bridge 输出的全过程。

## 读哪篇
- 想看字段和事件规范：
  - [schema.md](./schema.md)
- 想看迁移策略和默认行为：
  - [migration.md](./migration.md)
- 想看验收标准和验证流程：
  - [validation.md](./validation.md)

## 当前关键事件族

### 模型流式事件
常见事件名：
- `model.stream_started`
- `model.stream_chunk`
- `model.tool_decision`
- `model.stream_completed`

典型用途：
- 记录一次 streaming request 的开始/结束
- 记录 chunk 级增量输出
- 记录模型是否决定发起 tool call
- 记录最终 usage、聚合后的 tool call 状态

### workflow / executor 事件
常见事件名：
- `workflow.state_transition`
- `executor.command_prepared`
- `executor.command_result`

典型用途：
- 记录 runtime 状态迁移
- 记录工具执行前的标准化命令/路由决策
- 记录执行结果、退出码、错误与输出摘要

### bridge / compatibility 相关事件
当前 frontend 仍消费 legacy wire，因此日志里需要能同时追踪：
- 内部 canonical runtime event
- 对外 legacy event / legacy status 的投影

兼容相关字段至少要关注：
- `legacy_event_type`
- `tool_calls_delta`
- `tool_calls_aggregated`

含义：
- `legacy_event_type`: 当前记录最终映射到旧协议时使用的事件/类型语义，便于核对兼容层是否回退
- `tool_calls_delta`: 当前 chunk 级别新增的 tool call 增量
- `tool_calls_aggregated`: 流式聚合后当前已知的完整 tool call 状态

## 日志路由

当前 JSONL handler 会按 category 将记录拆到不同文件：
- `system.jsonl`
- `tasks.jsonl`
- `changes.jsonl`

与 runtime / function-calling 最相关的是：
- `tasks.jsonl`

这里通常承载：
- `task.*`
- `model.*`
- `api.*`
- `workflow.*`
- `executor.*`
- 部分 bridge/runtime 投影相关事件

## 代码与测试位置

### 实现
- `backend/alice/core/logging/adapter.py`
- `backend/alice/core/logging/configure.py`
- `backend/alice/core/logging/configure_legacy.py`
- `backend/alice/core/logging/jsonl_formatter.py`
- `backend/alice/core/logging/jsonl_logger.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/domain/execution/services/execution_service.py`

### 验证
- `backend/tests/integration/test_logging_e2e.py`
- `backend/tests/performance/test_log_write_speed.py`
- `scripts/validate_logs.py`

## 当前最小验证

修改 logging schema、事件名、字段或 runtime/function-calling observability 时，至少运行：

```bash
python -m pytest backend/tests/integration/test_logging_e2e.py
python -m pytest backend/tests/integration/test_agent.py
python -m pytest backend/tests/integration/test_bridge.py
```

建议同时人工检查生成的 JSONL：
- 是否落到预期文件
- 是否保留 `ts`、`event_type`、`level`、`source`
- `context.task_id` / `context.request_id` / `context.trace_id` 是否连续
- tool calling 相关字段是否仍可用于串联一次执行链路

## 改动提醒
- 改 schema 时，文档、实现、测试、校验脚本要一起更新。
- 改默认行为时，记得同步迁移文档。
- 改事件分类时，注意 `system/tasks/changes` 三文件路由。
- 改 function-calling 或 runtime event 但不改 wire contract 时，也要检查 logging 字段是否还能解释 legacy compatibility。
