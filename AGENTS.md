# AGENTS.md

本文件给通用 agent 一个最小工作地图，不做百科式说明。

## 先看哪里
- 文档入口：`docs/README.md`
- 代码地图：`docs/reference/code-map.md`
- 结构视图：`docs/reference/code-map-structure.md`
- 耦合视图：`docs/reference/code-map-coupling.md`
- 权威来源：`docs/reference/sources-of-truth.md`
- 架构总览：`docs/architecture/overview.md`
- Bridge 协议：`docs/protocols/bridge.md`
- 测试指南：`docs/testing/guide.md`

规则：需要细节时进入 `docs/`，不要把长期知识继续堆回 `AGENTS.md`。

## Repo Map
- `frontend/`：Rust TUI
- `backend/alice/`：Python 引擎
- `backend/tests/`：后端测试
- `protocols/`：协议与 schema
- `prompts/`：仓库 prompt 模板分片
- `skills/`：技能目录
- `docs/`：结构化知识库
- `.alice/`、日志、缓存、coverage、build 产物：运行时数据，不是权威来源

## 当前高耦合区域
- Bridge 协议与状态流
- Runtime Context / Request Envelope / Tool Binding
- Execution harness / executor / lifecycle 装配
- Prompt 分片、运行时聚合与 `update_prompt`
- 结构化日志 schema 与分类路由

遇到这些改动时，优先看 `docs/reference/code-map-coupling.md`。

## 最小操作约束
- 默认先读 `docs/`，再改代码
- 改代码前做针对性检查；改完后做同类验证
- 影响结构、协议、日志、测试入口或代码地图导航时，运行 `/code_map_team`
- 长期知识写入 `docs/`，不要扩写根目录文档
- 不要把 `.alice/`、memory、logs、workspace 当作设计文档

## 最小验证命令
```bash
python -m pytest backend/tests
python -m ruff check backend/alice backend/tests
python -m mypy backend/alice
cd frontend && cargo test
cd frontend && cargo clippy
cd frontend && cargo fmt --check
```
