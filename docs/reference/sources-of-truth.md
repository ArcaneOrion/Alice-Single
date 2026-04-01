# 权威来源与运行时数据边界

本页定义：哪个主题看哪份文档，哪些路径只是运行时数据，不应被当成设计文档。

## 主题 -> 权威来源
- 仓库结构与改动导航：
  - `docs/reference/code-map.md`
  - `docs/reference/code-map-structure.md`
  - `docs/reference/code-map-coupling.md`
- 分层边界与依赖方向：
  - `docs/architecture/overview.md`
- Runtime Context、Tool Registry 与工具调用编排：
  - `docs/reference/code-map.md`
  - `docs/reference/code-map-structure.md`
  - `docs/reference/code-map-coupling.md`
  - `backend/alice/application/runtime/`
  - `backend/alice/application/workflow/function_calling_orchestrator.py`
  - `backend/alice/domain/execution/services/tool_registry.py`
- Bridge 协议与当前默认运行边界：
  - `docs/protocols/bridge.md`
  - `protocols/bridge_schema.json`
  - `backend/alice/application/dto/responses.py`
  - `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`
- 测试策略与运行方式：
  - `docs/testing/guide.md`
  - `backend/tests/README.md`
- 结构化日志：
  - `docs/operations/logging/README.md`
  - `docs/operations/logging/schema.md`
  - `docs/operations/logging/migration.md`
  - `docs/operations/logging/validation.md`
- 用户侧启动与交互：
  - 根目录 `README.md`

## 对代码地图的约束
- `docs/reference/*` 是代码地图的权威来源。
- agent 需要仓库结构时，优先读取 `docs/reference/code-map.md`。
- 需要目录分层时，读取 `docs/reference/code-map-structure.md`。
- 需要判断联动面与同步更新面时，读取 `docs/reference/code-map-coupling.md`。
- 若历史根目录文档与 `docs/reference/*` 不一致，优先修正 `docs/reference/*`。

## 运行时数据，不是设计文档
以下路径属于 operational data 或本地产物：

- `.alice/`
- `memory/`
- `alice_output/`
- `*.log`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `.coverage`
- `htmlcov/`
- `target/`
- `frontend/target/`
- `.venv/`

使用原则：
- 可以把它们当作调试线索。
- 不要把它们当作架构说明或协议说明。
- 如果某个运行时行为值得长期保留，请把知识写进 `docs/`，不要只留在产物里。

## 文档维护策略
- 新的长期规则、迁移说明、验证标准，优先写入 `docs/`。
- `AGENTS.md`、`CLAUDE.md` 只保留最小导航和操作约束，不扩写主题知识。
- 根目录历史文档不再作为主题权威来源；若发现旧入口残留，应直接收敛到 `docs/` 对应专题。
- 当导航或主题入口迁移到 `docs/` 后，旧入口应尽快改为指向 `docs/`，避免双份导航长期漂移。
