from __future__ import annotations

"""
LLM Provider Protocol

定义 LLM 提供商的接口规范。
"""

from typing import Protocol, runtime_checkable, Any, Iterator
from dataclasses import dataclass, field
from abc import abstractmethod


@dataclass(frozen=True)
class ProviderCapability:
    """Provider 能力声明。"""

    supports_tool_calling: bool = True
    supports_streaming: bool = True
    supports_usage_in_stream: bool = True
    supports_thinking: bool = False
    supports_tool_call_delta: bool = True
    supports_extra_headers: bool = True


@dataclass
class ChatMessage:
    """聊天消息"""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class StreamChunk:
    """流式响应块"""

    content: str
    thinking: str  # 思考内容
    is_complete: bool
    tool_calls: list[dict]
    usage: dict | None = None


@dataclass
class ChatResponse:
    """完整聊天响应"""

    content: str
    thinking: str
    tool_calls: list[dict]
    usage: dict = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """LLM 提供商接口。"""

    @property
    def model_name(self) -> str:
        """返回 provider 当前模型名称。"""
        ...

    @property
    def capabilities(self) -> ProviderCapability:
        """返回 provider 能力声明。"""
        ...

    @abstractmethod
    def chat(self, messages: list[ChatMessage], **kwargs: Any) -> ChatResponse:
        """同步聊天请求"""
        ...

    @abstractmethod
    async def achat(self, messages: list[ChatMessage], **kwargs: Any) -> ChatResponse:
        """异步聊天请求"""
        ...

    @abstractmethod
    def stream_chat(self, messages: list[ChatMessage], **kwargs: Any) -> Iterator[StreamChunk]:
        """流式聊天请求"""
        ...

    @abstractmethod
    def count_tokens(self, messages: list[ChatMessage]) -> int:
        """计算 Token 数量"""
        ...


__all__ = [
    "ProviderCapability",
    "ChatMessage",
    "StreamChunk",
    "ChatResponse",
    "LLMProvider",
]
