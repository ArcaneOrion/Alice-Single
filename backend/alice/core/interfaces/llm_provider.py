"""
LLM Provider Protocol

定义 LLM 提供商的接口规范
"""

from typing import AsyncIterator, Protocol
from dataclasses import dataclass
from abc import abstractmethod


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
    usage: dict


class LLMProvider(Protocol):
    """LLM 提供商接口"""

    @abstractmethod
    def chat(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        """同步聊天请求"""
        ...

    @abstractmethod
    async def achat(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        """异步聊天请求"""
        ...

    @abstractmethod
    def stream_chat(self, messages: list[ChatMessage], **kwargs) -> iter[StreamChunk]:
        """流式聊天请求"""
        ...

    @abstractmethod
    def count_tokens(self, messages: list[ChatMessage]) -> int:
        """计算 Token 数量"""
        ...
