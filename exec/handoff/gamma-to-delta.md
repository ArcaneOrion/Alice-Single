# 历史文档：Gamma -> Delta Handoff（已过期）

> 状态：**历史材料，不再作为当前事实输入**
>
> 原因：该 handoff 生成于旧一轮 Phase 3 之后；后续审查已确认其中部分关于 execution harness seam 已完全落地、owner 关系已稳定的表述，不能直接等同于当前代码现实。当前请优先参考：
> - `exec/audit-baseline-current-tree.md`
> - `exec/short-cycle-repair-plan.md`

# Gamma -> Delta Handoff

## Phase 3 结果
- 已将 execution harness 收口为统一 backend seam：`ExecutionBackend`
- Docker 具体实现位于：`backend/alice/infrastructure/docker/container_manager.py:190`
- `LifecycleService` 已退化为生命周期编排者，通过 backend 调用 `ensure_ready/status/cleanup`
- `DockerExecutor` 已退化为 domain 适配层，通过 backend 调用 `ensure_ready/exec/status/interrupt`

## 对 Delta 的影响
- 当前无破坏性接口变更；上层现有构造方式仍保持可用
- 如 Phase 4 需要继续收口 core/container 或 workflow 层，请直接依赖 `ExecutionBackend` seam，而不要重新引入第二条 Docker 初始化链

## 已确认的兼容点
- `LifecycleService(project_root=...)` 仍可用
- `DockerExecutor(container_name=..., docker_image=..., work_dir=...)` 仍可用
- `ExecutionService.execute_tool_invocation(...)` 兼容入口保持不变

## 遗留问题
- 全量测试在 `backend/tests/unit/test_core/test_container.py` 收集阶段失败：`backend.alice.core.container.ServiceDescriptor` 导出缺失
- 该问题不在 Gamma 本轮允许修改范围内
