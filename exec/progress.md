# 进度记录

> 说明：以下早期条目属于**历史记录**，其中若与当前代码树冲突，一律以代码现状和 `exec/audit-baseline-current-tree.md` 为准。
>
> 从本次短周期修复开始，请由主 agent 统一追加新的执行记录。

## 当前短周期修复记录

### 最终审计 - Wave 1 / Wave 2 汇总
- 状态：审计完成，待最终全量回归
- 日期：2026-04-06
- 对应计划：`exec/short-cycle-repair-plan.md`
- 汇总结论：
  - Alpha：已恢复 `backend.alice.core.container.ServiceDescriptor` 导出，消除了先前阻塞全量 pytest 收集期的导入错误；相关历史记录已过时。
  - Beta：execution harness 已形成显式 `ExecutionBackend` seam，`LifecycleService` 与 `DockerExecutor` 都改为委托 backend，`ContainerManager` 退回底层 Docker 适配职责。
  - Gamma：CLI 入口已通过 `backend/alice/cli/bootstrap.py` 收口 composition root，`create_agent_from_env()` 统一装配 provider / skill / harness，并让 lifecycle 与 execution 共享同一 backend owner。
  - Delta：workflow / provider 契约已部分收口；`ChatWorkflow` 每轮基于当前 `chat_service.messages` 重建 `RequestEnvelope`，`build_tool_kwargs()` 保持 `metadata` 与 `request_envelope` 分层，`OpenAIProvider` 在 SDK transport 前显式过滤这两个字段。
- 审计证据：
  - `backend/alice/core/container/__init__.py` 已重新导出 `ServiceDescriptor`
  - `backend/alice/application/services/lifecycle_service.py` 已接收 `backend: ExecutionBackend | None`
  - `backend/alice/domain/execution/executors/base.py` 已定义 `ExecutionBackend` / `ExecutionBackendStatus`
  - `backend/alice/domain/execution/executors/docker_executor.py` 已委托 `DockerExecutionBackend`
  - `backend/alice/infrastructure/docker/container_manager.py` 已提供统一 `ensure_ready / exec / status / interrupt / cleanup`
  - `backend/alice/cli/main.py` 已改为调用 `backend/alice/cli/bootstrap.py`
  - `backend/alice/infrastructure/bridge/canonical_bridge.py` 已直接复用 application DTO，而非维持双份 canonical 定义
  - `backend/alice/domain/llm/providers/openai_provider.py` 已过滤 `metadata` / `request_envelope`，不再把它们作为 transport kwargs 透传给 SDK
- 当前已确认的遗留风险：
  - `backend/alice/domain/execution/services/execution_service.py` 仍保留 `ExecutionResult | str` 双返回制
  - interrupt 语义仍只能表示“会话流停止”，不能等价为 backend 进程已被终止
  - gateway 目录与测试已存在于当前树中，但不属于本轮短周期修复目标；若后续继续推进 remote gateway，需要补独立 plan 与 docs 收口
- 最终回归：
  - 尚未执行 `python -m pytest backend/tests -q`
  - 跑完后需把失败区分为“本轮新增失败”或“历史基线残留失败”

## 历史记录

## Wave 1 - Agent Gamma - Phase 3
- 状态：完成
- 日期：2026-04-05
- 改动文件列表
  - `backend/alice/application/services/lifecycle_service.py`
  - `backend/alice/domain/execution/executors/base.py`
  - `backend/alice/domain/execution/executors/docker_executor.py`
  - `backend/alice/domain/execution/executors/__init__.py`
  - `backend/alice/infrastructure/docker/container_manager.py`
  - `backend/alice/infrastructure/docker/__init__.py`
- 测试结果摘要
  - 通过：`python -m pytest backend/tests/unit/test_domain/test_runtime_context_phase2.py -v`
  - 通过：`python -m pytest backend/tests/integration/test_agent.py -k "execute_tool_invocation_alias" -v`
  - 通过：`python -m pytest backend/tests/unit/test_domain/test_docker_executor.py -v`
  - 通过：`python -m pytest backend/tests/integration/test_logging_e2e.py -k "workflow_executor_and_api_error_events" -v`
  - 全量执行：`python -m pytest backend/tests/ -v`
    - 结果：失败（当时的基线/外部改动导致的收集期错误）
    - 历史错误：`backend/tests/unit/test_core/test_container.py` 导入 `backend.alice.core.container.ServiceDescriptor` 失败（现已修复，不再代表当前状态）
  - 手动验证：`docker ps -a --filter name=alice-sandbox-instance`
    - 结果：`alice-sandbox-instance` 容器存在且处于 `Up` 状态
