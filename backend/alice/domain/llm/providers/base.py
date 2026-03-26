"""LLM Provider 基类

定义 LLM 提供商的抽象基类和公共接口。
"""

from abc import ABC, abstractmethod
from typing import Iterator, TYPE_CHECKING, Any
import logging

from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.response import ChatResponse, TokenUsage
from backend.alice.domain.llm.models.stream_chunk import StreamChunk

# 使用 TYPE_CHECKING 避免运行时的导入问题
if TYPE_CHECKING:
    from backend.alice.core.interfaces.llm_provider import (
        ChatMessage as InterfaceChatMessage,
        StreamChunk as InterfaceStreamChunk,
        ChatResponse as InterfaceChatResponse,
    )

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """LLM 提供商抽象基类

    实现 LLMProvider 接口，提供公共功能。
    子类需要实现具体的 API 调用逻辑。
    """

    def __init__(self, model_name: str):
        """初始化 Provider

        Args:
            model_name: 模型名称
        """
        self.model_name = model_name
        self._request_count = 0

    @abstractmethod
    def _make_chat_request(
        self,
        messages: list[ChatMessage],
        stream: bool = False,
        **kwargs,
    ):
        """执行实际的聊天请求

        Args:
            messages: 消息列表
            stream: 是否流式返回
            **kwargs: 额外参数

        Returns:
            API 原始响应对象
        """
        pass

    @abstractmethod
    def _extract_stream_chunks(self, response) -> Iterator[StreamChunk]:
        """从流式响应中提取数据块

        Args:
            response: 流式响应对象

        Yields:
            StreamChunk 实例
        """
        pass

    def chat(
        self,
        messages: list[Any],
        **kwargs,
    ) -> ChatResponse:
        """同步聊天请求

        Args:
            messages: 消息列表（ChatMessage 或兼容对象）
            **kwargs: 额外参数

        Returns:
            ChatResponse 响应对象
        """
        # 转换接口消息到内部消息
        internal_messages = self._convert_messages(messages)

        self._request_count += 1
        logger.debug(f"执行聊天请求 #{self._request_count}，模型: {self.model_name}")

        response = self._make_chat_request(internal_messages, stream=False, **kwargs)
        return ChatResponse.from_openai_response(response, self.model_name)

    async def achat(
        self,
        messages: list[Any],
        **kwargs,
    ) -> ChatResponse:
        """异步聊天请求

        默认实现为同步包装，子类可重写为真正的异步实现。

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Returns:
            ChatResponse 响应对象
        """
        return self.chat(messages, **kwargs)

    def stream_chat(
        self,
        messages: list[Any],
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """流式聊天请求

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Yields:
            StreamChunk 流式数据块
        """
        # 转换接口消息到内部消息
        internal_messages = self._convert_messages(messages)

        self._request_count += 1
        logger.debug(f"执行流式聊天请求 #{self._request_count}，模型: {self.model_name}")

        response = self._make_chat_request(internal_messages, stream=True, **kwargs)
        yield from self._extract_stream_chunks(response)

    def _convert_messages(self, messages: list[Any]) -> list[ChatMessage]:
        """转换消息到内部格式

        Args:
            messages: 输入消息列表

        Returns:
            ChatMessage 列表
        """
        result = []
        for m in messages:
            if isinstance(m, ChatMessage):
                result.append(m)
            elif hasattr(m, "role") and hasattr(m, "content"):
                # 兼容接口定义的 ChatMessage
                result.append(ChatMessage.from_dict({"role": m.role, "content": m.content}))
            elif isinstance(m, dict):
                result.append(ChatMessage.from_dict(m))
            else:
                raise TypeError(f"不支持的消息类型: {type(m)}")
        return result

    def count_tokens(self, messages: list[Any]) -> int:
        """计算 Token 数量

        默认实现使用简单的字符估算。
        子类可以重写为更精确的计算方式。

        Args:
            messages: 消息列表

        Returns:
            估算的 token 数量
        """
        total_chars = sum(len(getattr(m, "content", m) if hasattr(m, "content") else str(m)) for m in messages)
        # 粗略估算：英文约 4 字符/token，中文约 2 字符/token
        # 取中间值 3 字符/token
        return max(1, total_chars // 3)

    @property
    def request_count(self) -> int:
        """获取请求计数"""
        return self._request_count


__all__ = ["BaseLLMProvider"]
