# Structured Logging 迁移指南

## 1. 目标
日志系统升级为三类结构化 JSONL 日志，并保持 legacy 双写兼容：

- `.alice/logs/system.jsonl`
- `.alice/logs/tasks.jsonl`
- `.alice/logs/changes.jsonl`

核心升级点：

- 事件名统一点号风格（`event_type`）
- 统一推荐字段命名：`trace_id/request_id/task_id/session_id/span_id/component/phase/timing/payload_kind/context/data/error`
- 默认完整载荷 + 最少脱敏

## 2. 默认行为
初始化 `configure_logging(settings.logging)` 后：

- 控制台继续输出可读文本日志。
- 默认继续写 legacy 文本日志 `alice_runtime.log`。
- 同时按 `event_type/log_category` 路由写入 `.alice/logs/*.jsonl`（system/tasks/changes）。
- 若目标日志目录缺少 `schema_version.json`，初始化时会自动补齐一个最小 schema 文件。

## 3. 回退开关
若需要快速回退到旧系统，可使用：

```bash
USE_LEGACY_LOGGING=true
```

回退后：

- 只启用 legacy 文本日志链路。
- `configure_legacy.py` 中的滚动文本日志配置继续生效。

## 4. 渐进式接入方式

### 4.1 完全不改调用点
已有代码继续使用：

```python
import logging

logger = logging.getLogger(__name__)
logger.info("something happened")
```

这种情况下：

- 不会破坏旧行为；
- JSONL 中默认会规范化为点号风格 `event_type`（如 `system.log` / `task.start`）；
- 默认归入 `system.jsonl`。

### 4.2 推荐的新写法
新增代码建议使用：

```python
from backend.alice.core.logging import get_structured_logger

logger = get_structured_logger(__name__, category="tasks")
logger.event(
    "workflow.state_transition",
    "Task started",
    trace_id="tr-001",
    request_id="req-001",
    task_id="task-123",
    session_id="session-001",
    span_id="span-001",
    component="orchestrator",
    phase="bootstrap",
    timing={"elapsed_ms": 12},
    payload_kind="workflow_state",
    context={"agent_version": "2.0.0"},
    data={"from": "queued", "to": "running"},
)
```

或使用标准 `logging` 的 `extra`：

```python
logger.info(
    "API request sent",
    extra={
        "event_type": "api.request",
        "log_category": "tasks",
        "trace_id": "tr-001",
        "request_id": "req-001",
        "task_id": "task-123",
        "session_id": "session-001",
        "span_id": "span-002",
        "component": "openai.client",
        "phase": "send",
        "payload_kind": "http",
        "data": {"method": "POST"},
    },
)
```

## 5. 字段约定
结构化字段以 `docs/logging_schema.md` 和 `.alice/logs/schema_version.json` 为准。

必需字段：

- `ts`
- `event_type`
- `level`
- `source`

常用扩展字段：

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

## 6. 详细度与脱敏配置
`[logging]` 新增配置（默认值为“完整载荷 + 最少脱敏”）：

- `payload_depth = -1`
- `redaction_policy = "minimal"`（可选：`none`、`minimal`、`strict`）
- `capture_thinking = true`
- `capture_api_headers = true`
- `capture_api_bodies = true`
- `capture_tool_io = true`
- `max_field_length = 0`（0 表示不截断）

## 7. 分类规则
运行时会把日志归到三类文件：

- `system`: 启停、桥接、通用运行日志
- `tasks`: task/workflow/api/model/bridge/executor/llm/tool/interrupt 相关事件
- `changes`: 文件、配置、记忆、技能等变更事件

如果调用侧没有显式指定类别，系统会根据 `event_type` 或 `log_category` 自动归类；仍无法判断时，默认进入 `system.jsonl`。

## 8. 验证方式
推荐在迁移后执行：

```bash
python -m pytest backend/tests/unit/test_core/test_logging_schema.py
python -m pytest backend/tests/unit/test_core/test_jsonl_logger.py
python -m pytest backend/tests/integration/test_logging_e2e.py
python -m pytest backend/tests/performance/test_log_write_speed.py
python scripts/validate_logs.py .alice/logs/system.jsonl .alice/logs/tasks.jsonl .alice/logs/changes.jsonl
```

## 9. 已知限制
- 当前实现在线程内安全，使用 `RLock + O_APPEND` 追加写入。
- 多进程同时滚动时仍是 best-effort，不提供跨进程文件锁保证。
- 若调用方完全不传结构化字段，事件仍可记录，但可检索性会弱于推荐写法。
