# 短周期 Agent 提示词

按 wave 排列。每个终端只执行一个 agent 角色。

---

## Wave 1（两个终端并行）

### 终端 1 — Agent Alpha：修复测试基线阻塞

```
你是 Agent Alpha，负责短周期修复计划中的“测试基线阻塞修复”。

## 先读文档
- exec/README.md
- exec/audit-baseline-current-tree.md
- exec/short-cycle-repair-plan.md
- exec/ownership-matrix.md

## 你的文件所有权
只允许修改：
- backend/alice/core/container/__init__.py
- backend/tests/unit/test_core/test_container.py

## 任务
1. 先复现当前阻塞问题
2. 修复 `ServiceDescriptor` 导出问题
3. 让 `backend/tests/unit/test_core/test_container.py` 可以正常运行
4. 再验证全量后端测试至少不再因收集期导出问题失败

## 约束
- 只改你拥有的文件
- 不顺手改 DI 容器架构
- 改代码前先测试，改完后跑相同测试
- 用中文报告结论

## 最小验证集
```bash
python -m pytest backend/tests/unit/test_core/test_container.py -q
python -m pytest backend/tests -q
```

## 输出格式
完成后请汇报：
1. 修改了哪些文件
2. 改前测试结果
3. 改后测试结果
4. 是否仍有全量失败；如果有，明确失败点
```

---

### 终端 2 — Agent Beta：真正收口 execution harness seam

```
你是 Agent Beta，负责短周期修复计划中的“execution harness seam 收口”。

## 先读文档
- exec/README.md
- exec/audit-baseline-current-tree.md
- exec/short-cycle-repair-plan.md
- exec/ownership-matrix.md
- exec/contracts/execution-harness-contract.md

## 你的文件所有权
只允许修改：
- backend/alice/application/services/lifecycle_service.py
- backend/alice/domain/execution/executors/base.py
- backend/alice/domain/execution/executors/__init__.py
- backend/alice/domain/execution/executors/docker_executor.py
- backend/alice/infrastructure/docker/__init__.py
- backend/alice/infrastructure/docker/container_manager.py

必要时可修改：
- backend/alice/domain/execution/services/execution_service.py
- backend/alice/infrastructure/docker/client.py
- backend/alice/infrastructure/docker/config.py

## 任务
1. 先复现当前 harness seam 的真实问题
2. 把 `ensure_ready / exec / status / interrupt / cleanup` 收口到单一 backend owner
3. 消除三处 Docker 初始化链路并存
4. 修复 `LifecycleService` 覆盖调用方 `docker_config.project_root` 的兼容问题
5. 不要改 composition root，不要改 workflow/provider

## 约束
- 只改你拥有的文件
- 改代码前先测试，改完后跑相同测试
- 用中文报告结论
- 如发现需要 Gamma 配合的装配问题，只在汇报里说明，不越权修改

## 最小验证集
```bash
python -m pytest backend/tests/unit/test_domain/test_docker_executor.py -q
python -m pytest backend/tests/integration/test_agent.py -k "execute_tool_invocation_alias" -q
python -m pytest backend/tests/integration/test_logging_e2e.py -k "workflow_executor_and_api_error_events" -q
```
手动验证：
```bash
docker ps -a --filter name=alice-sandbox-instance
```

## 输出格式
完成后请汇报：
1. 修改了哪些文件
2. 改前测试结果
3. 改后测试结果
4. backend owner 现在如何收口
5. 还剩哪些需要 Gamma 处理的入口装配问题
```

---

## Wave 2（两个终端并行，前提：Wave 1 Beta 完成）

### 终端 1 — Agent Gamma：对齐 composition root 与真实入口

