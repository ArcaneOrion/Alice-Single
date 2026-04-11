# Alice Docs

`docs/` 是本仓库的统一知识库入口。

如果你要修改代码、协议、测试或运行约束，请先从这里找主题，再进入对应专题文档，而不是直接把 `AGENTS.md`、聊天上下文或运行时目录当成权威来源。

## 如何使用
- 先按任务类型选专题。
- 再进入专题里的权威文档。
- 如果发现旧的根目录历史文档入口与 `docs/` 重复，优先删除旧入口并修正到 `docs/` 下的专题文档。
- 如果改动影响架构、协议、日志、测试入口或代码地图导航，顺手运行一次 `/code_map_team` 做 docs-first 同步。

## 按任务导航

### 想快速理解仓库结构
- [架构总览](./architecture/overview.md)
- [代码地图总览](./reference/code-map.md)
- [代码地图-结构视图](./reference/code-map-structure.md)
- [代码地图-耦合视图](./reference/code-map-coupling.md)
- [文档权威来源表](./reference/sources-of-truth.md)

### 想修改前端状态流 / TUI 事件循环
- [代码地图总览](./reference/code-map.md)
- [代码地图-结构视图](./reference/code-map-structure.md)
- [代码地图-耦合视图](./reference/code-map-coupling.md)
- `frontend/src/main.rs`
- `frontend/src/app/state.rs`
- `frontend/src/core/dispatcher.rs`
- `frontend/src/ui/screen.rs`
- `frontend/src/bridge/client.rs`

### 想修改 Bridge / 跨语言协议
- [Bridge 协议与状态流](./protocols/bridge.md)
- [代码地图-耦合视图](./reference/code-map-coupling.md)
- [架构总览](./architecture/overview.md)
- `protocols/bridge_schema.json`
- `frontend/src/bridge/`
- `backend/alice/infrastructure/bridge/`

### 想修改 Gateway / WebSocket 会话传输
- [代码地图总览](./reference/code-map.md)
- [代码地图-结构视图](./reference/code-map-structure.md)
- [代码地图-耦合视图](./reference/code-map-coupling.md)
- `backend/alice/infrastructure/gateway/`
- `backend/tests/unit/test_infrastructure/`

### 想修改应用分层或模块边界
- [架构总览](./architecture/overview.md)
- [代码地图总览](./reference/code-map.md)
- [代码地图-结构视图](./reference/code-map-structure.md)
- [代码地图-耦合视图](./reference/code-map-coupling.md)

### 想修改 Runtime Context / Tool Registry / 工具调用编排
- [代码地图总览](./reference/code-map.md)
- [代码地图-结构视图](./reference/code-map-structure.md)
- [代码地图-耦合视图](./reference/code-map-coupling.md)
- `backend/alice/application/runtime/`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/application/workflow/function_calling_orchestrator.py`
- `backend/alice/domain/llm/services/chat_service.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/domain/execution/services/tool_registry.py`

### 想修改运行时配置 / Harness / Prompt 组装
- [代码地图总览](./reference/code-map.md)
- [代码地图-结构视图](./reference/code-map-structure.md)
- [代码地图-耦合视图](./reference/code-map-coupling.md)
- [测试指南](./testing/guide.md)
- `backend/alice/core/config/settings.py`
- `backend/alice/core/config/loader.py`
- `backend/alice/core/prompts.py`
- `backend/alice/cli/bootstrap.py`
- `backend/alice/core/registry/command_registry.py`
- `backend/alice/application/services/lifecycle_service.py`
- `backend/alice/domain/execution/executors/`
- `prompts/`

### 想跑测试或补测试
- [测试指南](./testing/guide.md)
- `backend/tests/unit/test_domain/test_chat_workflow.py`
- `backend/tests/unit/test_domain/test_stream_service.py`
- `backend/tests/unit/test_domain/test_chat_service.py`
- `backend/tests/integration/test_bridge.py`
- `backend/tests/integration/test_logging_e2e.py`

### 想修改结构化日志
- [Logging 专题首页](./operations/logging/README.md)
- [Logging Schema](./operations/logging/schema.md)
- [Logging Migration Guide](./operations/logging/migration.md)
- [Logging Validation Report](./operations/logging/validation.md)

### 想确认运行时文件哪些不是设计文档
- [权威来源与运行时数据边界](./reference/sources-of-truth.md)

### 想看执行背景 / 演进计划
- `../exec/README.md`
- `../exec/harness-decoupling-context.md`
- `../exec/harness-decoupling-plan.md`

## 文档结构
```text
docs/
├── README.md
├── architecture/
│   └── overview.md
├── protocols/
│   └── bridge.md
├── testing/
│   └── guide.md
├── operations/
│   └── logging/
│       ├── README.md
│       ├── schema.md
│       ├── migration.md
│       └── validation.md
└── reference/
    ├── code-map.md
    ├── code-map-structure.md
    ├── code-map-coupling.md
    └── sources-of-truth.md

exec/
├── README.md
├── harness-decoupling-context.md
└── harness-decoupling-plan.md
```

## 文档原则
- `docs/` 是知识沉淀区。
- `docs/reference/*` 是代码地图的权威来源。
- `AGENTS.md` 只保留最小地图和操作约束。
- `.alice/`、`.alice/workspace/`、日志、缓存、coverage、build 产物是运行时数据，不是设计文档；仓库 prompt 模板在 `prompts/`，用户可编辑分片在 `.alice/prompt/*.xml`，运行时聚合文件在 `.alice/prompt/prompt.xml`。
- 代码改动如果引入新的长期知识，应优先补到 `docs/` 对应专题。