- 对外接口变更说明（如有）
  - 无破坏性接口变更
  - `LifecycleService` 与 `DockerExecutor` 仍保持原有构造入口可用
  - 新增统一 seam 导出：`ExecutionBackend`、`ExecutionBackendStatus`、`DockerExecutionBackend`
- 遗留问题（如有）
  - `backend/tests/unit/test_domain/test_command.py::TestCommandParsing::test_case_sensitivity_in_builtin_detection` 当前与现实现状不一致，未在本 Phase 修改

## Wave 1 - Agent Alpha - Phase 1
- 状态：完成
- 日期：2026-04-05
- 改动文件列表
  - `backend/alice/application/dto/responses.py`
  - `backend/alice/application/workflow/chat_workflow.py`
  - `backend/alice/infrastructure/bridge/canonical_bridge.py`
- 测试结果摘要
  - 通过：`python -m pytest backend/tests/unit/test_domain/test_chat_workflow.py -q`
  - 通过：`python -m pytest backend/tests/integration/test_bridge.py -q`
  - 通过：`python -m pytest backend/tests/integration/test_logging_e2e.py::test_logging_e2e_tracks_legacy_compatibility_projection_events -q`
  - 通过：`python -m pytest backend/tests/integration/test_logging_e2e.py::test_logging_e2e_tracks_typed_tool_call_aggregation -q`
  - 通过：`python -m pytest backend/tests/unit/test_domain/test_stream_service.py -q`
  - 全量执行：`python -m pytest backend/tests -v`
    - 结果：失败（当时的基线/外部改动导致的收集期错误）
    - 历史错误：`backend/tests/unit/test_core/test_container.py` 导入 `backend.alice.core.container.ServiceDescriptor` 失败（现已修复，不再代表当前状态）
- 对外接口变更说明（如有）
  - 无破坏性接口变更
  - canonical bridge 模型改为复用 dto 层定义，避免 bridge 与 dto 双份漂移
  - workflow 发出的 tool call / tool result 载荷统一对齐 dto canonical envelope
- 遗留问题（如有）
  - 无新增遗留；先前的 `ServiceDescriptor` 导出阻塞已在后续短周期修复中消除

## Wave 1 - Agent Alpha - Phase 1 Follow-up
- 状态：完成
- 日期：2026-04-05
- 改动文件列表
  - `backend/alice/application/workflow/chat_workflow.py`
  - `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`
  - `backend/tests/unit/test_domain/test_chat_workflow.py`
  - `backend/tests/integration/test_bridge.py`
- 测试结果摘要
  - 先失败后修复：`python -m pytest backend/tests/unit/test_domain/test_chat_workflow.py -q`
  - 先失败后修复：`python -m pytest backend/tests/integration/test_bridge.py -q`
  - 通过：`python -m pytest backend/tests/unit/test_domain/test_stream_service.py -q`
  - 通过：`python -m pytest backend/tests/integration/test_logging_e2e.py::test_logging_e2e_tracks_legacy_compatibility_projection_events -q`
  - 通过：`python -m pytest backend/tests/integration/test_logging_e2e.py::test_logging_e2e_tracks_typed_tool_call_aggregation -q`
  - 全量执行：`python -m pytest backend/tests -v`
    - 结果：失败（当时的基线/外部改动导致的收集期错误）
    - 历史错误：`backend/tests/unit/test_core/test_container.py` 导入 `backend.alice.core.container.ServiceDescriptor` 失败（现已修复，不再代表当前状态）
- 对外接口变更说明（如有）
  - 无破坏性接口变更
  - 已中断请求不再先发 `status_changed(thinking)`，直接发 `interrupt_ack`
  - 带 `tool_calls` 的 `message_completed` 现在按“一轮模型消息完成”对外发射，但 legacy serializer 不会因此提前投影 `done`
- 遗留问题（如有）
  - `tool_result.content` 仍承载 execution 层 JSON 字符串，受限于本 Phase 禁止修改 `backend/alice/domain/execution/**`，本 follow-up 未继续深入
