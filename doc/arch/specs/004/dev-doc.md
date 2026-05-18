# Spec-004: ChatMessage reasoning_content 字段兼容性

- **ADR**: ADR-004
- **Status**: Draft
- **Author**: arcanexis
- **Date**: 2026-05-18
- **Version**: 0.1.0

---

## 概述

### 1.1 问题陈述

使用 GLM thinking mode 的用户在多轮对话中遇到 400 错误：API 要求将 assistant 消息的 `reasoning_content` 字段原样回传，但当前代码在构造消息历史时丢弃了该字段。

### 1.2 解决方案概述

在 `ChatMessage` 数据结构中新增可选字段 `reasoning_content`，并在序列化时条件性输出。以最小侵入方式将 thinking 内容从响应层传递到消息历史层，确保多轮对话时 API 收到完整的消息结构。

### 1.3 范围边界

**包含**:
- `ChatMessage` 新增 `reasoning_content` 字段及序列化/反序列化
- `ChatMessage.assistant()` 工厂方法新增 `reasoning_content` 参数
- `ChatService.add_assistant_message()` 新增 `reasoning_content` 参数
- `ChatWorkflow` 和 `ChatService` 向 assistant 消息传递 thinking 内容
- `FunctionCallingOrchestrator` 传递 `reasoning_content` 到 assistant 消息

**不包含**:
- 桥接协议变更（TUI 不需要 reasoning_content）
- `RoundEntry` 记忆持久化变更（已有 `assistant_thinking` 字段）
- OpenAI SDK 调用层变更（仅透传 `to_dict()` 输出）
- `ProviderCapability.supports_thinking` gate 逻辑

---

## 接口契约

本变更不涉及外部 API 端点修改，仅影响内部数据结构的序列化格式。

### 2.1 OpenAI 兼容消息格式变更

**序列化输出变更**：`ChatMessage.to_dict()` 对于 `role=assistant` 的消息，当 `reasoning_content` 非空时新增该字段。

**变更前后对比**：

变更前（assistant 消息）：
```json
{"role": "assistant", "content": "...", "tool_calls": [...]}
```

变更后（含 thinking 时）：
```json
{"role": "assistant", "content": "...", "reasoning_content": "思考过程...", "tool_calls": [...]}
```

变更后（无 thinking 时，与变更前一致）：
```json
{"role": "assistant", "content": "...", "tool_calls": [...]}
```

**兼容性保证**：`reasoning_content` 为 None 或空字符串时不输出该字段，行为与变更前完全一致。OpenAI 等忽略未知字段的 API 不受影响。

---

## 数据形状

### 3.1 核心实体

#### ChatMessage

| 字段 | 类型 | 必填 | 描述 | 约束 | 示例 |
|------|------|------|------|------|------|
| role | Literal["system", "user", "assistant", "tool"] | 是 | 消息角色 | 枚举值 | "assistant" |
| content | str | 是 | 消息内容 | 非空 | "你好" |
| name | str \| None | 否 | 消息名称 | 仅 tool 角色使用 | "get_weather" |
| tool_call_id | str \| None | 否 | 工具调用 ID | 仅 tool 角色使用 | "call_abc123" |
| tool_calls | list[dict] \| None | 否 | 工具调用列表 | 仅 assistant 角色使用 | [{"id": "...", "type": "function", "function": {...}}] |
| **reasoning_content** | **str \| None** | **否** | **推理/思考内容** | **仅 assistant 角色使用；为 None 或空串时不序列化** | **"让我分析一下..."** |

### 3.2 序列化规则

`to_dict()` 输出规则：
- `reasoning_content` 为 `None` 或空字符串 `""` 时，**不输出**该字段（保持变更前行为）
- `reasoning_content` 为非空字符串时，**输出**该字段

`from_dict()` 反序列化规则：
- 输入 dict 含 `reasoning_content` 键且值为非空字符串时，读入该字段
- 输入 dict 不含该键或值为空/None 时，字段设为 `None`

### 3.3 数据关系

`reasoning_content` 字段与 `ChatResponse.thinking` 和 `StreamChunk.thinking` 对应：
- `ChatResponse.thinking` → 写入 `ChatMessage.reasoning_content`
- `StreamChunk.thinking`（累积后） → 写入 `ChatMessage.reasoning_content`
- 消息历史中的 `reasoning_content` → 通过 `to_dict()` 发送给 API

---

## 行为规则

### 4.1 业务规则

#### 规则：reasoning_content 回传

