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
