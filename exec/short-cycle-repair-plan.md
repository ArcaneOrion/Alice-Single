# 短周期修复计划

本计划替代旧的长期 Phase 0-5 执行叙事，专注解决当前树上已经被审查确认的问题。

## 总目标
在不扩大改动面的前提下，完成以下四件事：

1. 恢复可信的测试基线
2. 让 execution harness seam 真正落地
3. 让 composition root 与真实入口对齐
4. 收口 workflow / provider 的最小契约漂移

---

## Wave 0：冻结基线（主 agent）

### 目标
统一团队对“当前事实”的理解，停止继续使用旧 handoff 与旧 progress 作为现状输入。

### 产物
- `exec/audit-baseline-current-tree.md`
- `exec/short-cycle-repair-plan.md`
- `exec/ownership-matrix.md`
- `exec/agent-prompts-short-cycle.md`

### 完成标准
- 所有后续 agent 只按新文档执行
- `exec/handoff/gamma-to-delta.md` 被视为历史材料，不再视为当前事实

---

## Wave 1：并行修复（2 个 agent）

### Agent Alpha — 修复测试基线阻塞

#### 文件范围
- `backend/alice/core/container/__init__.py`
- `backend/tests/unit/test_core/test_container.py`

#### 任务
1. 修复 `ServiceDescriptor` 导出问题
2. 恢复 full pytest 至少能通过收集期
3. 不顺手扩大 DI 容器改造范围

#### 验收
```bash
python -m pytest backend/tests/unit/test_core/test_container.py -q
python -m pytest backend/tests -q
```

#### 完成标准
- `test_container.py` 可正常导入目标符号
- 全量后端测试若仍失败，失败原因不能再是收集期导出错误

---

### Agent Beta — 真正收口 execution harness seam

#### 文件范围
- `backend/alice/application/services/lifecycle_service.py`
- `backend/alice/domain/execution/executors/docker_executor.py`
- `backend/alice/infrastructure/docker/container_manager.py`
- 必要时：
  - `backend/alice/domain/execution/executors/base.py`
  - `backend/alice/domain/execution/executors/__init__.py`
  - `backend/alice/infrastructure/docker/__init__.py`

#### 任务
1. 统一 `ensure_ready`
2. 统一 `exec`
3. 统一 `status`
4. 统一 `interrupt`
5. 统一 `cleanup`
6. 消除三处 Docker 初始化链路并存
7. 修复 `LifecycleService` 覆盖 `docker_config.project_root` 的兼容问题

#### 验收
```bash
python -m pytest backend/tests/unit/test_domain/test_docker_executor.py -q
python -m pytest backend/tests/integration/test_agent.py -k "execute_tool_invocation_alias" -q
python -m pytest backend/tests/integration/test_logging_e2e.py -k "workflow_executor_and_api_error_events" -q
```
手动验证：
```bash
docker ps -a --filter name=alice-sandbox-instance
```

#### 完成标准
- `LifecycleService` 不再自持一套初始化主逻辑
- `DockerExecutor` 不再再造一套初始化主逻辑
- `ContainerManager` 退回底层适配职责
- `project_root` 的优先级与兼容规则明确

---

## Wave 2：并行收口（2 个 agent，依赖 Wave 1 Beta 完成）

### Agent Gamma — 对齐 composition root 与真实入口

#### 文件范围
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/cli/main.py`
- 如果确实需要新增：`backend/alice/cli/bootstrap.py`

#### 任务
1. 收口 provider / executor / registry 的装配入口
2. 确保 CLI 使用的 backend owner 与 execution 主链一致
3. 如果引入 `bootstrap.py`，必须由本 wave 显式创建，而不是假定其已存在
4. 消除“同一进程两套 harness/backend owner”问题

#### 验收
```bash
python -m pytest backend/tests/integration/test_agent.py -q
python -m pytest backend/tests/integration/test_logging_e2e.py -q
```

#### 完成标准
- composition root 只保留一条主装配路径
- lifecycle 与 execution 指向同一 backend owner

---

### Agent Delta — 收口 workflow / provider 最小契约漂移

#### 文件范围
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/domain/llm/providers/openai_provider.py`
- 相关测试文件（仅必要时）

#### 任务
1. 修复首轮请求复用旧 envelope 的问题
2. 收口 tool-calling capability gate 到单一 canonical 决策点
3. 明确 metadata 在 runtime / provider / transport 之间的投影边界
4. 保持 interrupt 语义与真实 backend 能力一致，不夸大“已中断 = 已终止执行”

#### 验收
```bash
python -m pytest backend/tests/unit/test_domain/test_chat_workflow.py -q
python -m pytest backend/tests/unit/test_domain/test_stream_service.py -q
python -m pytest backend/tests/unit/test_domain/test_provider_capability.py -q
python -m pytest backend/tests/integration/test_bridge.py -q
```

#### 完成标准
- 首轮消息与当前 `chat_service.messages` 对齐
- capability gate 不再重复分叉
- metadata 行为与测试、实现一致

---

## Wave 3：文档收口与最终回归（主 agent）

### 目标
把修复后的事实重新写回 exec 与 docs，避免再次形成“代码已变、计划未变”的漂移。

### 任务
1. 更新 `exec/progress.md`
2. 更新 `exec/contracts/README.md` 中与现实冲突的摘要
3. 如需要，运行 `/code-map` 同步 docs 索引
4. 跑最终回归并区分：
   - 本轮新增失败
   - 历史基线残留失败

### 最终验收
```bash
python -m pytest backend/tests -q
```

如果失败，必须明确归因，不能仅写“基线问题”。

---

## 并行原则

1. 同一 wave 内不允许两个 agent 修改同一文件
2. `chat_workflow.py` 只归 Delta
3. harness 三件套只归 Beta
4. 入口装配只归 Gamma
5. `exec/*.md` 只归主 agent

---

## 本轮不做
1. 不推进 remote gateway
2. 不推进全面插件化
3. 不继续扩 Phase 4/5 叙事
4. 不用旧 handoff 继续派工
