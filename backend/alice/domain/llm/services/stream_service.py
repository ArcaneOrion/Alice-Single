"""流处理服务

提供 LLM 流式响应的高级处理功能。
"""

import logging
import traceback
from typing import Any, Callable, Iterator

from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.response import ChatResponse, TokenUsage
from backend.alice.domain.llm.providers.base import BaseLLMProvider
from backend.alice.domain.llm.parsers.stream_parser import (
    StreamParser,
    StreamParserConfig,
    ParsedStreamMessage,
    StreamMessageType,
)

logger = logging.getLogger(__name__)


def _extract_stream_log_context(kwargs: dict[str, Any]) -> dict[str, Any]:
    """提取流式调用日志上下文（兼容缺省字段）"""
    metadata = kwargs.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    session_id = metadata.get("session_id") or kwargs.get("session_id") or ""
    request_id = (
        metadata.get("request_id")
        or metadata.get("trace_id")
        or kwargs.get("request_id")
        or kwargs.get("trace_id")
        or ""
    )
    task_id = metadata.get("task_id") or kwargs.get("task_id") or request_id or session_id or ""

    return {
        "task_id": task_id,
        "request_id": request_id,
        "session_id": session_id,
        "component": "stream_service",
    }


def _usage_to_data(usage: Any) -> dict[str, int]:
    """提取 token 信息到日志数据字段"""
    if usage is None:
        return {}

    return {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


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
        log_context = _extract_stream_log_context(kwargs)

        logger.info(
            "LLM streaming call started",
            extra={
                "event_type": "llm_call",
                "log_category": "llm.stream",
                "context": log_context,
                "data": {
                    "operation": "stream_with_parser",
                    "model": self.provider.model_name,
                    "message_count": len(messages),
                },
            },
        )

        try:
            for chunk in self.provider.stream_chat(messages, **kwargs):
                chunk_count += 1
                if chunk.usage:
                    usage = chunk.usage

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
            logger.error(
                "LLM streaming call failed",
                exc_info=True,
                extra={
                    "event_type": "llm_response",
                    "log_category": "llm.stream",
                    "context": log_context,
                    "data": {
                        "operation": "stream_with_parser",
                        "model": self.provider.model_name,
                        "chunk_count": chunk_count,
                        **_usage_to_data(usage),
                    },
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    },
                },
            )
            raise

        logger.info(
            "LLM streaming call completed",
            extra={
                "event_type": "llm_response",
                "log_category": "llm.stream",
                "context": log_context,
                "data": {
                    "operation": "stream_with_parser",
                    "model": self.provider.model_name,
                    "chunk_count": chunk_count,
                    "content_length": len(full_content),
                    "thinking_length": len(full_thinking),
                    **_usage_to_data(usage),
                },
            },
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
        log_context = _extract_stream_log_context(kwargs)

        logger.info(
            "LLM streaming call started",
            extra={
                "event_type": "llm_call",
                "log_category": "llm.stream",
                "context": log_context,
                "data": {
                    "operation": "stream_to_ui",
                    "model": self.provider.model_name,
                    "message_count": len(messages),
                },
            },
        )

        # 发送开始状态
        emit_callback({"type": "status", "content": "thinking"})

        try:
            for chunk in self.provider.stream_chat(messages, **kwargs):
                chunk_count += 1
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
            logger.error(
                "LLM streaming call failed",
                exc_info=True,
                extra={
                    "event_type": "llm_response",
                    "log_category": "llm.stream",
                    "context": log_context,
                    "data": {
                        "operation": "stream_to_ui",
                        "model": self.provider.model_name,
                        "chunk_count": chunk_count,
                        **_usage_to_data(usage),
                    },
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    },
                },
            )
            raise

        # 发送完成状态
        emit_callback({"type": "status", "content": "done"})

        logger.info(
            "LLM streaming call completed",
            extra={
                "event_type": "llm_response",
                "log_category": "llm.stream",
                "context": log_context,
                "data": {
                    "operation": "stream_to_ui",
                    "model": self.provider.model_name,
                    "chunk_count": chunk_count,
                    "content_length": len(full_content),
                    "thinking_length": len(full_thinking),
                    **_usage_to_data(usage),
                },
            },
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
        log_context = _extract_stream_log_context(kwargs)

        logger.info(
            "LLM streaming call started",
            extra={
                "event_type": "llm_call",
                "log_category": "llm.stream",
                "context": log_context,
                "data": {
                    "operation": "stream_collect",
                    "model": self.provider.model_name,
                    "message_count": len(messages),
                },
            },
        )

        try:
            for chunk in self.provider.stream_chat(messages, **kwargs):
                chunk_count += 1
                full_content += chunk.content
                full_thinking += chunk.thinking

                if chunk.tool_calls:
                    for tc in chunk.tool_calls:
                        # 简单的增量收集逻辑
                        # 实际使用时可能需要更复杂的聚合
                        pass

                if chunk.usage:
                    usage = TokenUsage(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                        total_tokens=chunk.usage.total_tokens,
                    )

                if chunk.is_complete:
                    break
        except Exception as e:
            logger.error(
                "LLM streaming call failed",
                exc_info=True,
                extra={
                    "event_type": "llm_response",
                    "log_category": "llm.stream",
                    "context": log_context,
                    "data": {
                        "operation": "stream_collect",
                        "model": self.provider.model_name,
                        "chunk_count": chunk_count,
                        **_usage_to_data(usage),
                    },
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    },
                },
            )
            raise

        logger.info(
            "LLM streaming call completed",
            extra={
                "event_type": "llm_response",
                "log_category": "llm.stream",
                "context": log_context,
                "data": {
                    "operation": "stream_collect",
                    "model": self.provider.model_name,
                    "chunk_count": chunk_count,
                    "content_length": len(full_content),
                    "thinking_length": len(full_thinking),
                    **_usage_to_data(usage),
                },
            },
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
        log_context = _extract_stream_log_context(kwargs)

        logger.info(
            "LLM streaming call started",
            extra={
                "event_type": "llm_call",
                "log_category": "llm.stream",
                "context": log_context,
                "data": {
                    "operation": "stream_iter",
                    "model": self.provider.model_name,
                    "message_count": len(messages),
                },
            },
        )

        try:
            for chunk in self.provider.stream_chat(messages, **kwargs):
                chunk_count += 1
                if chunk.usage:
                    usage = chunk.usage

                # 处理内容块
                if chunk.content:
                    parsed = parser.process_chunk(chunk.content)
                    yield from parsed

                # 处理思考内容
                if chunk.thinking:
                    yield ParsedStreamMessage(type=StreamMessageType.THINKING, content=chunk.thinking)

                if chunk.is_complete:
                    break

            # 冲刷剩余内容
            remaining = parser.flush()
            yield from remaining
        except Exception as e:
            logger.error(
                "LLM streaming call failed",
                exc_info=True,
                extra={
                    "event_type": "llm_response",
                    "log_category": "llm.stream",
                    "context": log_context,
                    "data": {
                        "operation": "stream_iter",
                        "model": self.provider.model_name,
                        "chunk_count": chunk_count,
                        **_usage_to_data(usage),
                    },
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    },
                },
            )
            raise

        logger.info(
            "LLM streaming call completed",
            extra={
                "event_type": "llm_response",
                "log_category": "llm.stream",
                "context": log_context,
                "data": {
                    "operation": "stream_iter",
                    "model": self.provider.model_name,
                    "chunk_count": chunk_count,
                    **_usage_to_data(usage),
                },
            },
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
        log_context = _extract_stream_log_context(kwargs)

        logger.info(
            "LLM streaming call started",
            extra={
                "event_type": "llm_call",
                "log_category": "llm.stream",
                "context": log_context,
                "data": {
                    "operation": "count_tokens_streaming",
                    "model": self.provider.model_name,
                    "message_count": len(messages),
                },
            },
        )

        try:
            for chunk in self.provider.stream_chat(messages, **kwargs):
                chunk_count += 1
                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                    total_tokens = chunk.usage.total_tokens

                if chunk.is_complete:
                    break
        except Exception as e:
            logger.error(
                "LLM streaming call failed",
                exc_info=True,
                extra={
                    "event_type": "llm_response",
                    "log_category": "llm.stream",
                    "context": log_context,
                    "data": {
                        "operation": "count_tokens_streaming",
                        "model": self.provider.model_name,
                        "chunk_count": chunk_count,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    },
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    },
                },
            )
            raise

        logger.info(
            "LLM streaming call completed",
            extra={
                "event_type": "llm_response",
                "log_category": "llm.stream",
                "context": log_context,
                "data": {
                    "operation": "count_tokens_streaming",
                    "model": self.provider.model_name,
                    "chunk_count": chunk_count,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
            },
        )

        return prompt_tokens, completion_tokens


__all__ = ["StreamService"]
