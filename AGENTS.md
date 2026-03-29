# Agent 执行手册

## 仓库定位
本仓库是一个 **Rust TUI frontend + Python backend engine + bridge protocol + Docker sandbox** 系统。
默认工作原则：保持分层边界，保持跨语言协议同步，把运行时状态视为本地产物而不是设计文档。

## 优先阅读
在做结构性改动、跨模块改动或协议改动前，先看这些文件：

- `CODE_MAP.md`：最快的代码地图，适合先判断改动边界和耦合点
- `ARCHITECTURE.md`：分层职责和依赖方向
- `API.md`：bridge protocol 与 DTO contract
- `README.md`：启动流程、memory model、内置命令
- `backend/tests/README.md`：测试布局与 marker 约定

## Repo Map
- `backend/alice/`：Python backend，按 `application/`、`domain/`、`infrastructure/`、`core/` 分层
- `frontend/src/`：Rust frontend，按 `app/`、`bridge/`、`core/`、`ui/`、`util/` 组织
- `backend/tests/`：后端测试，包含 `unit/`、`integration/`、`performance/`，共享夹具在 `fixtures/`
- `protocols/`：共享协议与 schema；bridge 相关改动通常会触达这里
- `prompts/`：人格与提示词资产
- `skills/`：内置技能定义与相关资源
- `docs/`：迁移、日志、验证与补充工程文档
- `.alice/`、`alice_output/`、日志、memory 类运行时文件：本地运行产物，不是 source of truth

## 架构约束
- 后端代码应保持在既有分层模型内：
  `application` 负责 workflow / use case orchestration，
  `domain` 负责核心业务能力，
  `infrastructure` 负责适配器与外部集成，
  `core` 负责共享框架能力。
- 不要为了方便跨层直连。新增代码应遵守现有依赖方向，而不是绕过层次边界。
- 优先扩展现有子包，不要随意新增顶层目录或新的“杂项模块”。
- 前端改动应留在现有模块边界内：
  `app` 管状态与消息流，
  `bridge` 管后端通信，
  `core` 管 dispatcher / event / input handler，
  `ui` 管渲染与组件。
- 不要继续把逻辑堆进 `frontend/src/main.rs`；该文件应保持为组合与启动入口。

## 高耦合区域
- **Bridge protocol 是双端契约。** 只要修改消息结构、字段语义或状态流转，就必须同步更新 Rust 和 Python 两端实现。
- Bridge 相关改动通常至少涉及：
  `frontend/src/bridge/protocol/`
  `frontend/src/bridge/transport/`
  `backend/alice/infrastructure/bridge/protocol/`
  `backend/alice/infrastructure/bridge/transport/`
  `protocols/bridge_schema.json`
- Structured logging 也是横切关注点。修改日志 schema、字段命名或校验流程前，先看 `docs/` 中相关说明。
- 运行时状态目录和文件是 operational data，不要把它们当作权威架构说明。

## 构建与测试
后端使用 **Python 3.11+**，前端使用 **Rust/Cargo**。

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e 'backend[dev]'
cd frontend && cargo run --release
```

常用校验命令：

```bash
python -m pytest backend/tests
python -m ruff check backend/alice backend/tests
python -m mypy backend/alice
cd frontend && cargo test
cd frontend && cargo clippy
cd frontend && cargo fmt --check
```

常用定向测试：

```bash
pytest -m unit
pytest -m integration
pytest -m "not slow"
```

## 编辑规则
- Python 使用 4 空格缩进、`snake_case`、显式类型标注；新代码默认要满足 strict `mypy`。
- Ruff 配置集中在 `backend/pyproject.toml`，导入顺序和 lint 行为应与现有配置一致。
- Rust 遵循标准 `cargo fmt` 风格；模块/函数使用 `snake_case`，结构体/枚举使用 `CamelCase`。
- 优先复用现有模块，再考虑新增文件；只有在边界清晰且有明确架构理由时才引入新抽象。
- 修改 protocol、prompt、config 这类高影响文件时，保持改动最小化，并在总结或 PR 中明确标出。

## 测试要求
- 测试文件命名使用 `test_*.py`，测试类使用 `Test*`，测试函数使用 `test_*`。
- 集成测试和慢测试要显式添加 `@pytest.mark.integration`、`@pytest.mark.slow`。
- 后端功能改动通常优先补或更新 unit tests。
- 如果改动影响 bridge communication、Docker execution、workflow orchestration 或其他跨子系统边界，补 integration coverage。
- 如果改动影响吞吐、时延或重执行路径，检查是否需要更新 `backend/tests/performance/`。

## 安全与配置
- 不要提交 `.env`、API keys、日志、运行时 memory/state 文件或其他本地产物。
- 配置模板参考 `.env.example`；真实 secrets 只保存在本地 `.env`。
- `memory/` 以及类似运行时状态目录默认视为本地 operational data，除非任务明确要求处理它们。

## Commit 与 PR 约定
- 提交信息遵循 **Conventional Commits**，例如 `feat: ...`、`fix: ...`、`refactor: ...`、`chore: ...`。
- 单次提交尽量聚焦一个 feature、一个 layer 或一个连贯的 refactor。
- PR 至少应说明：
  改了什么，
  关联 issue / task，
  跑了哪些验证命令，
  TUI 改动的截图或终端录屏，
  以及 protocol / config / prompt 改动的单独说明。
