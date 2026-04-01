# 代码地图总览

> 同步时间：2026-04-01
>
> 同步基线 commit：4d37cb1
>
> 维护规则：先更新 `docs/reference/*`，再在代码结构、专题导航或高耦合区域变更后同步本页；若结构视图与耦合视图不一致，以实际代码与对应专题文档为准，并尽快回补。

本页给 agent 一个最短入口：先定位改动大致落点，再判断要继续看结构视图还是耦合视图。

## 推荐阅读顺序
1. 先看本页，确定主题与目录层级。
2. 需要看目录/分层时，转到 [code-map-structure.md](./code-map-structure.md)。
3. 需要看联动面/同步更新面时，转到 [code-map-coupling.md](./code-map-coupling.md)。
4. 需要确认文档权威性时，转到 [sources-of-truth.md](./sources-of-truth.md)。

## 一级结构
- `frontend/src/`：Rust TUI，负责界面、交互、事件分发、Bridge 客户端。
- `backend/alice/`：Python 引擎，负责 agent、workflow、memory、tool execution，以及 canonical runtime -> legacy bridge 输出。
- `backend/tests/`：后端测试，含 unit / integration / performance。
- `protocols/`：共享协议与 schema。
- `prompts/`：系统提示词与 prompt 资产。
- `skills/`：技能资源与 `SKILL.md`。
- `docs/`：面向 agent 的结构化知识库。

## 任务到区域
- UI / 交互问题：优先看 `frontend/src/app/`、`frontend/src/core/`、`frontend/src/ui/`。
- Bridge / 流式消息：优先看 `backend/alice/cli/`、`backend/alice/application/dto/`、`backend/alice/infrastructure/bridge/`、`frontend/src/bridge/`、`protocols/`。
- Agent 工作流：优先看 `backend/alice/application/`、`backend/alice/domain/`。
- Runtime Context / Tool Registry / 工具调用编排：优先看 `backend/alice/application/runtime/`、`backend/alice/application/agent/`、`backend/alice/application/workflow/`、`backend/alice/domain/execution/services/`、`backend/alice/domain/llm/services/`。
- 配置 / 容器 / 日志：优先看 `backend/alice/core/`、`backend/alice/infrastructure/`、`docs/operations/logging/`。
- 技能系统：优先看 `skills/`、`backend/alice/domain/skills/`。
- 测试补齐：优先看 `backend/tests/` 与对应实现目录，phase-2 最小入口是 `backend/tests/unit/test_domain/test_runtime_context_phase2.py`。

## 快速决策
- 只想知道目录怎么分：看 [code-map-structure.md](./code-map-structure.md)。
- 想知道“改这里还要改哪”：看 [code-map-coupling.md](./code-map-coupling.md)。
- 想知道哪个文档可信：看 [sources-of-truth.md](./sources-of-truth.md)。
