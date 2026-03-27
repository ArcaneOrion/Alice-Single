# Repository Guidelines

## 项目结构与模块组织
本仓库采用 Python 后端 + Rust 前端的双端结构。后端代码位于 `backend/alice/`，按 `application/`、`domain/`、`infrastructure/`、`core/` 分层组织。前端代码位于 `frontend/src/`，主要模块包括 `app/`、`bridge/`、`core/` 和 `ui/`。测试集中在 `backend/tests/`，其中 `unit/` 和 `integration/` 分别放单元测试与集成测试，共享夹具放在 `fixtures/`。资源与运行时相关目录包括 `assets/`、`prompts/`、`protocols/`、`skills/`、`memory/` 和 `alice_output/`。

## 构建、测试与开发命令
进行后端开发时，建议使用 Python 3.11+ 虚拟环境。

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
cd frontend && cargo test && cargo clippy && cargo fmt --check
```

按需执行测试时，可使用 `pytest -m unit`、`pytest -m integration` 或 `pytest -m "not slow"`。

## 代码风格与命名约定
Python 使用 4 空格缩进，模块、函数、变量统一采用 `snake_case`，新增后端代码应补齐类型注解，因为 `mypy` 以严格模式运行。Ruff 已启用导入排序和常见正确性检查，单行长度尽量控制在 100 个字符附近。

Rust 代码遵循标准 Cargo 格式化规范，模块和函数使用 `snake_case`，结构体和枚举使用 `CamelCase`。UI、bridge 和事件处理逻辑优先放在现有前端子模块中，不要继续把逻辑堆进 `main.rs`。

## 测试规范
Python 测试文件命名为 `test_*.py`，测试类命名为 `Test*`，测试函数命名为 `test_*`。慢测试或集成测试请显式添加 `@pytest.mark.slow` 或 `@pytest.mark.integration`。新增后端功能优先补单元测试；如果改动涉及 bridge、Docker 或工作流编排，再补对应集成测试。

## 提交与 Pull Request 规范
最近提交历史基本遵循 Conventional Commit 风格，例如 `feat: ...`、`refactor: ...`、`chore: ...`，后续请保持一致。示例：`feat: define bridge protocol schema`。单次提交尽量聚焦一个层级或一个功能点。

PR 需要包含简要说明、关联 issue 或任务、已执行的验证命令；如果修改了 TUI，请附截图或终端录屏。凡是涉及配置、协议或 prompt 的改动，都应在描述中单独标出，因为这类变更会同时影响运行行为和开发流程。

## 安全与配置提示
不要提交 `.env`、日志文件或运行时记忆文件。必需环境变量请参考 `.env.example`，真实 API Key 只保存在本地 `.env` 中。`memory/` 应视为本地运行状态，而不是需要纳入版本管理的文档内容。
