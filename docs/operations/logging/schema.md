# Logging Schema 说明（v2）

## 1. 目标
日志核心层统一支持：

- 三文件路由：`system.jsonl`、`tasks.jsonl`、`changes.jsonl`
- 完整载荷采集（默认开启 thinking/API/tool 全量）
- 最少脱敏（默认仅脱敏敏感凭据键）
- 点号风格 `event_type`

## 2. 全局字段规范

### 2.1 必需字段
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ts` | ISO 8601 字符串 | UTC 时间戳，例如 `2026-03-28T14:22:45Z`。 |
| `event_type` | 字符串 | 事件类型，必须使用点号风格（如 `task.started`）。 |
| `level` | 字符串 | 标准日志级别。 |
| `source` | 字符串 | 来源模块名。 |

### 2.2 推荐字段（统一命名）
以下字段是跨模块推荐命名，不再引入平行命名：

- `trace_id`
- `request_id`
- `task_id`
- `session_id`
- `span_id`
- `component`
- `phase`
- `timing`
- `payload_kind`
- `context`
- `data`
- `error`

## 3. 三文件路由规则

- `system.jsonl`: 系统生命周期、健康检查、告警、无法归类事件。
- `tasks.jsonl`: `task/workflow/api/model/bridge/executor/tool/llm/iteration/interrupt` 相关事件。
- `changes.jsonl`: `change/memory/skill/config` 相关事件。

路由优先依据 `event_type` 根段（点号前第一段），其次参考 `log_category`，最终回退到 `system`。

## 4. 事件族（event families）

### 4.1 system.jsonl
- `system.start`
- `system.shutdown`
- `system.health_check`
- `system.config_reload`
- `system.alert`

### 4.2 tasks.jsonl
- `task.created`
- `task.started`
- `task.progress`
- `task.completed`
- `task.failed`
- `api.request`
- `api.response`
- `api.retry`
- `api.error`
- `model.prompt_built`
- `model.stream_chunk`
- `model.stream_completed`
- `model.tool_decision`
- `bridge.message_sent`
- `bridge.message_received`
- `workflow.state_transition`
- `executor.command_prepared`
- `executor.command_result`

### 4.3 changes.jsonl
- `change.file_saved`
- `change.memory_updated`
- `change.skill_loaded`
- `change.config_mutation`
- `change.execution_plan`

## 5. 示例

```json
{"ts":"2026-03-28T09:00:00Z","event_type":"api.request","level":"INFO","source":"alice.domain.llm","trace_id":"tr-1","request_id":"req-1","task_id":"task-9","session_id":"sess-1","span_id":"span-1","component":"openai.client","phase":"send","payload_kind":"http","context":{"provider":"openai"},"data":{"method":"POST","url":"https://api.openai.com/v1/responses"}}
{"ts":"2026-03-28T09:00:01Z","event_type":"model.stream_chunk","level":"DEBUG","source":"alice.domain.llm","trace_id":"tr-1","request_id":"req-1","task_id":"task-9","phase":"stream","timing":{"elapsed_ms":120},"payload_kind":"model_output","data":{"chunk":"..."}}
{"ts":"2026-03-28T09:00:02Z","event_type":"change.file_saved","level":"INFO","source":"alice.infrastructure.bridge","task_id":"task-9","component":"workspace.writer","payload_kind":"file_change","data":{"path":"prompts/alice.md","bytes":2048}}
```
