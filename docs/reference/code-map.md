# 代码地图总览

> 同步时间：2026-04-07
>
> 同步基线 commit：24e8f03
>
> 维护规则：先更新 `docs/reference/*`，再在代码结构、专题导航或高耦合区域变更后同步本页；若结构视图与耦合视图不一致，以实际代码与对应专题文档为准，并尽快回补。

本页给 agent 一个最短入口：先定位改动大致落点，再判断要继续看结构视图还是耦合视图。

## 推荐阅读顺序
1. 先看本页，确定主题与目录层级。
2. 需要看目录/分层时，转到 [code-map-structure.md](./code-map-structure.md)。
3. 需要看联动面/同步更新面时，转到 [code-map-coupling.md](./code-map-coupling.md)。
4. 需要确认文档权威性时，转到 [sources-of-truth.md](./sources-of-truth.md)。

## 一级结构
- `frontend/src/`：Rust TUI，负责界面、交互、事件分发、Bridge 客户端与 stdio 传输。
- `backend/alice/`：Python 引擎，负责 agent、workflow、memory、tool execution，以及 canonical runtime context / request envelope -> legacy bridge compatibility 输出；当前树里也已包含 gateway/websocket transport 适配层。
- `backend/alice/cli/bootstrap.py`：CLI runtime scaffold 与启动装配入口，负责补齐 `.alice/config.json`、`.alice/prompt/*.xml`、`.alice/prompt/prompt.xml`、`.alice/memory/*`，并把 `Settings` 装配为 orchestration / lifecycle / workflow。
- `backend/alice/domain/execution/`：执行域；当前默认通过 `core/registry/command_registry.py` 选择 `container` harness，并装配到 `docker_executor.py` / `DockerExecutionBackend`，`local_process_executor.py` 保留给单进程 runtime 场景。
- `backend/tests/`：后端测试，含 unit / integration / performance。
- `protocols/`：共享协议与 schema。
- `.alice/`：运行时配置与产物目录，默认包含唯一运行时配置源 `.alice/config.json`，以及 prompt、memory、logs、workspace 等运行时文件；首次 CLI 启动会幂等补齐该目录，其中仓库 `prompts/01_identity.xml` 到 `prompts/05_output.xml` 会复制到 `.alice/prompt/`，再组装为 `.alice/prompt/prompt.xml`。
- `prompts/`：XML prompt 默认模板；`01_identity.xml` 到 `05_output.xml` 会在首次启动时复制到 `.alice/prompt/`，供用户编辑。
- `docs/`：面向 agent 的结构化知识库。

## 任务到区域
- UI / 交互问题：优先看 `frontend/src/main.rs`、`frontend/src/app/`、`frontend/src/core/dispatcher.rs`、`frontend/src/ui/screen.rs`、`frontend/src/ui/`。
- Bridge / 流式消息：优先看 `backend/alice/cli/`、`backend/alice/infrastructure/bridge/`（尤其 `legacy_compatibility_serializer.py` / `server.py`）、`frontend/src/bridge/`、`frontend/src/core/dispatcher.rs`、`protocols/`。
- Gateway / WebSocket 会话传输：优先看 `backend/alice/infrastructure/gateway/`、`backend/tests/unit/test_infrastructure/`，以及 canonical runtime event / request interrupt / replay 相关路径。
- Agent 工作流：优先看 `backend/alice/application/workflow/`、`backend/alice/domain/llm/services/`、`backend/alice/application/agent/`。
- Runtime Context / Request Envelope / Model-visible Context / Tool Binding：优先看 `backend/alice/application/runtime/`、`backend/alice/application/workflow/`、`backend/alice/domain/llm/services/`、`backend/alice/domain/execution/services/`。
- 配置 / 容器 / 日志：优先看 `backend/alice/core/`（尤其 `config/`、`logging/configure.py`）、`backend/alice/cli/bootstrap.py`、`backend/alice/infrastructure/`、`docs/operations/logging/`。
- 运行时配置 / Harness / Prompt 组装：优先看 `backend/alice/core/config/`、`backend/alice/core/registry/command_registry.py`、`backend/alice/cli/bootstrap.py`、`backend/alice/application/services/lifecycle_service.py`、`backend/alice/domain/execution/executors/`、`prompts/`。
- 技能系统：优先看 `skills/`、`backend/alice/domain/skills/`。
- 测试补齐：优先看 `backend/tests/` 与对应实现目录；当前最小主回归入口是 `backend/tests/unit/test_domain/test_chat_workflow.py`、`backend/tests/unit/test_domain/test_stream_service.py`、`backend/tests/unit/test_domain/test_chat_service.py`、`backend/tests/integration/test_bridge.py`、`backend/tests/integration/test_logging_e2e.py`。

## 快速决策
- 只想知道目录怎么分：看 [code-map-structure.md](./code-map-structure.md)。
- 想知道“改这里还要改哪”：看 [code-map-coupling.md](./code-map-coupling.md)。
- 想知道哪个文档可信：看 [sources-of-truth.md](./sources-of-truth.md)。
