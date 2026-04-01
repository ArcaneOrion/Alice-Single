# Phase 3：Tool Schema 单一真源收口

## 1. 项目上下文

当前 Alice 已经有 ToolRegistry 的四分类快照：

- builtin_system_tools
- skills
- terminal_commands
- code_execution

但真正给模型绑定的 callable schema 仍然只覆盖一小部分工具，并且快照、provider binding、runtime 校验并未完全共用同一份 schema 真源。

## 2. 此次修改任务的原因

如果 tool schema 继续分散：

- runtime context 展示的是一套工具事实
- provider 绑定的是另一套 schema
- runtime 执行校验可能又是一套约束
- 审计与测试无法确认“到底哪份定义才是真”

本 phase 的目标，是把工具定义收口成真正的单一真源，让展示、绑定、校验、测试都从同一处派生。

## 3. 范围

### 3.1 本 phase 包含
- 明确 tool schema 真源位置
- 明确 snapshot / provider binding / runtime validation 的派生关系
- 减少手写重复 schema
- 固化 tool 参数错误与未注册工具错误的处理边界

### 3.2 本 phase 不包含
- provider capability 抽象本身
- frontend 协议变更
- request envelope 结构扩展

## 4. 关键文件

### 4.1 代码
- `backend/alice/domain/execution/services/tool_registry.py`
- `backend/alice/application/workflow/function_calling_orchestrator.py`
- `backend/alice/domain/execution/models/tool_calling.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/llm/services/stream_service.py`

### 4.2 文档
- `docs/reference/code-map.md`
- `docs/testing/guide.md`

### 4.3 主要测试
- `backend/tests/unit/test_domain/test_runtime_context_phase2.py`
- `backend/tests/unit/test_domain/test_chat_workflow.py`
- `backend/tests/integration/test_agent.py`
- `backend/tests/integration/test_bridge.py`
- `backend/tests/integration/test_logging_e2e.py`

## 5. 风险与边界

1. 不能只改 snapshot，不改 provider tools
2. 不能只改 provider tools，不改 runtime 校验
3. 不能让“未注册工具”和“参数非法工具”混成同一种失败语义
4. 不能让日志与测试继续围绕过时 schema 运行

## 6. 多 Agent 团队组成

### 主 Agent
- 决定 schema 真源位置
- 决定派生边界：display / binding / validation / logging

### 测试基线 Agent
- 建立当前工具快照、tool binding、tool execution 的行为基线
- 标出覆盖空洞

### 开发 Agent
- 以最小改动收口 schema 真源
- 改造派生层，不扩散到无关功能

### Schema 审计 Agent
- 检查是否仍有第二套隐形 schema
- 检查 binding 和 runtime 错误语义是否一致
- 检查日志字段是否仍引用过时结构

## 7. 协作流程

## Phase 3.0：测试基线建立

### 必跑测试

```bash
python -m pytest backend/tests/unit/test_domain/test_runtime_context_phase2.py
python -m pytest backend/tests/unit/test_domain/test_chat_workflow.py
```

### 测试基线 Agent 输出
- 当前 snapshot 结构
- 当前 provider tools 结构
- 当前 orchestration/runtime failure 行为
- 当前测试未覆盖的 schema 漂移点

## Phase 3.1：真源设计与最小开发切片

### 目标
建立 schema 真源，并让 display / binding / validation 都成为派生物。

### 开发原则
- 真源唯一
- 派生明确
- 错误语义清晰
- 不在本 phase 扩大工具面，只先收口定义来源

### 建议切片顺序
1. 定义唯一 tool schema 真源
2. snapshot 从真源派生
3. provider binding schema 从真源派生
4. runtime validation 从真源派生
5. orchestration / logging / tests 改为依赖派生结果

### 开发 Agent 输出
- 真源定义方案
- 派生关系图
- 兼容策略

## Phase 3.2：审计

### 审计检查项
- 是否仍有手写重复 schema
- snapshot / binding / validation 是否仍可能漂移
- orchestrator 是否继续依赖非真源结构
- failure 类型是否可区分：未注册、参数非法、执行异常

### 审计输出
- 阻断项
- 可延后项
- 对 Phase 4 的输入约束

## Phase 3.3：再测试

### 必跑测试

```bash
python -m pytest backend/tests/unit/test_domain/test_runtime_context_phase2.py
python -m pytest backend/tests/unit/test_domain/test_chat_workflow.py
python -m pytest backend/tests/integration/test_agent.py
python -m pytest backend/tests/integration/test_bridge.py
python -m pytest backend/tests/integration/test_logging_e2e.py
```

### 判定规则
- 若 provider tools 与 snapshot 不一致：回到 Phase 3.1
- 若 runtime failure 语义混乱：回到 Phase 3.1
- 若 tool lifecycle 日志失真：不允许进入下一 phase

## 8. 循环规则

```text
测试基线 -> 真源最小切片开发 -> 审计 -> 再测试
  └─ 未通过：回到开发切片
  └─ 通过但仍有第二 schema 来源：继续同 phase
  └─ 真源已收口：进入 Phase 4
```

## 9. 退出条件

- tool schema 真源唯一
- snapshot / binding / validation 均由真源派生
- failure 语义清晰可测
- tool lifecycle 与相关日志/测试稳定通过

## 10. 本 phase 完成后的主 Agent 结项记录

主 Agent 需要记录：

- schema 真源最终位置
- 派生链路
- failure 分类
- 哪些旧 schema 拼装逻辑被删除或冻结

### 本轮完成记录（2026-04-01）

#### 基线测试

