"""流处理服务

提供 LLM 流式响应的高级处理功能。
"""

import logging
import time
from typing import Any, Callable, Iterator

from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.response import ChatResponse, TokenUsage
from backend.alice.domain.llm.providers.base import (
    BaseLLMProvider,
    build_error_payload,
    emit_observability_log,
    sanitize_for_log,
    usage_to_log_data,
)
from backend.alice.domain.llm.parsers.stream_parser import (
    StreamParser,
    StreamParserConfig,
    ParsedStreamMessage,
    StreamMessageType,
)

logger = logging.getLogger(__name__)


def _tool_call_delta_to_dict(tool_call: Any) -> dict[str, Any]:
    return sanitize_for_log(
        {
            "index": getattr(tool_call, "index", 0),
            "id": getattr(tool_call, "id", None),
            "type": getattr(tool_call, "type", None),
            "function_name": getattr(tool_call, "function_name", None),
            "function_arguments": getattr(tool_call, "function_arguments", None),
        }
    )


def _merge_tool_call_state(
    tool_call_state: dict[int, dict[str, Any]],
    tool_calls: list[Any],
) -> list[dict[str, Any]]:
    for tool_call in tool_calls:
        index = int(getattr(tool_call, "index", 0) or 0)
        current = tool_call_state.setdefault(
            index,
            {
                "index": index,
                "id": None,
                "type": None,
                "function_name": None,
                "function_arguments": "",
            },
        )
        if getattr(tool_call, "id", None):
            current["id"] = tool_call.id
        if getattr(tool_call, "type", None):
            current["type"] = tool_call.type
        if getattr(tool_call, "function_name", None):
            current["function_name"] = tool_call.function_name
        if getattr(tool_call, "function_arguments", None):
            current["function_arguments"] += tool_call.function_arguments

    return _tool_call_state_to_list(tool_call_state)


