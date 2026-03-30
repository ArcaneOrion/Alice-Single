# 代码地图：结构视图

给 agent 的最小结构地图：回答“这个改动大概落在哪一层、哪个目录”。

## 仓库一级结构
- `frontend/src/`：Rust TUI。
- `backend/alice/`：Python 引擎。
- `backend/tests/`：后端测试。
- `protocols/`：跨语言协议与 schema。
- `prompts/`：prompt 资产。
- `skills/`：技能目录与 `SKILL.md`。
- `docs/`：结构化文档。

## Frontend
- `frontend/src/app/`：App 状态、常量、消息容器。
- `frontend/src/bridge/`：Bridge 客户端、协议编解码、stdio 传输。
- `frontend/src/core/`：事件分发、事件总线、键盘/鼠标处理。
- `frontend/src/ui/`：布局、组件、渲染。
- `frontend/src/util/`：辅助工具与 runtime log。

## Backend
- `backend/alice/application/`：agent、workflow、services、DTO。
- `backend/alice/domain/`：execution、llm、memory、skills 等业务逻辑。
- `backend/alice/infrastructure/`：bridge、docker、cache、logging。
- `backend/alice/core/`：config、container、event_bus、interfaces、registry。
- `backend/alice/cli/`：CLI 入口。

## 常见改动落点
- TUI 渲染或交互：`frontend/src/ui/`、`frontend/src/core/`。
- 前后端消息收发：`frontend/src/bridge/`、`backend/alice/infrastructure/bridge/`。
- Agent 编排：`backend/alice/application/`。
- 执行、记忆、技能：`backend/alice/domain/`。
- 容器、日志、配置：`backend/alice/infrastructure/`、`backend/alice/core/`。
- 协议契约：`protocols/bridge_schema.json`。

## 配套阅读
- 总览入口：`docs/reference/code-map.md`
- 联动关系：`docs/reference/code-map-coupling.md`