```bash
python -m pytest backend/tests/unit/test_domain/test_runtime_context_phase2.py
python -m pytest backend/tests/unit/test_domain/test_chat_workflow.py
```

结果：通过。

#### 本轮最小切片

- 将 `run_bash` / `run_python` 的参数解析与校验下沉到 `ToolSchemaDefinition.parse_and_validate_arguments()`
- 在 `ToolRegistry` 增加：
  - `require_tool()`
  - `validate_tool_arguments()`
- `ExecutionService.execute_tool_call()` 改为优先复用 `ToolRegistry` 真源做 runtime validation
- `FunctionCallingOrchestrator` fallback 结果补充结构化 `error_type` metadata，区分：
  - `unknown_tool`
  - `invalid_arguments`
  - `execution_error`

#### schema 真源最终位置

- callable tools 的 schema 真源：
  - `backend/alice/domain/execution/services/tool_registry.py`
  - `backend/alice/domain/execution/models/tool_calling.py`
- 其中：
  - `ToolRegistry._tools` 持有 `run_bash` / `run_python` 的 `ToolSchemaDefinition`
  - `ToolSchemaDefinition.parameters` 是 provider binding / snapshot descriptor / runtime validation 共用的参数 schema 来源

#### 派生链路

- snapshot：`ToolRegistry.snapshot()` -> `ToolSchemaDefinition.to_descriptor()`
- binding：`ToolRegistry.list_openai_tools()` -> `ToolSchemaDefinition.to_openai_tool()`
- validation：`ToolRegistry.validate_tool_arguments()` -> `ToolSchemaDefinition.parse_and_validate_arguments()`
- orchestration failure metadata：`FunctionCallingOrchestrator.execute_tool_calls()` 统一写入 `payload.metadata.error_type`
- workflow runtime event：`ChatWorkflow` 透传 `execution_result.payload.metadata`

#### failure 分类

- 未注册工具：`unknown_tool`
- 参数非法：`invalid_arguments`
- 执行异常：`execution_error`

#### 已删除或冻结的旧 schema 拼装逻辑

- 删除：`ExecutionService.execute_tool_call()` 中针对 callable tools 的主参数校验职责；改为由 `ToolRegistry` 真源驱动
- 冻结：`ExecutionService` 中 `run_bash` / `run_python` 的字段存在性判断仅保留为 dispatch 前守卫，不再作为 schema 真源
- 保留但未纳入本 phase 收口：
  - `builtin_system_tools` 手写 `ToolDescriptor`
  - `skills` 快照描述符拼装
  - bridge / legacy serializer / frontend 协议层的 tool call/result 投影结构

#### 再测试

```bash
python -m pytest backend/tests/unit/test_domain/test_runtime_context_phase2.py
python -m pytest backend/tests/unit/test_domain/test_chat_workflow.py
python -m pytest backend/tests/integration/test_agent.py
python -m pytest backend/tests/integration/test_bridge.py
python -m pytest backend/tests/integration/test_logging_e2e.py
```

结果：84 passed。

#### 结论

- Phase 3 范围内的最小切片已完成：`run_bash` / `run_python` 已实现 snapshot / binding / runtime validation 同源派生
- failure 语义已结构化且可测
- 未越界修改 bridge 主路径、request envelope、provider capability、frontend 协议
- `builtin_system_tools` / `skills` 仍为快照侧独立描述，这部分作为 Phase 4 之前的已知冻结边界保留

#### 审计结论摘要

- 阻断项：无
- 可延后项：
  - `ExecutionService` 仍保留 dispatch 前字段守卫
  - `builtin_system_tools` / `skills` 尚未纳入 callable tool schema 真源
  - runtime / bridge 的 tool call/result 投影重复定义仍在，但不属于本 phase 范围
- 对 Phase 4 的输入约束：
  - 不得绕开 `ToolRegistry` 另起 provider schema
  - 若扩展 callable tools，必须同时从真源派生 binding / validation / tests
  - failure 分类 metadata 必须继续透传到 workflow/runtime event

#### 本轮新增测试点

- `backend/tests/unit/test_domain/test_runtime_context_phase2.py`
  - schema 真源参数校验
  - `ExecutionService` 复用 `ToolRegistry` 校验
  - unknown tool / invalid arguments / execution error 的 `error_type` 断言
- `backend/tests/unit/test_domain/test_chat_workflow.py`
  - `TOOL_RESULT` runtime event 透传 `metadata.error_type`

#### 多 Agent 结果摘要

- 测试基线 Agent：两组基线测试通过，确认可进入最小切片开发
- 开发盘点 Agent：确认最小切片应限定在 `run_bash` / `run_python` 的 schema 真源收口
- schema 审计 Agent：确认当前切片未越界；补足 failure metadata 结构化后可通过本 phase 审计

#### 修改文件

- `backend/alice/domain/execution/models/tool_calling.py`
- `backend/alice/domain/execution/models/__init__.py`
- `backend/alice/domain/execution/services/tool_registry.py`
- `backend/alice/domain/execution/services/execution_service.py`
- `backend/alice/application/workflow/function_calling_orchestrator.py`
- `backend/alice/application/services/orchestration_service.py`
- `backend/tests/unit/test_domain/test_runtime_context_phase2.py`
- `backend/tests/unit/test_domain/test_chat_workflow.py`
- `tmp/phase-3-tool-schema-single-source.md`

#### 未修改但已验证稳定的边界

- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/tests/integration/test_agent.py`
- `backend/tests/integration/test_bridge.py`
- `backend/tests/integration/test_logging_e2e.py`