- **前置条件**: LLM API 在响应中返回了 reasoning_content / thinking 内容
- **触发条件**: 将 assistant 消息添加到对话历史时
- **执行逻辑**:
  1. 从 `ChatResponse.thinking` 或累积的 `full_thinking` 中提取 thinking 文本
  2. 将其作为 `reasoning_content` 参数传入 `ChatMessage.assistant()` 或 `add_assistant_message()`
  3. `ChatMessage.to_dict()` 条件性输出 `reasoning_content`
  4. API 请求中包含完整的历史消息（含 reasoning_content）
- **后置条件**: GLM thinking mode 多轮对话不再报 400；其他模型不受影响
- **异常处理**: `reasoning_content` 为空时静默跳过，无异常

#### 规则：reasoning_content 条件性序列化

- **前置条件**: `ChatMessage` 实例含有 `reasoning_content` 字段
- **触发条件**: 调用 `to_dict()` 序列化消息
- **执行逻辑**: 仅当 `reasoning_content` 为非 None 且非空字符串时，才在输出 dict 中包含该键
- **后置条件**: 不含 thinking 的消息序列化结果与变更前完全一致
- **异常处理**: 无

### 4.2 幂等性要求

`from_dict(to_dict(msg))` 往返一致性：对同一 `ChatMessage` 实例，`from_dict(msg.to_dict())` 应产出等价实例。

### 4.3 并发控制

无新增并发场景，遵循现有 `ChatService` 的线程模型。

---

## 非目标

### 5.1 明确排除的功能

- 不变更桥接协议（TUI 侧不需要 reasoning_content）
- 不变更记忆持久化格式（`RoundEntry.assistant_thinking` 已覆盖此场景）
- 不增加 `supports_thinking` capability gate（模型会自行忽略未知字段）
- 不变更非 assistant 角色的消息结构

### 5.2 未来可能扩展

- 若更多模型要求不同的 thinking 字段名（如 `reasoning`、`thought`），可在序列化层做字段名映射
- 若需要控制是否回传 thinking（token 成本考量），可引入 `ProviderCapability` 开关

---

## 测试策略

### 8.1 验收标准

```gherkin
Scenario: reasoning_content 为非空字符串时序列化输出
  Given 一个 assistant ChatMessage，reasoning_content = "思考过程"
  When 调用 to_dict()
  Then 输出 dict 包含 "reasoning_content" 键，值为 "思考过程"

Scenario: reasoning_content 为 None 或空字符串时序列化不输出
  Given 一个 assistant ChatMessage，reasoning_content = None
  When 调用 to_dict()
  Then 输出 dict 不包含 "reasoning_content" 键

Scenario: from_dict 往返一致性
  Given 一个包含 reasoning_content 的 dict
  When 调用 from_dict() 后再调用 to_dict()
  Then 结果 dict 与原始 dict 在 reasoning_content 字段上一致

Scenario: 多轮对话消息历史包含 reasoning_content
  Given ChatService 中已有一轮含 thinking 的 assistant 消息
  When 构造下一轮 API 请求消息列表
  Then 消息列表中 assistant 消息包含 reasoning_content 字段
```

### 8.2 测试用例

| 测试类型 | 覆盖范围 | 优先级 |
|----------|----------|--------|
| 单元测试 | ChatMessage.to_dict() 条件性序列化 | P0 |
| 单元测试 | ChatMessage.from_dict() 反序列化 | P0 |
| 单元测试 | ChatMessage.from_dict(to_dict(msg)) 往返 | P0 |
| 单元测试 | ChatMessage.assistant() 工厂方法 | P1 |
| 单元测试 | ChatService.add_assistant_message() 传递 | P1 |
| 集成测试 | ChatWorkflow 端到端 thinking 传递 | P1 |

### 8.3 边界条件

- `reasoning_content = None`（默认值，最常见场景）
- `reasoning_content = ""`（空串，等同于 None）
- `reasoning_content` 含多行文本、特殊字符
- 非 assistant 角色消息不应携带 `reasoning_content`

---

## 日志实现

本变更不引入新的日志事件。reasoning_content 的写入/读取走现有 `ChatService` 和 `StreamService` 的日志通道，不单独记录。

### 9.1 日志级别规范

沿用项目现有日志规范，无新增。

### 9.2 必须记录的事件

无新增必须记录事件。

### 9.3 日志格式

沿用项目现有日志格式。

### 9.4 敏感信息处理

`reasoning_content` 可能包含模型的完整推理过程，属于对话内容。已在 `sanitize_for_log` 的截断逻辑中覆盖（作为 `ChatMessage.to_dict()` 输出的一部分被现有消息摘要逻辑处理），无需单独脱敏。

### 9.5 日志采样策略

沿用项目现有采样策略，无新增。

---

## 变更历史

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 0.1.0 | 2026-05-18 | arcanexis | 初始版本 |

---

## References

- **ADR**: ADR-004
- **Related Specs**: 无
- **External**: 无