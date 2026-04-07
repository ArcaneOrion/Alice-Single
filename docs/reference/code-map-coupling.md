# 代码地图：耦合视图

给 agent 的最小耦合地图：回答“改这里通常还要一起看哪些地方”。

## Bridge 协议
通常联动：
- `backend/alice/cli/main.py`
- `backend/alice/application/dto/responses.py`
- `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`
- `backend/alice/infrastructure/bridge/protocol/`
- `backend/alice/infrastructure/bridge/server.py`
- `backend/alice/infrastructure/bridge/__init__.py`
- `backend/alice/core/logging/configure.py`
- `frontend/src/bridge/client.rs`
- `frontend/src/bridge/transport/stdio_transport.rs`
- `frontend/src/core/dispatcher.rs`
- `frontend/src/bridge/protocol/`
- `protocols/bridge_schema.json`
- `backend/tests/integration/test_bridge.py`
- `backend/tests/integration/test_logging_e2e.py`
- `backend/tests/unit/test_core/test_logging_schema.py`

当前边界：
- `bridge/server.py` 是 legacy bridge 兼容薄壳，正式输出应统一经过 compatibility serializer。
- `legacy_compatibility_serializer.py` 是 canonical/internal runtime event -> legacy message 的显式 compatibility 边界，并记录 `bridge.compatibility_serializer_used` / `bridge.event_dropped_by_legacy_projection` 两类日志事件。
- 旧协议无法表达的 canonical event 会被显式丢弃并记日志，而不是继续扩展 legacy 顶层消息类型。
- `StreamManager` 已不是 `BridgeServer` 构造参数，也不是 `bridge` 包级正式导出；若修改其行为，至少联动 `backend/tests/unit/test_core/test_stream_manager.py`。
- 如果改 legacy projection，不要只看 bridge 目录；还要同步核对 frontend bridge client / dispatcher、logging schema、bridge integration test 与 logging e2e。

## Execution Harness / 双后端装配
通常联动：
- `backend/alice/core/config/settings.py`
- `backend/alice/core/config/loader.py`
- `backend/alice/core/registry/command_registry.py`
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/application/services/lifecycle_service.py`
- `backend/alice/domain/execution/executors/local_process_executor.py`
- `backend/alice/domain/execution/executors/docker_executor.py`
- `backend/alice/domain/execution/models/command.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `backend/tests/unit/test_core/test_command_registry.py`
- `backend/tests/unit/test_application/test_lifecycle_service.py`
- `backend/tests/unit/test_domain/test_local_process_executor.py`

当前边界：
- 当前默认通过 `Settings.harness.name -> CommandRegistry.create_harness()` 选择 execution harness，主路径是 `container` harness + `DockerExecutor` / `DockerExecutionBackend`；`local_process_executor.py` 保留给单进程 runtime 场景。
- `ExecutionService` 与 `LifecycleService` 都依赖同一个 `HarnessBundle`，因此修改默认 backend、环境名或 readiness 语义时，不能只看 executor。
- `Command.environment` / tool metadata / executor `environment_name` 需要保持一致，否则日志、tool result metadata 与测试断言会漂移。
- `backend/alice/core/config/settings.py` 与 `backend/alice/infrastructure/docker/config.py` 都定义了 `DockerConfig`，前者偏用户配置，后者偏运行时容器模型；修改 Docker 相关字段时要确认改的是哪一层。

## Bridge compatibility logging
通常联动：
- `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`
- `backend/alice/core/logging/configure.py`
- `backend/tests/integration/test_bridge.py`
- `backend/tests/integration/test_logging_e2e.py`
- `backend/tests/unit/test_core/test_logging_schema.py`
- `docs/operations/logging/README.md`

当前边界：
- `bridge.compatibility_serializer_used` 与 `bridge.event_dropped_by_legacy_projection` 属于 `tasks` 类别，而不是 `system` / `changes`。
- 修改 canonical event 到 legacy message 的映射时，必须同步看 serializer、日志 schema、测试与 logging 文档。

## 前端状态流
通常联动：
- `frontend/src/main.rs`
- `frontend/src/app/state.rs`
- `frontend/src/app/constants.rs`
- `frontend/src/core/dispatcher.rs`
- `frontend/src/core/event/types.rs`
- `frontend/src/ui/screen.rs`
- `frontend/src/ui/component/`
- `frontend/src/bridge/client.rs`
- `frontend/src/bridge/transport/stdio_transport.rs`

当前边界：
- `App` 是前端单一运行时状态容器，持有消息、状态、滚动、token、布局边界与 `BridgeClient`。
- `EventDispatcher` 负责把 `BridgeMessage`、键盘和鼠标动作映射回 `App` 状态；`Status/Thinking/Content/Tokens/Error` 的处理集中在这里。
- `render_app()` 会把真实组件布局与滚动状态回写到 `App`，因此改 UI 布局通常要同步看 `screen.rs`、`state.rs` 与鼠标区域更新。
- stderr 是否向用户暴露，不只看 bridge；还要同步看 `dispatcher.rs` 的 actionable error 过滤规则。

