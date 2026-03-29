"""LLM Provider 基类

定义 LLM 提供商的抽象基类和公共接口。
"""

from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Mapping
import logging
from typing import Iterator, TYPE_CHECKING, Any

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

TASKS_LOG_CATEGORY = "tasks"
SENSITIVE_FIELD_MARKERS = (
    "api_key",
    "api-key",
    "authorization",
    "token",
    "secret",
    "password",
    "cookie",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    return any(marker in normalized for marker in SENSITIVE_FIELD_MARKERS)


def _mask_secret(value: Any) -> str:
    text = "" if value is None else str(value)
    if not text:
        return "***"
    if len(text) <= 6:
        return "*" * len(text)
    return f"{text[:4]}...{text[-2:]}"


def sanitize_for_log(value: Any) -> Any:
    """将值转换为适合日志输出的安全 JSON 结构。"""
    if value is None or isinstance(value, bool | int | float | str):
        return value

    if hasattr(value, "model_dump"):
        try:
            return sanitize_for_log(value.model_dump())
        except Exception:
            return str(value)

    if hasattr(value, "to_dict"):
        try:
            return sanitize_for_log(value.to_dict())
        except Exception:
            return str(value)

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                sanitized[key_text] = _mask_secret(item)
            else:
                sanitized[key_text] = sanitize_for_log(item)
        return sanitized

    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_log(item) for item in value]

    return str(value)


def summarize_messages(messages: list[Any]) -> dict[str, Any]:
    """汇总消息角色分布和长度，用于请求日志。"""
    role_counter: Counter[str] = Counter()
    total_characters = 0
    tool_call_message_count = 0

    for message in messages:
        role = getattr(message, "role", None)
        if role is None and isinstance(message, dict):
            role = message.get("role")
        role_counter[str(role or "unknown")] += 1

        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        total_characters += len(content or "")

        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls is None and isinstance(message, dict):
            tool_calls = message.get("tool_calls")
        if tool_calls:
            tool_call_message_count += 1

    return {
        "message_count": len(messages),
        "role_distribution": dict(role_counter),
        "total_characters": total_characters,
        "tool_call_message_count": tool_call_message_count,
    }


def usage_to_log_data(usage: Any) -> dict[str, int]:
    """提取 token 使用信息。"""
    if usage is None:
        return {}

    if isinstance(usage, dict):
        return {
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
        }

    return {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def build_error_payload(error: BaseException, **extra: Any) -> dict[str, Any]:
    """构建统一错误日志字段。"""
    payload = {
        "type": type(error).__name__,
        "message": str(error),
    }
    for key, value in extra.items():
        if value is not None:
            payload[key] = sanitize_for_log(value)
    return payload


def extract_observability_context(
    kwargs: dict[str, Any] | None,
    *,
    component: str,
    phase: str,
    payload_kind: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """统一抽取 trace/request/task/session/span 上下文。"""
    request_kwargs = kwargs or {}
    metadata = request_kwargs.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    trace_id = (
        metadata.get("trace_id")
        or request_kwargs.get("trace_id")
        or metadata.get("request_id")
        or request_kwargs.get("request_id")
        or ""
    )
    request_id = metadata.get("request_id") or request_kwargs.get("request_id") or trace_id or ""
    task_id = (
        metadata.get("task_id")
        or request_kwargs.get("task_id")
        or request_id
        or trace_id
        or ""
    )
    session_id = metadata.get("session_id") or request_kwargs.get("session_id") or ""
    span_id = metadata.get("span_id") or request_kwargs.get("span_id") or ""

    base_context = {
        "trace_id": trace_id,
        "request_id": request_id,
        "task_id": task_id,
        "session_id": session_id,
        "span_id": span_id,
        "component": component,
        "phase": phase,
        "payload_kind": payload_kind,
    }
    if context:
        base_context.update(sanitize_for_log(context))
    return base_context


def emit_observability_log(
    target_logger: logging.Logger,
    *,
    level: int,
    event_type: str,
    component: str,
    phase: str,
    payload_kind: str,
    kwargs: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    timing: dict[str, Any] | None = None,
    message: str | None = None,
    exc_info: Any = None,
) -> None:
    """按统一 envelope 记录结构化观测日志。"""
    log_context = extract_observability_context(
        kwargs,
        component=component,
        phase=phase,
        payload_kind=payload_kind,
        context=context,
    )
    log_data = sanitize_for_log(data or {})
    log_timing = sanitize_for_log(timing or {})
    if log_timing:
        log_data = {**log_data, "timing": log_timing}

    extra = {
        "event_type": event_type,
        "log_category": TASKS_LOG_CATEGORY,
        "trace_id": log_context["trace_id"],
        "request_id": log_context["request_id"],
        "task_id": log_context["task_id"],
        "session_id": log_context["session_id"],
        "span_id": log_context["span_id"],
        "component": component,
        "phase": phase,
        "timing": log_timing,
        "payload_kind": payload_kind,
        "context": log_context,
        "data": log_data,
    }
    if error is not None:
        extra["error"] = sanitize_for_log(error)

    target_logger.log(level, message or event_type, extra=extra, exc_info=exc_info)


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

    def _emit_log(
        self,
        *,
        event_type: str,
        phase: str,
        payload_kind: str,
        kwargs: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        timing: dict[str, Any] | None = None,
        level: int = logging.INFO,
        message: str | None = None,
        exc_info: Any = None,
        component: str = "llm.provider.base",
    ) -> None:
        emit_observability_log(
            logger,
            level=level,
            event_type=event_type,
            component=component,
            phase=phase,
            payload_kind=payload_kind,
            kwargs=kwargs,
            context=context,
            data=data,
            error=error,
            timing=timing,
            message=message,
            exc_info=exc_info,
        )

    def _log_prompt_built(
        self,
        messages: list[ChatMessage],
        *,
        stream: bool,
        kwargs: dict[str, Any],
        operation: str,
    ) -> None:
        message_summary = summarize_messages(messages)
        payload = {
            "provider": self.__class__.__name__,
            "model": self.model_name,
            "operation": operation,
            "stream": stream,
            "request_count": self.request_count,
            "messages": sanitize_for_log([message.to_dict() for message in messages]),
            **message_summary,
            "request_kwargs": sanitize_for_log(kwargs),
        }
        self._emit_log(
            event_type="model.prompt_built",
            phase="prepare",
            payload_kind="messages",
            kwargs=kwargs,
            data=payload,
            component="llm.provider.base",
        )

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
        self._log_prompt_built(
            internal_messages,
            stream=False,
            kwargs=kwargs,
            operation="chat",
        )

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
        self._log_prompt_built(
            internal_messages,
            stream=True,
            kwargs=kwargs,
            operation="stream_chat",
        )

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
