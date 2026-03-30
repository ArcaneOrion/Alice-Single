# Structured Logging

这是结构化日志专题首页。

如果你要修改日志 schema、字段命名、事件路由、JSONL handler、兼容策略或验证流程，请从这里进入，而不是直接依赖零散代码搜索。

## 读哪篇
- 想看字段和事件规范：
  - [schema.md](./schema.md)
- 想看迁移策略和默认行为：
  - [migration.md](./migration.md)
- 想看验收标准和验证流程：
  - [validation.md](./validation.md)

## 代码与测试位置

### 实现
- `backend/alice/core/logging/adapter.py`
- `backend/alice/core/logging/configure.py`
- `backend/alice/core/logging/configure_legacy.py`
- `backend/alice/core/logging/jsonl_formatter.py`
- `backend/alice/core/logging/jsonl_logger.py`

### 验证
- `backend/tests/integration/test_logging_e2e.py`
- `backend/tests/performance/test_log_write_speed.py`
- `scripts/validate_logs.py`

## 改动提醒
- 改 schema 时，文档、实现、测试、校验脚本要一起更新。
- 改默认行为时，记得同步迁移文档。
- 改事件分类时，注意 `system/tasks/changes` 三文件路由。