## Agent 工作流
通常联动：
- `backend/alice/application/agent/`
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/application/workflow/`
- `backend/alice/domain/llm/services/chat_service.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `backend/tests/integration/test_agent.py`

当前边界：
- `chat_workflow.py` 已是 canonical runtime event 与 tool loop 编排中心，不再只是普通 chat workflow。
- `ChatWorkflow`、`ChatService`、`StreamService` 之间存在同一条主链：请求装配 -> provider 调用 -> runtime event / tool call 聚合 -> workflow 输出。
- 若改 workflow 状态、tool loop、provider metadata 或 message 完成语义，至少同步看 `test_chat_workflow.py`、`test_stream_service.py`、`test_agent.py`、`test_logging_e2e.py`。

## Runtime Context 管线
通常联动：
- `backend/alice/application/runtime/`
- `backend/alice/application/__init__.py`
- `backend/alice/application/agent/agent.py`
- `backend/alice/application/workflow/base_workflow.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/domain/llm/services/chat_service.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/domain/llm/providers/base.py`
- `backend/tests/unit/test_application/test_application_lazy_exports.py`
- `backend/tests/unit/test_domain/test_chat_workflow.py`
- `backend/tests/unit/test_domain/test_chat_service.py`
- `backend/tests/unit/test_domain/test_stream_service.py`
- `backend/tests/integration/test_agent.py`
- `backend/tests/integration/test_logging_e2e.py`

当前边界：
- `application/__init__.py` 是包级导出面，不应再通过 eager import 把 `runtime -> agent/services -> llm` 拉成循环依赖。
- 现在存在两条相关但不同的输入边界：`runtime_context` 负责 runtime 聚合视图，`request_envelope` 负责发给 provider 的 canonical request 载荷。
- `RequestEnvelope` 的主链路是 `agent.py` -> `WorkflowContext` -> `chat_workflow.py` -> `chat_service.py` -> `stream_service.py` / provider。
- `ChatService` 只把 model-visible 上下文投影进 system prompt；`request_metadata`、tools 原始载荷等不应伪装成用户消息内容。
- request / trace / span metadata 会沿 `request_envelope.request_metadata` 继续向 provider logging 透传。

