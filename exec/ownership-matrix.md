# 文件所有权矩阵

本文件定义短周期修复计划中的 agent 文件边界。**同一 wave 内不得交叉写文件。**

## 主 agent
可写：
- `exec/*.md`
- `exec/contracts/README.md`
- 如需：`docs/README.md`
- 如需：`docs/reference/*.md`

职责：
- 冻结基线
- 维护计划
- 汇总进度
- 最终审查

---

## Wave 1

### Agent Alpha — 测试基线
可写：
- `backend/alice/core/container/__init__.py`
- `backend/tests/unit/test_core/test_container.py`

不可写：
- `backend/alice/application/services/**`
- `backend/alice/domain/execution/**`
- `backend/alice/infrastructure/docker/**`
- `backend/alice/application/workflow/**`
- `backend/alice/domain/llm/**`

---

### Agent Beta — execution harness seam
可写：
- `backend/alice/application/services/lifecycle_service.py`
- `backend/alice/domain/execution/executors/base.py`
- `backend/alice/domain/execution/executors/__init__.py`
- `backend/alice/domain/execution/executors/docker_executor.py`
- `backend/alice/infrastructure/docker/__init__.py`
- `backend/alice/infrastructure/docker/container_manager.py`

必要时可扩展到：
- `backend/alice/domain/execution/services/execution_service.py`
- `backend/alice/infrastructure/docker/client.py`
- `backend/alice/infrastructure/docker/config.py`

不可写：
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/cli/main.py`
- `backend/alice/cli/bootstrap.py`
- `backend/alice/application/workflow/**`
- `backend/alice/domain/llm/**`
- `exec/*.md`

---

## Wave 2

### Agent Gamma — composition root / CLI 入口
前置依赖：Wave 1 Beta 完成

可写：
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/cli/main.py`
- 如确有必要：`backend/alice/cli/bootstrap.py`

不可写：
- `backend/alice/application/services/lifecycle_service.py`
- `backend/alice/domain/execution/**`
- `backend/alice/infrastructure/docker/**`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/llm/**`
- `exec/*.md`

---

### Agent Delta — workflow / provider
前置依赖：Wave 1 Beta 完成

可写：
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/domain/llm/providers/openai_provider.py`
- 必要时相关测试文件：
  - `backend/tests/unit/test_domain/test_chat_workflow.py`
  - `backend/tests/unit/test_domain/test_stream_service.py`
  - `backend/tests/unit/test_domain/test_provider_capability.py`
  - `backend/tests/integration/test_bridge.py`
  - `backend/tests/integration/test_logging_e2e.py`

不可写：
- `backend/alice/application/services/**`
- `backend/alice/domain/execution/**`
- `backend/alice/infrastructure/docker/**`
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/cli/**`
- `exec/*.md`

---

## 依赖关系

```text
Wave 0: 主 agent

Wave 1:
  Alpha || Beta

Wave 2:
  Gamma || Delta
  但都依赖 Beta 先完成

Wave 3:
  主 agent
```

---

## 冲突清单

### 不能同时写的关键文件
- `backend/alice/application/workflow/chat_workflow.py` → 只归 Delta
- `backend/alice/application/services/lifecycle_service.py` → 只归 Beta
- `backend/alice/application/services/orchestration_service.py` → 只归 Gamma
- `backend/alice/cli/main.py` → 只归 Gamma
- `exec/progress.md` → 只归主 agent

---

## 同步规则

1. Agent 完成后不要直接改 `exec/progress.md`
2. 先把结果发回主终端
3. 由主 agent 统一写入进度与审计结论
4. 如需 handoff，写新文件到 `exec/handoff/`，并明确标注日期与适用 wave
