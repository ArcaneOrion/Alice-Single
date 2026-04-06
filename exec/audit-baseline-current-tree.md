# 当前树审查基线

本文件记录 **2026-04-05 审查后** 的当前代码事实，用来替代旧 exec 文档中的过期前提。

## 核心结论

### 1. 当前不适合继续沿用旧的 Phase 0-5 执行叙事
原因不是方向错，而是**执行状态已经和代码树脱节**。后续 agent 不能再默认：
- Phase 3 已稳定完成
- ExecutionBackend seam 已完全落地
- handoff 中描述的 execution owner 关系已经成为事实

**以当前代码为准，不能以旧进度文档为准。**

### 2. 当前 active scope 应收缩为“短周期修复”
本轮优先级不是继续扩展插件化 / gateway，而是把这几件已被审查确认的问题修掉：

1. 测试基线阻塞
2. harness seam 现实与文档不一致
3. composition root 与实际入口装配不一致
4. workflow/provider contract 漂移

---

## 已确认的审查问题

### A. 首轮请求可能复用旧的 RequestEnvelope.messages
- 位置：`backend/alice/application/workflow/chat_workflow.py:263-268`
- 影响：provider 首轮看到的可能不是当前 `chat_service.messages`，而是旧 envelope 快照
- 结论：属于高优先级真实问题

### B. CLI bootstrap 额外创建了一套 harness/backend
- 位置：`backend/alice/cli/bootstrap.py:89-94`
- 对照：`backend/alice/application/services/orchestration_service.py:120-131`
- 影响：同一进程可能存在两套 backend owner，破坏 Phase 3 的单一 seam 目标
- 结论：属于高优先级真实问题

### C. LifecycleService 会覆盖调用方传入的 docker_config.project_root
- 位置：`backend/alice/application/services/lifecycle_service.py:35-37`
- 影响：容器挂载目录、build context、镜像定位可能被静默改写
- 结论：属于中优先级真实问题

---

## 已确认的文档 / 进度漂移

### D. provider contract 仍按“双重 capability gate”描述，但实现已变化
- 文档：`exec/contracts/provider-request-contract.md:167-179`
- 现实：异常已统一表面化为 `CHAT_ERROR`

### E. provider contract 仍把 metadata 当 transport 参数，但 OpenAIProvider 已过滤
- 文档：`exec/contracts/provider-request-contract.md:127-151`
- 代码：`backend/alice/domain/llm/providers/openai_provider.py:387-394`

### F. runtime contract 仍写 DTO / canonical bridge 双定义，但 bridge 已复用 dto
- 文档：`exec/contracts/runtime-event-contract.md:9-10`
- 代码：`backend/alice/infrastructure/bridge/canonical_bridge.py:1-19`

### G. progress.md 中关于 ServiceDescriptor 导出缺失的描述已经滞后
- 文档：`exec/progress.md`
- 代码：`backend/alice/core/container/__init__.py`

---

## 约束与决策

### 当前轮不做
1. 不推进 remote gateway
2. 不推进全面插件化
3. 不把旧 Phase 文档继续当 active plan
4. 不使用 `exec/handoff/gamma-to-delta.md` 作为当前事实输入

### 当前轮要做
1. 先修基线和真实缺陷
2. 再对齐装配边界
3. 最后回写文档与进度

---

## 当前唯一可信输入
当前执行时，优先级按下面顺序：
1. **代码现状**
2. **本文件 audit-baseline-current-tree.md**
3. `short-cycle-repair-plan.md`
4. `ownership-matrix.md`
5. 其他背景材料

如果其他 exec 文档与代码冲突，一律以代码和本文件为准。