## Tool Registry / Function Calling
通常联动：
- `backend/alice/domain/execution/models/tool_calling.py`
- `backend/alice/domain/execution/services/tool_registry.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `backend/alice/application/workflow/function_calling_orchestrator.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/cli/main.py`
- `backend/tests/unit/test_domain/test_chat_workflow.py`
- `backend/tests/unit/test_domain/test_stream_service.py`
- `backend/tests/integration/test_logging_e2e.py`

当前边界：
- tool calling capability 不是纯 provider 内部细节；CLI 环境变量、stream service request kwargs 与 provider capability dataclass 会一起联动。
- `ChatWorkflow -> FunctionCallingOrchestrator -> ToolRegistry -> ExecutionService -> harness executor` 是当前结构化工具执行主链；若改 tool schema、参数验证、environment metadata 或执行后端，至少同步看这条主链和对应测试。
- `ExecutionService` 仍保留 `toolkit` / `update_prompt` / `todo` / `memory` 等 builtin 文本命令拦截，属于与结构化 tool schema 并存的兼容轨；改工具能力时不要只改其中一条入口。
- `StreamService.build_tool_kwargs()` 是当前显式 capability gate、tool binding 与 binding 日志的单点；若改绑定规则，至少同步看 `chat_workflow.py` 的 request kwargs 装配、`test_stream_service.py` 与 `test_provider_capability.py`。
- `ChatWorkflow` 负责准备 iteration 级 `request_envelope` 与 provider metadata 投影，但不应再复制第二套 capability 决策逻辑。

## 配置 / CLI 启动装配
通常联动：
- `backend/alice/core/config/settings.py`
- `backend/alice/core/config/loader.py`
- `backend/alice/cli/bootstrap.py`
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `backend/tests/unit/test_core/test_config_loader.py`
- `backend/tests/unit/test_cli/test_bootstrap.py`
- `backend/tests/unit/test_application/test_orchestration_service.py`

当前边界：
- `.alice/config.json` 已是运行时配置源，`ConfigLoader` 负责把 JSON 解析为 `Settings`，再叠加环境变量覆盖。
- `bootstrap.create_agent_from_env()` 负责把 `Settings`、请求头 profile 解析和 provider capability 拼成启动装配，不应在 CLI 主链继续散落第二套默认值。
- `OrchestrationService.create_from_settings()` 是 `Settings -> create_from_config()` 的显式透传边界；若新增运行时配置字段，至少同步看 loader、bootstrap、orchestration 与对应单测。
- `ExecutionService._update_prompt_file()` 已通过 `settings.get_absolute_path(settings.prompt_path)` 走统一配置路径，修改 prompt/memory 路径语义时要一起回归。

## 配置 / CLI 启动装配
通常联动：
- `backend/alice/core/config/settings.py`
- `backend/alice/core/config/loader.py`
- `backend/alice/cli/bootstrap.py`
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `backend/tests/unit/test_core/test_config_loader.py`
- `backend/tests/unit/test_cli/test_bootstrap.py`
- `backend/tests/unit/test_application/test_orchestration_service.py`

当前边界：
- `.alice/config.json` 已是运行时配置源，`ConfigLoader` 负责把 JSON 解析为 `Settings`，再叠加环境变量覆盖。
- `bootstrap.create_agent_from_env()` 负责把 `Settings`、请求头 profile 解析和 provider capability 拼成启动装配，不应在 CLI 主链继续散落第二套默认值。
- `bootstrap.ensure_runtime_scaffold()` 是首次运行时脚手架边界：负责补齐 `.alice/config.json`、`.alice/prompt.xml`、`.alice/memory/*`；改默认 prompt/config/memory 路径时，要同时看 scaffold、loader、orchestration 与对应测试。
- `OrchestrationService.create_from_settings()` 是 `Settings -> create_from_config()` 的显式透传边界；若新增运行时配置字段，至少同步看 loader、bootstrap、orchestration 与对应单测。
- `ExecutionService._update_prompt_file()` 已通过 `settings.get_absolute_path(settings.prompt_path)` 走统一配置路径，修改 prompt/memory 路径语义时要一起回归。

## Prompt fragments / runtime prompt assembly
通常联动：
- `prompts/01_identity.xml`
- `prompts/02_principles.xml`
- `prompts/03_memory.xml`
- `prompts/04_tools.xml`
- `prompts/05_output.xml`
- `backend/alice/cli/bootstrap.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `backend/tests/unit/test_cli/test_bootstrap.py`

当前边界：
- `prompts/01_identity.xml` 到 `prompts/05_output.xml` 是 prompt 源分片，`bootstrap.py` 通过固定顺序组装它们生成运行时 `.alice/prompt.xml`。
- 运行时消费与 `update_prompt` 写入的都是 `.alice/prompt.xml`，不会回写 `prompts/` 源分片；因此改 prompt 分片内容、顺序、标签格式或目标路径时，要同步检查首次组装与后续写入语义是否一致。
- `.alice/prompt.xml` 是当前运行时真实输入边界，但不是长期设计文档；长期 prompt 规则仍应沉淀在 `prompts/` 源文件与 `docs/`。

## Gateway / WebSocket 传输
通常联动：
- `backend/alice/infrastructure/gateway/server.py`
- `backend/alice/infrastructure/gateway/session_runtime.py`
- `backend/alice/infrastructure/gateway/session_registry.py`
- `backend/alice/infrastructure/gateway/replay.py`
- `backend/alice/infrastructure/gateway/projector.py`
- `backend/alice/application/dto/responses.py`
- `backend/alice/application/agent/agent.py`
- `backend/tests/unit/test_infrastructure/test_gateway_auth.py`
- `backend/tests/unit/test_infrastructure/test_gateway_projector.py`
- `backend/tests/unit/test_infrastructure/test_gateway_replay.py`
- `backend/tests/unit/test_infrastructure/test_gateway_session_registry.py`

当前边界：
- gateway 不直接定义第二套 runtime event；`projector.py` 负责把 `ApplicationResponse` 投影成 websocket frame，runtime payload 仍复用 canonical DTO 形状。
- `GatewaySessionRuntime` 维护 request 生命周期、replay buffer、背压丢弃与 interrupt 转发；若改 `interrupt_ack`、`request.completed.final_state` 或 droppable delta 类型，至少同步看 gateway projector / replay / session tests。
- websocket transport 已存在于当前树，但不等于本轮要推进 remote gateway 产品化；涉及其协议扩展时，需单独评估与 legacy bridge、runtime event、execution interrupt 语义的兼容面。

## 结构化日志
通常联动：
- `backend/alice/core/logging/`
- `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `scripts/validate_logs.py`
- `backend/tests/integration/test_logging_e2e.py`
- `backend/tests/unit/test_core/test_logging_schema.py`
- `backend/tests/performance/test_log_write_speed.py`
- `docs/operations/logging/README.md`

当前边界：
- bridge compatibility 事件也属于结构化日志的一部分，并落到 `tasks` 时间线。
- `binding.*`、`bridge.*`、`workflow.*`、`model.*` 事件修改时，要同步检查 schema 文件生成、分类路由与测试断言。

## 技能系统
通常联动：
- `skills/`
- `backend/alice/domain/skills/`
- `backend/alice/domain/execution/services/execution_service.py` 中的 `SkillSnapshotManager`
- `toolkit refresh` 对应加载逻辑

## 何时扩展搜索面
出现下面情况时，不要只改单点：
- 改了协议字段或消息类型。
- 改了 workflow 阶段或状态枚举。
- 改了 runtime context / request envelope / provider metadata 传播规则。
- 改了日志 schema、trace 字段或校验规则。
- 改了技能发现、缓存或 `SKILL.md` 约束。

## 配套阅读
- 总览入口：`docs/reference/code-map.md`
- 结构分层：`docs/reference/code-map-structure.md`
- 权威性说明：`docs/reference/sources-of-truth.md`