def _tool_call_state_to_list(tool_call_state: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    return [sanitize_for_log(tool_call_state[index]) for index in sorted(tool_call_state)]


def _messages_to_log_data(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    return sanitize_for_log([message.to_dict() for message in messages])


class StreamService:
    """流处理服务

    提供流式响应的处理和转换功能。
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        parser_config: StreamParserConfig | None = None,
    ):
        """初始化流处理服务

        Args:
            provider: LLM Provider 实例
            parser_config: 流解析器配置
        """
        self.provider = provider
        self.parser_config = parser_config or StreamParserConfig()

    def _emit_stream_log(
        self,
        *,
        event_type: str,
        phase: str,
        payload_kind: str,
        kwargs: dict[str, Any],
        data: dict[str, Any],
        error: dict[str, Any] | None = None,
        timing: dict[str, Any] | None = None,
        level: int = logging.INFO,
        message: str | None = None,
        exc_info: Any = None,
    ) -> None:
        emit_observability_log(
            logger,
            level=level,
            event_type=event_type,
            component="llm.stream_service",
            phase=phase,
            payload_kind=payload_kind,
            kwargs=kwargs,
            data=data,
            error=error,
            timing=timing,
            message=message,
            exc_info=exc_info,
        )

    def _log_stream_chunk(
        self,
        *,
        operation: str,
        kwargs: dict[str, Any],
        chunk: Any,
        chunk_index: int,
        started_at: float,
        tool_call_state: dict[int, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        aggregated_tool_calls = _merge_tool_call_state(tool_call_state, chunk.tool_calls)
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 3)

        self._emit_stream_log(
            event_type="model.stream_chunk",
            phase="stream",
            payload_kind="stream_chunk",
            kwargs=kwargs,
            data={
                "operation": operation,
                "model": self.provider.model_name,
                "chunk_index": chunk_index,
                "has_content": bool(chunk.content),
                "has_thinking": bool(chunk.thinking),
                "has_tool_calls": bool(chunk.tool_calls),
                "has_usage": chunk.usage is not None,
                "content_delta": chunk.content,
                "thinking_delta": chunk.thinking,
                "tool_calls_delta": [_tool_call_delta_to_dict(tool_call) for tool_call in chunk.tool_calls],
                "tool_calls_aggregated": aggregated_tool_calls,
                "usage": usage_to_log_data(chunk.usage),
                "is_complete": chunk.is_complete,
            },
            timing={"latency_ms": elapsed_ms},
            message="model.stream_chunk",
        )

        if chunk.tool_calls:
            self._emit_stream_log(
                event_type="model.tool_decision",
                phase="stream",
                payload_kind="tool_calls",
                kwargs=kwargs,
                data={
                    "operation": operation,
                    "model": self.provider.model_name,
                    "chunk_index": chunk_index,
                    "tool_calls_delta": [_tool_call_delta_to_dict(tool_call) for tool_call in chunk.tool_calls],
                    "tool_calls_aggregated": aggregated_tool_calls,
                },
                timing={"latency_ms": elapsed_ms},
                message="model.tool_decision",
            )

        return aggregated_tool_calls

    def _log_stream_completed(
        self,
        *,
        operation: str,
        kwargs: dict[str, Any],
        started_at: float,
        chunk_count: int,
        full_content: str,
        full_thinking: str,
        usage: Any,
        tool_call_state: dict[int, dict[str, Any]],
    ) -> None:
        self._emit_stream_log(
            event_type="model.stream_completed",
            phase="complete",
            payload_kind="stream_result",
            kwargs=kwargs,
            data={
                "operation": operation,
                "model": self.provider.model_name,
                "chunk_count": chunk_count,
                "content": full_content,
                "thinking": full_thinking,
                "content_length": len(full_content),
                "thinking_length": len(full_thinking),
                "output_length": len(full_content) + len(full_thinking),
                "usage": usage_to_log_data(usage),
                "tool_calls_aggregated": _tool_call_state_to_list(tool_call_state),
            },
            timing={"latency_ms": round((time.perf_counter() - started_at) * 1000, 3)},
            message="model.stream_completed",
        )

    def _log_stream_error(
        self,
        *,
        operation: str,
        kwargs: dict[str, Any],
        started_at: float,
        chunk_count: int,
        full_content: str,
        full_thinking: str,
        usage: Any,
        tool_call_state: dict[int, dict[str, Any]],
        error: BaseException,
    ) -> None:
        self._emit_stream_log(
            event_type="api.error",
            phase="error",
            payload_kind="stream",
            kwargs=kwargs,
            data={
                "operation": operation,
                "model": self.provider.model_name,
                "chunk_count": chunk_count,
                "content_length": len(full_content),
                "thinking_length": len(full_thinking),
                "usage": usage_to_log_data(usage),
                "tool_calls_aggregated": _tool_call_state_to_list(tool_call_state),
            },
            error=build_error_payload(error),
            timing={"latency_ms": round((time.perf_counter() - started_at) * 1000, 3)},
            level=logging.ERROR,
            message="api.error",
            exc_info=True,
        )

    def _log_stream_started(
        self,
        *,
        operation: str,
        messages: list[ChatMessage],
        kwargs: dict[str, Any],
    ) -> None:
        self._emit_stream_log(
            event_type="model.stream_started",
            phase="start",
            payload_kind="messages",
            kwargs=kwargs,
            data={
                "operation": operation,
                "model": self.provider.model_name,
                "message_count": len(messages),
                "messages": _messages_to_log_data(messages),
            },
            message="model.stream_started",
        )

    def stream_with_parser(
        self,
        messages: list[ChatMessage],
        on_message: Callable[[ParsedStreamMessage], None] | None = None,
        **kwargs,
    ) -> tuple[str, str]:
        """执行流式请求并解析输出

        Args:
            messages: 消息列表
            on_message: 消息回调
            **kwargs: 额外参数

        Returns:
            (完整内容, 完整思考内容)
        """
        parser = StreamParser(self.parser_config)
        full_content = ""
        full_thinking = ""
        usage = None
        chunk_count = 0
        started_at = time.perf_counter()
        tool_call_state: dict[int, dict[str, Any]] = {}
        self._log_stream_started(operation="stream_with_parser", messages=messages, kwargs=kwargs)

        try:
            for chunk in self.provider.stream_chat(messages, **kwargs):
                chunk_count += 1
                if chunk.usage:
                    usage = chunk.usage
                self._log_stream_chunk(
                    operation="stream_with_parser",
                    kwargs=kwargs,
                    chunk=chunk,
                    chunk_index=chunk_count,
                    started_at=started_at,
                    tool_call_state=tool_call_state,
                )

                # 处理内容块
                if chunk.content:
                    parsed = parser.process_chunk(chunk.content)
                    for msg in parsed:
                        if msg.type == StreamMessageType.CONTENT:
                            full_content += msg.content
                        elif msg.type == StreamMessageType.THINKING:
                            full_thinking += msg.content

                        if on_message:
                            on_message(msg)

                # 处理思考内容（直接来自模型）
                if chunk.thinking:
                    if on_message:
                        on_message(
                            ParsedStreamMessage(type=StreamMessageType.THINKING, content=chunk.thinking)
                        )
                    full_thinking += chunk.thinking

                if chunk.is_complete:
                    break

            # 冲刷剩余内容
            remaining = parser.flush()
            for msg in remaining:
                if msg.type == StreamMessageType.CONTENT:
                    full_content += msg.content
                elif msg.type == StreamMessageType.THINKING:
                    full_thinking += msg.content

                if on_message:
                    on_message(msg)
        except Exception as e:
            self._log_stream_error(
                operation="stream_with_parser",
                kwargs=kwargs,
                started_at=started_at,
                chunk_count=chunk_count,
                full_content=full_content,
                full_thinking=full_thinking,
                usage=usage,
                tool_call_state=tool_call_state,
                error=e,
            )
            raise

        self._log_stream_completed(
            operation="stream_with_parser",
            kwargs=kwargs,
            started_at=started_at,
            chunk_count=chunk_count,
            full_content=full_content,
            full_thinking=full_thinking,
            usage=usage,
            tool_call_state=tool_call_state,
        )

        return full_content, full_thinking

    def stream_to_ui(
        self,
        messages: list[ChatMessage],
        emit_callback: Callable[[dict], None],
        **kwargs,
    ) -> tuple[str, str, TokenUsage | None]:
        """执行流式请求并格式化输出到 UI

        Args:
            messages: 消息列表
            emit_callback: UI 发送回调（接收字典）
            **kwargs: 额外参数

        Returns:
            (完整内容, 完整思考内容, Token 使用)
        """
        parser = StreamParser(self.parser_config)
        full_content = ""
        full_thinking = ""
        usage = None
        chunk_count = 0
        started_at = time.perf_counter()
        tool_call_state: dict[int, dict[str, Any]] = {}
        self._log_stream_started(operation="stream_to_ui", messages=messages, kwargs=kwargs)

        # 发送开始状态
        emit_callback({"type": "status", "content": "thinking"})

        try:
            for chunk in self.provider.stream_chat(messages, **kwargs):
                chunk_count += 1
                self._log_stream_chunk(
                    operation="stream_to_ui",
                    kwargs=kwargs,
                    chunk=chunk,
                    chunk_index=chunk_count,
                    started_at=started_at,
                    tool_call_state=tool_call_state,
                )
                # 处理 Token 使用
                if chunk.usage:
                    usage = TokenUsage(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                        total_tokens=chunk.usage.total_tokens,
                    )
                    emit_callback(
                        {
                            "type": "tokens",
                            "total": usage.total_tokens,
                            "prompt": usage.prompt_tokens,
                            "completion": usage.completion_tokens,
                        }
                    )

                # 处理内容块
                if chunk.content:
                    parsed = parser.process_chunk(chunk.content)
                    for msg in parsed:
                        emit_callback(msg.to_dict())

                        if msg.type == StreamMessageType.CONTENT:
                            full_content += msg.content
                        elif msg.type == StreamMessageType.THINKING:
                            full_thinking += msg.content

                # 处理思考内容
                if chunk.thinking:
                    emit_callback({"type": "thinking", "content": chunk.thinking})
                    full_thinking += chunk.thinking

                if chunk.is_complete:
                    break

            # 冲刷剩余内容
            remaining = parser.flush()
            for msg in remaining:
                emit_callback(msg.to_dict())
                if msg.type == StreamMessageType.CONTENT:
                    full_content += msg.content
                elif msg.type == StreamMessageType.THINKING:
                    full_thinking += msg.content
        except Exception as e:
            self._log_stream_error(
                operation="stream_to_ui",
                kwargs=kwargs,
                started_at=started_at,
                chunk_count=chunk_count,
                full_content=full_content,
                full_thinking=full_thinking,
                usage=usage,
                tool_call_state=tool_call_state,
                error=e,
            )
            raise

        # 发送完成状态
        emit_callback({"type": "status", "content": "done"})

        self._log_stream_completed(
            operation="stream_to_ui",
            kwargs=kwargs,
            started_at=started_at,
            chunk_count=chunk_count,
            full_content=full_content,
            full_thinking=full_thinking,
            usage=usage,
            tool_call_state=tool_call_state,
        )

        return full_content, full_thinking, usage

    def stream_collect(
        self,
        messages: list[ChatMessage],
        **kwargs,
    ) -> ChatResponse:
        """执行流式请求并收集完整响应

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Returns:
            完整聊天响应
        """
        full_content = ""
        full_thinking = ""
        all_tool_calls: list[dict] = []
        usage = None
        chunk_count = 0
        started_at = time.perf_counter()
        tool_call_state: dict[int, dict[str, Any]] = {}
        self._log_stream_started(operation="stream_collect", messages=messages, kwargs=kwargs)

        try:
            for chunk in self.provider.stream_chat(messages, **kwargs):
                chunk_count += 1
                self._log_stream_chunk(
                    operation="stream_collect",
                    kwargs=kwargs,
                    chunk=chunk,
                    chunk_index=chunk_count,
                    started_at=started_at,
                    tool_call_state=tool_call_state,
                )
                full_content += chunk.content
                full_thinking += chunk.thinking

                if chunk.usage:
                    usage = TokenUsage(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                        total_tokens=chunk.usage.total_tokens,
                    )

                if chunk.is_complete:
                    break
        except Exception as e:
            self._log_stream_error(
                operation="stream_collect",
                kwargs=kwargs,
                started_at=started_at,
                chunk_count=chunk_count,
                full_content=full_content,
                full_thinking=full_thinking,
                usage=usage,
                tool_call_state=tool_call_state,
                error=e,
            )
            raise

        self._log_stream_completed(
            operation="stream_collect",
            kwargs=kwargs,
            started_at=started_at,
            chunk_count=chunk_count,
            full_content=full_content,
            full_thinking=full_thinking,
            usage=usage,
            tool_call_state=tool_call_state,
        )

        return ChatResponse(
            content=full_content,
            thinking=full_thinking,
            tool_calls=all_tool_calls,
            usage=usage,
            model=self.provider.model_name,
        )

    def stream_iter(
        self,
        messages: list[ChatMessage],
        **kwargs,
    ) -> Iterator[ParsedStreamMessage]:
        """执行流式请求并返回解析后的消息迭代器

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Yields:
            解析后的流消息
        """
        parser = StreamParser(self.parser_config)
        usage = None
        chunk_count = 0
        full_content = ""
        full_thinking = ""
        started_at = time.perf_counter()
        tool_call_state: dict[int, dict[str, Any]] = {}
        self._log_stream_started(operation="stream_iter", messages=messages, kwargs=kwargs)

        try:
            for chunk in self.provider.stream_chat(messages, **kwargs):
                chunk_count += 1
                if chunk.usage:
                    usage = chunk.usage
                self._log_stream_chunk(
                    operation="stream_iter",
                    kwargs=kwargs,
                    chunk=chunk,
                    chunk_index=chunk_count,
                    started_at=started_at,
                    tool_call_state=tool_call_state,
                )

                # 处理内容块
                if chunk.content:
                    parsed = parser.process_chunk(chunk.content)
                    for msg in parsed:
                        if msg.type == StreamMessageType.CONTENT:
                            full_content += msg.content
                        elif msg.type == StreamMessageType.THINKING:
                            full_thinking += msg.content
                        yield msg

                # 处理思考内容
                if chunk.thinking:
                    full_thinking += chunk.thinking
                    yield ParsedStreamMessage(type=StreamMessageType.THINKING, content=chunk.thinking)

                if chunk.is_complete:
                    break

            # 冲刷剩余内容
            remaining = parser.flush()
            for msg in remaining:
                if msg.type == StreamMessageType.CONTENT:
                    full_content += msg.content
                elif msg.type == StreamMessageType.THINKING:
                    full_thinking += msg.content
                yield msg
        except Exception as e:
            self._log_stream_error(
                operation="stream_iter",
                kwargs=kwargs,
                started_at=started_at,
                chunk_count=chunk_count,
                full_content=full_content,
                full_thinking=full_thinking,
                usage=usage,
                tool_call_state=tool_call_state,
                error=e,
            )
            raise

        self._log_stream_completed(
            operation="stream_iter",
            kwargs=kwargs,
            started_at=started_at,
            chunk_count=chunk_count,
            full_content=full_content,
            full_thinking=full_thinking,
            usage=usage,
            tool_call_state=tool_call_state,
        )

    def count_tokens_streaming(
        self,
        messages: list[ChatMessage],
        **kwargs,
    ) -> tuple[int, int]:
        """执行流式请求并统计实际 token 使用

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Returns:
            (输入 token 数, 输出 token 数)
        """
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        chunk_count = 0
        started_at = time.perf_counter()
        tool_call_state: dict[int, dict[str, Any]] = {}
        self._log_stream_started(
            operation="count_tokens_streaming",
            messages=messages,
            kwargs=kwargs,
        )

        try:
            for chunk in self.provider.stream_chat(messages, **kwargs):
                chunk_count += 1
                self._log_stream_chunk(
                    operation="count_tokens_streaming",
                    kwargs=kwargs,
                    chunk=chunk,
                    chunk_index=chunk_count,
                    started_at=started_at,
                    tool_call_state=tool_call_state,
                )
                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                    total_tokens = chunk.usage.total_tokens

                if chunk.is_complete:
                    break
        except Exception as e:
            self._log_stream_error(
                operation="count_tokens_streaming",
                kwargs=kwargs,
                started_at=started_at,
                chunk_count=chunk_count,
                full_content="",
                full_thinking="",
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
                tool_call_state=tool_call_state,
                error=e,
            )
            raise

        self._log_stream_completed(
            operation="count_tokens_streaming",
            kwargs=kwargs,
            started_at=started_at,
            chunk_count=chunk_count,
            full_content="",
            full_thinking="",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            tool_call_state=tool_call_state,
        )

        return prompt_tokens, completion_tokens


__all__ = ["StreamService"]
