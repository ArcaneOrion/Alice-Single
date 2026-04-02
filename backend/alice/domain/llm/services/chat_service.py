"""聊天服务

提供高层聊天接口，封装消息管理和上下文维护。
"""

import logging
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.response import ChatResponse
from backend.alice.domain.llm.models.stream_chunk import StreamChunk
from backend.alice.domain.llm.providers.base import BaseLLMProvider
from backend.alice.domain.llm.services.stream_service import (
    merge_tool_call_state,
    normalized_tool_calls,
    token_usage_from_chunk_usage,
)

logger = logging.getLogger(__name__)


class RequestEnvelopeLike(Protocol):
    def to_dict(self) -> dict[str, Any]:
        """将 envelope 投影为统一 dict。"""


class ChatService:
    """聊天服务

    提供高层聊天接口，管理消息历史和上下文。
    """

    _MODEL_VISIBLE_CONTEXT_LABELS = {
        "memory_snapshot": "Memory snapshot",
        "memory": "Memory snapshot",
        "skill_snapshot": "Skill snapshot",
        "skills": "Skill snapshot",
        "tool_history": "Tool history",
        "local_time": "Local time",
    }

    _MODEL_VISIBLE_CONTEXT_ORDER = (
        "local_time",
        "memory_snapshot",
        "memory",
        "skill_snapshot",
        "skills",
        "tool_history",
    )

    _MODEL_VISIBLE_SCALAR_ORDER = (
        "current_question",
        "current_input",
        "question",
    )

    _MODEL_VISIBLE_SCALAR_LABELS = {
        "current_question": "Current question",
        "current_input": "Current input",
        "question": "Question",
    }

    _MODEL_VISIBLE_EXCLUDED_KEYS = {
        "system",
        "user",
        "request_metadata",
        "metadata",
        "tools",
    }

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
        self.max_history = max_history
        self._base_system_prompt = system_prompt
        self._runtime_context: dict[str, Any] = {}
        self._messages: list[ChatMessage] = []
        self._sync_system_message()

    @property
    def messages(self) -> list[ChatMessage]:
        """获取当前消息列表"""
        return list(self._messages)

    @property
    def message_count(self) -> int:
        """获取当前消息数量"""
        return len(self._messages)

    @property
    def system_prompt(self) -> str:
        """获取基础系统提示词。"""
        return self._base_system_prompt

    @property
    def runtime_context(self) -> dict[str, Any]:
        """获取结构化运行时上下文。"""
        return dict(self._runtime_context)

    @classmethod
    def _prune_runtime_context(cls, value: Any) -> Any:
        """移除空字段，保持运行时上下文紧凑。"""
        if isinstance(value, dict):
            cleaned = {}
            for key, item in value.items():
                normalized = cls._prune_runtime_context(item)
                if normalized in (None, "", [], {}):
                    continue
                cleaned[key] = normalized
            return cleaned

        if isinstance(value, list):
            cleaned_items = []
            for item in value:
                normalized = cls._prune_runtime_context(item)
                if normalized in (None, "", [], {}):
                    continue
                cleaned_items.append(normalized)
            return cleaned_items

        if isinstance(value, str):
            return value.strip()

        return value

    @staticmethod
    def _format_mapping_lines(value: Mapping[str, Any], indent: int = 2) -> list[str]:
        lines: list[str] = []
        prefix = " " * indent
        for key, item in value.items():
            if isinstance(item, Mapping):
                nested = ChatService._format_mapping_lines(item, indent + 2)
                if not nested:
                    continue
                lines.append(f"{prefix}{key}:")
                lines.extend(nested)
                continue
            if isinstance(item, list):
                nested = ChatService._format_list_lines(item, indent + 2)
                if not nested:
                    continue
                lines.append(f"{prefix}{key}:")
                lines.extend(nested)
                continue
            if item in (None, "", [], {}):
                continue
            lines.append(f"{prefix}{key}: {item}")
        return lines

    @staticmethod
    def _format_list_lines(value: list[Any], indent: int = 2) -> list[str]:
        lines: list[str] = []
        prefix = " " * indent
        for item in value:
            if isinstance(item, Mapping):
                nested = ChatService._format_mapping_lines(item, indent + 2)
                if not nested:
                    continue
                lines.append(f"{prefix}-")
                lines.extend(nested)
                continue
            if isinstance(item, list):
                nested = ChatService._format_list_lines(item, indent + 2)
                if not nested:
                    continue
                lines.append(f"{prefix}-")
                lines.extend(nested)
                continue
            if item in (None, "", [], {}):
                continue
            lines.append(f"{prefix}- {item}")
        return lines

    @staticmethod
    def _format_context_block(label: str, value: Any) -> str:
        if isinstance(value, Mapping):
            lines = ChatService._format_mapping_lines(value)
            if not lines:
                return ""
            return f"{label}:\n" + "\n".join(lines)

        if isinstance(value, list):
            lines = ChatService._format_list_lines(value)
            if not lines:
                return ""
            return f"{label}:\n" + "\n".join(lines)

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return ""
            return f"{label}: {text}"

        if value in (None, "", [], {}):
            return ""
        return f"{label}: {value}"

    @classmethod
    def _render_model_visible_context(cls, runtime_context: dict[str, Any] | None) -> str:
        context_payload = cls._prune_runtime_context(runtime_context or {})
        if not context_payload or not isinstance(context_payload, dict):
            return ""

        visible_lines: list[str] = []

        user_payload = context_payload.get("user")
        if isinstance(user_payload, Mapping):
            for key in cls._MODEL_VISIBLE_SCALAR_ORDER:
                value = user_payload.get(key)
                if isinstance(value, str) and value.strip():
                    visible_lines.append(f"{cls._MODEL_VISIBLE_SCALAR_LABELS[key]}: {value.strip()}")
            local_time = user_payload.get("local_time")
            if isinstance(local_time, Mapping):
                block = cls._format_context_block("Local time", local_time)
                if block:
                    visible_lines.append(block)

        for key in cls._MODEL_VISIBLE_CONTEXT_ORDER:
            if key == "local_time" and isinstance(user_payload, Mapping):
                continue
            value = context_payload.get(key)
            if key not in cls._MODEL_VISIBLE_CONTEXT_LABELS:
                continue
            block = cls._format_context_block(cls._MODEL_VISIBLE_CONTEXT_LABELS[key], value)
            if block:
                visible_lines.append(block)

        for key, value in context_payload.items():
            if key in cls._MODEL_VISIBLE_CONTEXT_ORDER or key in cls._MODEL_VISIBLE_EXCLUDED_KEYS:
                continue
            if key in cls._MODEL_VISIBLE_SCALAR_ORDER and isinstance(value, str) and value.strip():
                visible_lines.append(f"{cls._MODEL_VISIBLE_SCALAR_LABELS[key]}: {value.strip()}")
                continue
            block = cls._format_context_block(key.replace("_", " ").title(), value)
            if block:
                visible_lines.append(block)

        return "\n\n".join(visible_lines)

    @classmethod
    def _compose_prompt_with_context(
        cls,
        base_prompt: str,
        runtime_context: dict[str, Any] | None,
    ) -> str:
        base_prompt = (base_prompt or "").strip()
        model_visible_context = cls._render_model_visible_context(runtime_context)
        if base_prompt and model_visible_context:
            return f"{base_prompt}\n\n{model_visible_context}"
        if model_visible_context:
            return model_visible_context
        return base_prompt

    def _compose_system_prompt(self) -> str:
        """组合基础系统提示词与模型可见上下文。"""
        return self._compose_prompt_with_context(self._base_system_prompt, self._runtime_context)

    def _sync_system_message(self) -> None:
        """同步系统消息到消息列表首位。"""
        composed_prompt = self._compose_system_prompt()
        if composed_prompt:
            system_message = ChatMessage.system(composed_prompt)
            if self._messages and self._messages[0].role == "system":
                self._messages[0] = system_message
            else:
                self._messages.insert(0, system_message)
            return

        if self._messages and self._messages[0].role == "system":
            self._messages.pop(0)

    def set_runtime_context(self, runtime_context: dict[str, Any] | None) -> dict[str, Any]:
        """替换运行时上下文。"""
        normalized = self._prune_runtime_context(runtime_context or {})
        self._runtime_context = normalized if isinstance(normalized, dict) else {}
        self._sync_system_message()
        return self.runtime_context

    def update_runtime_context(self, runtime_context: dict[str, Any] | None) -> dict[str, Any]:
        """合并运行时上下文。"""
        merged = {**self._runtime_context}
        for key, value in (runtime_context or {}).items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        return self.set_runtime_context(merged)

    def build_request_messages(
        self,
        runtime_context: dict[str, Any] | None = None,
        request_envelope: RequestEnvelopeLike | Mapping[str, Any] | None = None,
    ) -> list[ChatMessage]:
        """构造一次性 provider request messages，不污染持久历史。"""
        if request_envelope:
            return self._build_request_messages_from_envelope(request_envelope)
        if not runtime_context:
            return list(self._messages)

        composed_prompt = self._compose_system_prompt_for(runtime_context)
        if not composed_prompt:
            return [message for message in self._messages if message.role != "system"]

        request_messages = list(self._messages)
        system_message = ChatMessage.system(composed_prompt)
        if request_messages and request_messages[0].role == "system":
            request_messages[0] = system_message
        else:
            request_messages.insert(0, system_message)
        return request_messages

    def _build_request_messages_from_envelope(
        self,
        request_envelope: RequestEnvelopeLike | Mapping[str, Any],
    ) -> list[ChatMessage]:
        envelope = self._request_envelope_to_dict(request_envelope)
        if envelope is None:
            return list(self._messages)

        system_payload = envelope.get("system")
        system_prompt = self._base_system_prompt or ""
        if isinstance(system_payload, Mapping):
            prompt = system_payload.get("prompt")
            if isinstance(prompt, str):
                system_prompt = prompt

        model_context = envelope.get("model_context")
        runtime_context = dict(model_context) if isinstance(model_context, Mapping) else {}
        tool_history = envelope.get("tool_history")
        if isinstance(tool_history, list) and tool_history:
            runtime_context["tool_history"] = list(tool_history)

        system_prompt = self._compose_system_prompt_for(runtime_context, base_prompt=system_prompt)
        request_messages: list[ChatMessage] = []
        if system_prompt:
            request_messages.append(ChatMessage.system(system_prompt))
        for message in envelope.get("messages") or []:
            if isinstance(message, dict):
                request_messages.append(ChatMessage.from_dict(message))
        return request_messages or list(self._messages)

    @staticmethod
    def _request_envelope_to_dict(
        request_envelope: RequestEnvelopeLike | Mapping[str, Any],
    ) -> dict[str, Any] | None:
        if isinstance(request_envelope, Mapping):
            return dict(request_envelope)

        to_dict = getattr(request_envelope, "to_dict", None)
        if not callable(to_dict):
            return None

        payload = to_dict()
        if not isinstance(payload, Mapping):
            return None
        return dict(payload)

    def _compose_system_prompt_for(
        self,
        runtime_context: dict[str, Any] | None,
        *,
        base_prompt: str | None = None,
    ) -> str:
        base_prompt_value = self._base_system_prompt if base_prompt is None else base_prompt
        return self._compose_prompt_with_context(base_prompt_value or "", runtime_context)

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
        self._base_system_prompt = content
        self._sync_system_message()
        return self._messages[0]

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示词

        Args:
            prompt: 新的系统提示词
        """
        self._base_system_prompt = prompt
        self._sync_system_message()

    def add_tool_message(self, content: str, tool_call_id: str) -> ChatMessage:
        """添加工具结果消息。"""
        msg = ChatMessage.tool(content, tool_call_id)
        self.add_message(msg)
        return msg

    def clear_history(self, keep_system: bool = True) -> None:
        """清除历史消息

        Args:
            keep_system: 是否保留系统消息
        """
        if keep_system:
            composed_prompt = self._compose_system_prompt()
            self._messages = [ChatMessage.system(composed_prompt)] if composed_prompt else []
        else:
            self._messages = []

    def _trim_history(self) -> None:
        """修剪历史消息，保持在最大限制内"""
        if len(self._messages) <= self.max_history:
            return

        system_msg = None
        if self._messages and self._messages[0].role == "system":
            system_msg = self._messages[0]

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
        usage = None
        tool_call_state: dict[int, dict] = {}

        for chunk in self.provider.stream_chat(self._messages, **kwargs):
            if on_chunk:
                on_chunk(chunk)

            full_content += chunk.content
            full_thinking += chunk.thinking

            if chunk.tool_calls:
                merge_tool_call_state(tool_call_state, chunk.tool_calls)

            if chunk.usage:
                usage = token_usage_from_chunk_usage(chunk.usage)

            if chunk.is_complete:
                break

        response = ChatResponse(
            content=full_content,
            thinking=full_thinking,
            tool_calls=normalized_tool_calls(tool_call_state),
            usage=usage,
            model=self.provider.model_name,
        )

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
