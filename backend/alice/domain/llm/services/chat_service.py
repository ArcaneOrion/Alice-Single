"""聊天服务

提供高层聊天接口，封装消息管理和上下文维护。
"""

import logging
from typing import Iterator, Callable, Any

from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.response import ChatResponse
from backend.alice.domain.llm.models.stream_chunk import StreamChunk
from backend.alice.domain.llm.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class ChatService:
    """聊天服务

    提供高层聊天接口，管理消息历史和上下文。
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        system_prompt: str = "",
        max_history: int = 50,
    ):
        """初始化聊天服务

        Args:
            provider: LLM Provider 实例
            system_prompt: 系统提示词
            max_history: 最大保留的历史消息数量
        """
        self.provider = provider
        self.system_prompt = system_prompt
        self.max_history = max_history
        self._messages: list[ChatMessage] = []

        # 如果有系统提示词，初始化时添加
        if system_prompt:
            self._messages.append(ChatMessage.system(system_prompt))

    @property
    def messages(self) -> list[ChatMessage]:
        """获取当前消息列表"""
        return list(self._messages)

    @property
    def message_count(self) -> int:
        """获取当前消息数量"""
        return len(self._messages)

    def add_message(self, message: ChatMessage) -> None:
        """添加消息

        Args:
            message: 要添加的消息
        """
        self._messages.append(message)
        self._trim_history()

    def add_user_message(self, content: str) -> ChatMessage:
        """添加用户消息

        Args:
            content: 消息内容

        Returns:
            创建的消息对象
        """
        msg = ChatMessage.user(content)
        self.add_message(msg)
        return msg

    def add_assistant_message(self, content: str, tool_calls: list[dict] | None = None) -> ChatMessage:
        """添加助手消息

        Args:
            content: 消息内容
            tool_calls: 工具调用列表

        Returns:
            创建的消息对象
        """
        msg = ChatMessage.assistant(content, tool_calls)
        self.add_message(msg)
        return msg

    def add_system_message(self, content: str) -> ChatMessage:
        """添加系统消息

        Args:
            content: 消息内容

        Returns:
            创建的消息对象
        """
        msg = ChatMessage.system(content)
        # 系统消息总是放在开头
        if self._messages and self._messages[0].role == "system":
            self._messages[0] = msg
        else:
            self._messages.insert(0, msg)
        return msg

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示词

        Args:
            prompt: 新的系统提示词
        """
        self.system_prompt = prompt
        if self._messages and self._messages[0].role == "system":
            self._messages[0] = ChatMessage.system(prompt)
        else:
            self._messages.insert(0, ChatMessage.system(prompt))

    def clear_history(self, keep_system: bool = True) -> None:
        """清除历史消息

        Args:
            keep_system: 是否保留系统消息
        """
        if keep_system and self._messages and self._messages[0].role == "system":
            self._messages = [self._messages[0]]
        else:
            self._messages = []

    def _trim_history(self) -> None:
        """修剪历史消息，保持在最大限制内"""
        if len(self._messages) <= self.max_history:
            return

        # 保留系统消息和最近的消息
        system_msg = None
        if self._messages and self._messages[0].role == "system":
            system_msg = self._messages[0]

        # 保留最近的 max_history 条消息（不包括系统消息）
        if system_msg:
            self._messages = [system_msg] + self._messages[-self.max_history :]
        else:
            self._messages = self._messages[-self.max_history :]

        logger.debug(f"修剪历史消息，当前数量: {len(self._messages)}")

    def chat(
        self,
        user_input: str,
        **kwargs,
    ) -> ChatResponse:
        """执行同步聊天

        Args:
            user_input: 用户输入
            **kwargs: 额外参数

        Returns:
            聊天响应
        """
        self.add_user_message(user_input)

        response = self.provider.chat(self._messages, **kwargs)

        # 添加助手响应到历史
        self.add_assistant_message(response.content, response.tool_calls)

        return response

    def stream_chat(
        self,
        user_input: str,
        on_chunk: Callable[[StreamChunk], None] | None = None,
        **kwargs,
    ) -> ChatResponse:
        """执行流式聊天

        Args:
            user_input: 用户输入
            on_chunk: 可选的块处理回调
            **kwargs: 额外参数

        Returns:
            聊天响应
        """
        self.add_user_message(user_input)

        full_content = ""
        full_thinking = ""
        all_tool_calls: list[dict] = []
        usage = None

        for chunk in self.provider.stream_chat(self._messages, **kwargs):
            if on_chunk:
                on_chunk(chunk)

            full_content += chunk.content
            full_thinking += chunk.thinking

            if chunk.usage:
                usage = chunk.usage

            if chunk.is_complete:
                break

        # 构建响应
        response = ChatResponse(
            content=full_content,
            thinking=full_thinking,
            tool_calls=all_tool_calls,
            usage=usage,
            model=self.provider.model_name,
        )

        # 添加助手响应到历史
        self.add_assistant_message(response.content, response.tool_calls)

        return response

    def count_tokens(self) -> int:
        """计算当前消息列表的 token 数量

        Returns:
            估算的 token 数量
        """
        return self.provider.count_tokens(self._messages)

    def get_history_text(self, include_system: bool = True) -> str:
        """获取历史消息的文本表示

        Args:
            include_system: 是否包含系统消息

        Returns:
            历史消息文本
        """
        messages = self._messages if include_system else [m for m in self._messages if m.role != "system"]

        lines = []
        for msg in messages:
            lines.append(f"[{msg.role.upper()}]: {msg.content}")

        return "\n\n".join(lines)


__all__ = ["ChatService"]
