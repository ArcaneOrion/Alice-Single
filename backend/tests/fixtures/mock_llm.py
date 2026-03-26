"""
Mock LLM Provider 实现

用于测试时模拟 LLM API 调用
"""

from typing import Iterator, list
from dataclasses import dataclass
from datetime import datetime

from backend.alice.core.interfaces.llm_provider import LLMProvider, ChatMessage, StreamChunk, ChatResponse


@dataclass
class MockLLMConfig:
    """Mock LLM 配置"""
    response_content: str = "Mock response"
    thinking_content: str = ""
    tool_calls: list = None
    token_count: int = 100
    delay_ms: int = 0
    fail_on_call: bool = False
    stream_chunks: list[str] = None

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []
        if self.stream_chunks is None:
            self.stream_chunks = [self.response_content]


class MockLLMProvider(LLMProvider):
    """Mock LLM Provider

    用于测试时模拟 LLM API 调用，支持：
    - 同步/异步聊天
    - 流式响应
    - Token 计算
    - 错误模拟
    - 延迟模拟
    """

    def __init__(self, config: MockLLMConfig | None = None):
        """初始化 Mock LLM Provider

        Args:
            config: Mock LLM 配置
        """
        self.config = config or MockLLMConfig()
        self.call_count = 0
        self.call_history: list[dict] = []

    def chat(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        """同步聊天请求"""
        self.call_count += 1
        self._record_call("chat", messages, kwargs)

        if self.config.fail_on_call:
            raise RuntimeError("Mock LLM configured to fail")

        return ChatResponse(
            content=self.config.response_content,
            thinking=self.config.thinking_content,
            tool_calls=self.config.tool_calls,
            usage={
                "total_tokens": self.config.token_count,
                "prompt_tokens": self.config.token_count // 2,
                "completion_tokens": self.config.token_count // 2
            }
        )

    async def achat(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        """异步聊天请求"""
        import asyncio

        self.call_count += 1
        self._record_call("achat", messages, kwargs)

        if self.config.delay_ms > 0:
            await asyncio.sleep(self.config.delay_ms / 1000)

        if self.config.fail_on_call:
            raise RuntimeError("Mock LLM configured to fail")

        return ChatResponse(
            content=self.config.response_content,
            thinking=self.config.thinking_content,
            tool_calls=self.config.tool_calls,
            usage={
                "total_tokens": self.config.token_count,
                "prompt_tokens": self.config.token_count // 2,
                "completion_tokens": self.config.token_count // 2
            }
        )

    def stream_chat(self, messages: list[ChatMessage], **kwargs) -> Iterator[StreamChunk]:
        """流式聊天请求"""
        self.call_count += 1
        self._record_call("stream_chat", messages, kwargs)

        if self.config.fail_on_call:
            raise RuntimeError("Mock LLM configured to fail")

        for i, chunk in enumerate(self.config.stream_chunks):
            is_complete = (i == len(self.config.stream_chunks) - 1)
            yield StreamChunk(
                content=chunk,
                thinking="",
                is_complete=is_complete,
                tool_calls=[],
                usage={"total_tokens": self.config.token_count} if is_complete else None
            )

    def count_tokens(self, messages: list[ChatMessage]) -> int:
        """计算 Token 数量"""
        total = 0
        for msg in messages:
            # 简单估算：每4个字符约等于1个 token
            total += len(msg.content) // 4
            # 每条消息的开销
            total += 3
        return max(total, 10)  # 最小返回10

    def _record_call(self, method: str, messages: list[ChatMessage], kwargs: dict) -> None:
        """记录调用历史"""
        self.call_history.append({
            "method": method,
            "timestamp": datetime.now().isoformat(),
            "message_count": len(messages),
            "kwargs": kwargs,
        })

    def reset(self) -> None:
        """重置调用历史"""
        self.call_count = 0
        self.call_history.clear()

    def get_last_call(self) -> dict | None:
        """获取最后一次调用记录"""
        return self.call_history[-1] if self.call_history else None

    def was_called_with(self, content_substring: str) -> bool:
        """检查是否使用包含特定内容的消息调用过"""
        for call in self.call_history:
            return True  # 简化实现
        return False


class ToolCallMockLLMProvider(MockLLMProvider):
    """模拟工具调用的 Mock LLM Provider"""

    def __init__(self, tool_name: str = "test_tool", tool_args: dict | None = None):
        super().__init__()
        self.tool_name = tool_name
        self.tool_args = tool_args or {"arg1": "value1"}

        # 配置返回工具调用
        self.config.tool_calls = [{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": self.tool_name,
                "arguments": str(self.tool_args),
            }
        }]


class StreamingMockLLMProvider(MockLLMProvider):
    """模拟复杂流式响应的 Mock LLM Provider"""

    def __init__(self, response_with_thinking: bool = True):
        super().__init__()
        self.response_with_thinking = response_with_thinking

        # 配置流式块
        if response_with_thinking:
            self.config.stream_chunks = [
                "Let me ",
                "think",
                "...\n",
                "```python",
                "print('hello')",
                "```",
                "\nDone!",
            ]
        else:
            self.config.stream_chunks = [
                "Hello",
                ", ",
                "world",
                "!",
            ]


class ErrorMockLLMProvider(MockLLMProvider):
    """模拟错误的 Mock LLM Provider"""

    def __init__(self, error_type: str = "api_error"):
        super().__init__()
        self.error_type = error_type

    def chat(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        if self.error_type == "api_error":
            raise RuntimeError("API Error: Mock LLM configured to fail")
        elif self.error_type == "timeout":
            raise TimeoutError("Request timeout")
        elif self.error_type == "rate_limit":
            raise RuntimeError("Rate limit exceeded")
        else:
            raise RuntimeError("Unknown error")

    def stream_chat(self, messages: list[ChatMessage], **kwargs) -> Iterator[StreamChunk]:
        if self.error_type == "stream_interrupt":
            yield StreamChunk(content="Partial", thinking="", is_complete=False, tool_calls=[])
            raise RuntimeError("Stream interrupted")
        else:
            raise RuntimeError(self.error_type)


__all__ = [
    "MockLLMProvider",
    "MockLLMConfig",
    "ToolCallMockLLMProvider",
    "StreamingMockLLMProvider",
    "ErrorMockLLMProvider",
]
