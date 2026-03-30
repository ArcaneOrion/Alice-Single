# AGENTS.md

## 1. 这个文件的角色
把这份文件当作目录，不要当作百科全书。

- `AGENTS.md` 只保留稳定导航、改动边界、耦合提醒、最小操作约束。
- 更深层知识应写入 `docs/`，并在这里给出入口。
- 如果发现旧导航仍指向根目录历史文档，优先收敛到 `docs/` 的专题入口，而不是在这里补充长期知识。

## 2. 先看哪里
开始任何结构性、跨模块、跨语言改动前，先定位到对应文档：

- 文档总入口：`docs/README.md`
- 仓库地图：`docs/reference/code-map.md`
- 架构边界与依赖方向：`docs/architecture/overview.md`
- Bridge 协议语义：`docs/protocols/bridge.md`
- Bridge 线级 contract：`protocols/bridge_schema.json`
- 启动方式、运行入口、用户侧行为：`README.md`
- 测试指南：`docs/testing/guide.md`
- 结构化日志专题：`docs/operations/logging/README.md`

规则：需要细节时，进入这些权威来源；不要把主题知识再抄回 `AGENTS.md`。

## 3. 知识库约定
仓库知识库以 `docs/` 为统一入口。

- `AGENTS.md` 负责告诉你去哪里找知识。
- `docs/` 负责沉淀专题知识、迁移说明、验证标准、运行约束。
- `docs/reference/sources-of-truth.md` 定义“哪个主题看哪份文档”。
- 如果本次任务产生新的长期知识，优先更新 `docs/`，而不是继续扩写 `AGENTS.md`。

## 4. Repo Map
- `frontend/`: Rust TUI frontend。主要代码在 `frontend/src/`。
- `backend/alice/`: Python backend engine。
- `protocols/`: 共享协议与 schema。
- `prompts/`: 提示词与人格资产。
- `skills/`: 内置技能与相关资源。
- `docs/`: 结构化文档知识库。
- `.alice/`、`memory/`、`alice_output/`、`*.log`、缓存、coverage、build 产物：本地运行数据，不是 source of truth。

## 5. 模块边界
后端保持既有分层，不要跨层偷连：

- `application/`: workflow、use case orchestration
- `domain/`: 核心业务能力
- `infrastructure/`: bridge、docker、cache、logging 等适配器
- `core/`: config、DI、interfaces、event bus、共享框架能力

前端保持既有模块分工：

- `app/`: 状态与消息流
- `bridge/`: 后端通信、协议、传输
- `core/`: dispatcher、event、input handler
- `ui/`: 渲染与组件
- `frontend/src/main.rs`: 仅做组合与启动入口，不继续堆业务逻辑

优先扩展现有子包，不要随意新增顶层目录或新的 `misc` 式模块。

## 6. 高耦合区域
这些地方改动时，默认按“多文件联动”处理：

- Bridge protocol 是双端契约。改消息结构、字段名、状态值、序列化格式时，要同步更新：
  - `frontend/src/bridge/protocol/`
  - `backend/alice/infrastructure/bridge/protocol/`
  - `protocols/bridge_schema.json`
  - `docs/protocols/bridge.md`
- Bridge transport / control flow 改动通常还会触达：
  - `frontend/src/bridge/client.rs`
  - `frontend/src/bridge/transport/`
  - `backend/alice/infrastructure/bridge/server.py`
  - `backend/alice/infrastructure/bridge/transport/`
  - `backend/alice/infrastructure/bridge/event_handlers/`
- Frontend message/status 流改动通常还要检查：
  - `frontend/src/app/state.rs`
  - `frontend/src/core/dispatcher.rs`
- Structured logging 属于横切关注点；改 schema、字段命名、路由或校验逻辑前，先读 `docs/operations/logging/README.md`。

## 7. 构建与验证
基础环境：

- Python `>=3.11`
- Rust toolchain：见 `frontend/Cargo.toml`

常用命令：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e 'backend[dev]'
cd frontend && cargo run --release
```

最小验证集合：

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

## 8. 编辑约束
- Python: 4 空格缩进、`snake_case`、显式类型标注；新代码默认满足 strict `mypy`。
- Rust: 遵循 `cargo fmt`；模块/函数 `snake_case`，结构体/枚举 `CamelCase`。
- 优先复用现有模块，避免无边界的新抽象。
- 修改 protocol、prompt、config、logging 这类高影响文件时，保持改动最小，并在总结中明确标出。
- 如果任务引入新的长期知识或操作规则，把内容沉淀到 `docs/`，这里只保留入口。

## 9. 测试与文档更新规则
- 后端功能改动，优先补或更新 unit tests。
- 影响 bridge、Docker execution、workflow orchestration、跨子系统边界时，补 integration coverage。
- 影响日志 schema 或验证流程时，同步更新 `docs/` 与相关测试/脚本。
- 如果发现导航文档与真实代码不一致，优先修正对应的 `docs/` 权威入口，不要靠 `AGENTS.md` 打补丁。

## 10. 安全与提交
- 不要提交 `.env`、API keys、日志、memory/state 文件、缓存、coverage、构建产物。
- 配置模板参考 `.env.example`；真实 secrets 只保存在本地 `.env`。
- Commit message 使用 Conventional Commits，例如 `feat:`、`fix:`、`refactor:`、`chore:`。
- 单次提交尽量聚焦一个 feature、一个 layer 或一个连贯 refactor。