```
你是 Agent Gamma，负责短周期修复计划中的“composition root / CLI 入口对齐”。

## 前置条件
Wave 1 的 Agent Beta 已完成。开始前先确认：
- 已读取 Beta 的结果汇报
- 已确认 harness seam 当前 owner 模型

## 先读文档
- exec/README.md
- exec/audit-baseline-current-tree.md
- exec/short-cycle-repair-plan.md
- exec/ownership-matrix.md

## 你的文件所有权
只允许修改：
- backend/alice/application/services/orchestration_service.py
- backend/alice/cli/main.py
- 如确有必要：backend/alice/cli/bootstrap.py

## 任务
1. 审查当前 provider / executor / lifecycle 的装配路径
2. 消除“同一进程两套 harness/backend owner”问题
3. 让 CLI 入口与 execution 主链使用同一 backend owner
4. 如需新增 `bootstrap.py`，必须显式创建并说明原因

## 约束
- 不修改 lifecycle_service.py
- 不修改 execution harness 三件套
- 不修改 chat_workflow.py / stream_service.py / openai_provider.py
- 改代码前先测试，改完后跑相同测试
- 用中文报告结论

## 最小验证集
```bash
python -m pytest backend/tests/integration/test_agent.py -q
python -m pytest backend/tests/integration/test_logging_e2e.py -q
```

## 输出格式
完成后请汇报：
1. 修改了哪些文件
2. 改前测试结果
3. 改后测试结果
4. 入口装配现在如何收口
5. 是否新增了 bootstrap.py；如有，说明原因
```

---

### 终端 2 — Agent Delta：收口 workflow / provider 最小契约漂移

```
你是 Agent Delta，负责短周期修复计划中的“workflow / provider 最小契约漂移修复”。

## 前置条件
Wave 1 的 Agent Beta 已完成。开始前先确认：
- 已读取 Beta 的结果汇报
- 已确认 interrupt / metadata / backend owner 的真实语义边界

## 先读文档
- exec/README.md
- exec/audit-baseline-current-tree.md
- exec/short-cycle-repair-plan.md
- exec/ownership-matrix.md
- exec/contracts/runtime-event-contract.md
- exec/contracts/provider-request-contract.md

## 你的文件所有权
只允许修改：
- backend/alice/application/workflow/chat_workflow.py
- backend/alice/domain/llm/services/stream_service.py
- backend/alice/domain/llm/providers/openai_provider.py

必要时可修改这些测试：
- backend/tests/unit/test_domain/test_chat_workflow.py
- backend/tests/unit/test_domain/test_stream_service.py
- backend/tests/unit/test_domain/test_provider_capability.py
- backend/tests/integration/test_bridge.py
- backend/tests/integration/test_logging_e2e.py

## 任务
1. 修复首轮请求复用旧 envelope 的问题
2. 把 tool-calling capability gate 收口到单一 canonical 决策点
3. 对齐 metadata 在 runtime / provider / transport 之间的行为
4. 不把 interrupt_ack 描述成“底层执行一定已被终止”

## 约束
- 不修改 orchestration_service.py / cli/main.py
- 不修改 lifecycle_service.py / docker_executor.py / container_manager.py
- 改代码前先测试，改完后跑相同测试
- 用中文报告结论

## 最小验证集
```bash
python -m pytest backend/tests/unit/test_domain/test_chat_workflow.py -q
python -m pytest backend/tests/unit/test_domain/test_stream_service.py -q
python -m pytest backend/tests/unit/test_domain/test_provider_capability.py -q
python -m pytest backend/tests/integration/test_bridge.py -q
```

## 输出格式
完成后请汇报：
1. 修改了哪些文件
2. 改前测试结果
3. 改后测试结果
4. 首轮 envelope 问题如何修复
5. capability gate 现在落在哪一层
```

---

## Wave 3（主 agent）

主终端执行：

```
Wave 1 和 Wave 2 都已完成。请做最终审计：

1. 汇总 Alpha / Beta / Gamma / Delta 的结果
2. 更新 exec/progress.md，分成“历史记录”和“当前短周期修复记录”
3. 检查 exec/contracts/README.md 中与现实冲突的摘要是否需要更新
4. 如本轮影响了架构边界或代码地图，运行 /code-map 同步 docs 索引
5. 运行最终回归：python -m pytest backend/tests -q
6. 输出最终结论：
   - 已修复问题
   - 未修复问题
   - 剩余风险
```
