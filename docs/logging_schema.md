# Logging Schema 说明

## 1. 目的
为了后续能够稳定解析 `system.jsonl`、`tasks.jsonl`、`changes.jsonl` 三类结构化日志，我们统一了字段约定与 event_type 枚举。即使本地开发环境只记录简单文本，也仍应在额外字段中补充最基本的 `ts`, `event_type`, `level`, `source`，以便后端、监控或分析客户端能够从 JSONL 快速构建事件视图。

## 2. 全局字段规范
### 2.1 必需字段
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ts` | ISO 8601 字符串 | 事件发生 UTC 时间戳，格式如 `2026-03-28T14:22:45Z`，用来排序与关联。 |
| `event_type` | 字符串 | 已注册的事件类型，用于指出当前条目属于哪一类行为。 |
| `level` | 字符串 | 标准日志级别（`DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL`），便于筛选与告警。 |
| `source` | 字符串 | 事件来源模块（如 `alice.core.agent`、`alice.infrastructure.bridge`），可作为 routing key。 |

### 2.2 推荐字段（可选但建议填充）
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `message` | 简洁文本 | 人类可读的事件描述，便于直接在日志聚合界面展示。 |
| `task_id` | 字符串 | 若事件属于某个任务或 workflow，使用统一 ID 进行串联。 |
| `span_id` | 字符串 | 链路追踪的 span id，可与 task_id 搭配用于序列分析。 |
| `context` | 对象 | 补充上下文标签，如 `{ "agent_version": "1.2.0", "bridge": "stdio" }`。 |
| `error` | 对象或字符串 | 仅对于异常或失败事件填写，建议包含 `message`、`code`、`stack`。 |
| `data` | 对象 | 结构化 payload，包含本次事件的详细字段，例如任务执行参数、变更 diff、性能指标等。 |

## 3. 日志文件定义与示例
每条记录均为一行合法 JSON，字段顺序可自由，但必须至少包含 `ts`, `event_type`, `level`, `source`。下面按文件分别列出 allowed event_type、描述以及典型示例。

### 3.1 system.jsonl
**用途**：记录守护进程生命周期、健康检查与系统级事件。特别关注 agent 启动、关闭、配置变更与告警。依赖者可以基于 `event_type` 构建整体状态视图。

#### event_type 枚举
- `system.start`: 服务启动完成，context 里可带版本号。
- `system.shutdown`: 服务优雅终止。
- `system.health_check`: 周期性健康探测结果，可在 `data` 中附加指标。
- `system.config_reload`: 配置热加载，`data.config_source` 说明来源。
- `system.alert`: 关键告警，`level` 通常是 `WARNING` 或更高。

#### 示例 JSONL
```json
{"ts":"2026-03-28T01:00:00Z","event_type":"system.start","level":"INFO","source":"alice.core.agent","message":"agent 启动","context":{"agent_version":"1.0.1"}}
{"ts":"2026-03-28T02:00:00Z","event_type":"system.health_check","level":"DEBUG","source":"alice.infrastructure.monitor","message":"健康探测","data":{"latency_ms":42,"cache_hit":true}}
{"ts":"2026-03-28T03:00:00Z","event_type":"system.config_reload","level":"INFO","source":"alice.core.config","message":"配置重新加载","data":{"config_source":"prompts/alice.md"}}
{"ts":"2026-03-28T04:00:00Z","event_type":"system.alert","level":"WARNING","source":"alice.core.monitor","message":"内存使用偏高","data":{"usage_ratio":0.92}}
```

### 3.2 tasks.jsonl
**用途**：聚焦每个任务及其阶段，包括调度、执行、完成和失败。推荐通过 `task_id` 与 `span_id` 追踪相关事件。

#### event_type 枚举
- `task.created`: 任务创建。
- `task.started`: 任务执行开始，`data` 可含输入参数。
- `task.progress`: 进度更新或里程碑。
- `task.completed`: 任务正常完成。
- `task.failed`: 任务失败，需在 `error` 中提供信息。

#### 示例 JSONL
```json
{"ts":"2026-03-28T05:00:00Z","event_type":"task.created","level":"INFO","source":"alice.application.services.orchestration_service","task_id":"task-123","message":"准备执行任务","data":{"intent":"write tests"}}
{"ts":"2026-03-28T05:01:00Z","event_type":"task.started","level":"INFO","source":"alice.application.agent","task_id":"task-123","span_id":"span-abc","message":"任务已启动","context":{"agent_profile":"python"}}
{"ts":"2026-03-28T05:02:00Z","event_type":"task.progress","level":"DEBUG","source":"alice.domain.execution.services.execution_service","task_id":"task-123","span_id":"span-abc","data":{"phase":"fetching"}}
{"ts":"2026-03-28T05:03:00Z","event_type":"task.completed","level":"INFO","source":"alice.application.agent","task_id":"task-123","span_id":"span-abc","message":"任务完成"}
``` 

### 3.3 changes.jsonl
**用途**：捕捉系统状态的变更，如文件写入、记忆更新、技能加载或配置调整。此类日志常被用于审计或回放。

#### event_type 枚举
- `change.file_saved`: 职能配置或 prompt 文件保存。
- `change.memory_updated`: working memory/STM/LTM 变更。
- `change.skill_loaded`: 新技能或技能版本被加载。
- `change.config_mutation`: 环境配置被修改且需持久化。
- `change.execution_plan`: 工作流执行计划或步进发生变动。

#### 示例 JSONL
```json
{"ts":"2026-03-28T06:00:00Z","event_type":"change.file_saved","level":"INFO","source":"alice.infrastructure.bridge.server","message":"prompt 写入","data":{"file_path":"prompts/alice.md","size":4096}}
{"ts":"2026-03-28T06:05:00Z","event_type":"change.memory_updated","level":"DEBUG","source":"alice.domain.memory.services","message":"STM 更新","data":{"stm_entries":5}}
{"ts":"2026-03-28T06:10:00Z","event_type":"change.skill_loaded","level":"INFO","source":"alice.domain.skills.services.skill_registry","message":"技能注册","data":{"skill_id":"toolkit-calc"}}
{"ts":"2026-03-28T06:15:00Z","event_type":"change.config_mutation","level":"WARNING","source":"alice.application.services.lifecycle_service","message":"配置切换","data":{"key":"logging.level","from":"INFO","to":"DEBUG"}}
``` 

以上示例展示了每种 JSONL 日志在真实场景下的典型字段组合。所有交付的事件都应遵循上述 `ts/event_type/level/source` 必需字段，剩余字段可根据需要填充。
