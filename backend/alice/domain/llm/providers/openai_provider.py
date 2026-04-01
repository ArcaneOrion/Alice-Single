from __future__ import annotations

"""OpenAI 兼容 LLM Provider

实现 OpenAI API 兼容的 LLM 提供商。
"""

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator, Any
from collections.abc import MutableMapping

try:
    from openai import OpenAI, Stream
    from openai._legacy_response import LegacyAPIResponse
    from openai.types.chat import ChatCompletion, ChatCompletionChunk
except ImportError:
    OpenAI = None
    Stream = None
    LegacyAPIResponse = None

from backend.alice.domain.llm.providers.base import (
    BaseLLMProvider,
    ProviderCapability,
    build_error_payload,
    emit_observability_log,
    sanitize_for_log,
    summarize_messages,
    usage_to_log_data,
)
from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.stream_chunk import StreamChunk

logger = logging.getLogger(__name__)
_OPENAI_RETRY_STATE: ContextVar[dict[str, Any]] = ContextVar("openai_retry_state", default={})

CURL_USER_AGENT = "curl/8.0"

DEFAULT_REQUEST_HEADER_PROFILES: list[dict[str, str]] = [
    {
        "User-Agent": CURL_USER_AGENT,
        "Accept": "*/*",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": CURL_USER_AGENT,
        "Accept": "application/json",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    },
    {
        "User-Agent": CURL_USER_AGENT,
        "Accept": "*/*",
        "Connection": "close",
        "Pragma": "no-cache",
    },
]


def resolve_request_header_profiles(
    base_url: str,
    configured_profiles: list[dict] | None = None,
) -> list[dict]:
    """解析最终生效的请求头轮询配置。

    无论请求目标是什么，最终都保证带有 curl 风格 User-Agent。
    若未显式配置，则使用默认轮询 profiles；若已显式配置，
    则对每个 profile 注入/覆盖 User-Agent。
    """
    if configured_profiles:
        return [ensure_curl_user_agent(profile) for profile in configured_profiles]

    return [dict(profile) for profile in DEFAULT_REQUEST_HEADER_PROFILES]


def ensure_curl_user_agent(headers: MutableMapping[str, Any] | dict | None = None) -> dict:
    """确保请求头中始终使用 curl 风格 User-Agent。"""
    normalized_headers = dict(headers or {})
    normalized_headers["User-Agent"] = CURL_USER_AGENT
    return normalized_headers


if OpenAI is not None:

    class LoggingOpenAI(OpenAI):
        """在 OpenAI SDK 重试点补充结构化日志。"""

        def __init__(self, *args: Any, retry_callback: Any = None, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._retry_callback = retry_callback

        def _sleep_for_retry(
            self,
            *,
            retries_taken: int,
            max_retries: int,
            options: Any,
            response: Any,
        ) -> None:
            remaining_retries = max_retries - retries_taken
            timeout = self._calculate_retry_timeout(
                remaining_retries,
                options,
                response.headers if response else None,
            )

            if self._retry_callback is not None:
                status_code = getattr(response, "status_code", None)
                reason = f"http_{status_code}" if status_code is not None else "transport_error"
                request_path = str(getattr(options, "url", "") or "")
                try:
                    if hasattr(options, "url") and options.url is not None:
                        request_path = str(getattr(options.url, "path", "") or options.url)
                except Exception:
                    request_path = str(getattr(options, "url", "") or "")

                self._retry_callback(
                    attempt=retries_taken + 1,
                    max_retries=max_retries,
                    backoff_seconds=timeout,
                    reason=reason,
                    request_path=request_path,
                    status_code=status_code,
                )

            time.sleep(timeout)

else:
    LoggingOpenAI = None


@dataclass
class RequestHeaderRotator:
    """请求头轮换器

    支持配置多个请求头 profile，每次请求轮换使用。
    """

    profiles: list[dict] = field(default_factory=list)
    _current_index: int = field(default=0, init=False, repr=False)

    def next_profile(self) -> tuple[int, dict]:
        """获取下一个 profile"""
        if not self.profiles:
            return 0, {}

        index = self._current_index % len(self.profiles)
        self._current_index += 1
        return index, self.profiles[index]


@dataclass
class OpenAIConfig:
    """OpenAI Provider 配置

    Attributes:
        api_key: API 密钥
        base_url: API 基础 URL
        model_name: 模型名称
        timeout: 请求超时时间（秒）
        max_retries: 最大重试次数
        extra_headers: 额外的请求头
        request_header_profiles: 请求头轮换配置
    """

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4"
    timeout: int = 120
    max_retries: int = 2
    extra_headers: dict = field(default_factory=dict)
    request_header_profiles: list[dict] = field(default_factory=list)
    capabilities: ProviderCapability | None = None

    @classmethod
    def from_env(cls, api_key: str, base_url: str = "", model_name: str = "") -> "OpenAIConfig":
        """从环境变量创建配置"""
        return cls(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
            model_name=model_name or "gpt-4",
        )


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API 兼容的 LLM 提供商

    支持标准 OpenAI API 以及兼容的第三方服务（如 Azure、ModelScope 等）。
    """

    def __init__(self, config: OpenAIConfig):
        """初始化 OpenAI Provider

        Args:
            config: OpenAI 配置
        """
        if OpenAI is None:
            raise ImportError("openai 包未安装，请运行: pip install openai")

        super().__init__(
            config.model_name or config.api_key,
            capabilities=config.capabilities,
        )
        self.config = config
        self._client: OpenAI | None = None
        self._header_rotator = RequestHeaderRotator(config.request_header_profiles)
        self._stream_retry_state: dict[int, dict[str, Any]] = {}

    @property
    def client(self) -> OpenAI:
        """延迟初始化 OpenAI 客户端"""
        if self._client is None:
            self._client = LoggingOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
                retry_callback=self._log_retry_event,
            )
        return self._client

    def _get_extra_headers(self) -> dict:
        """获取额外的请求头"""
        headers = ensure_curl_user_agent(self.config.extra_headers)

        # 如果配置了轮换 profiles，使用轮换
        if self._header_rotator.profiles:
            _, profile_headers = self._header_rotator.next_profile()
            headers.update(ensure_curl_user_agent(profile_headers))
            logger.debug(f"使用请求头 profile #{self._header_rotator._current_index - 1}")

        return headers

    def _log_retry_event(
        self,
        *,
        attempt: int,
        max_retries: int,
        backoff_seconds: float,
        reason: str,
        request_path: str,
        status_code: int | None,
    ) -> None:
        retry_state = _OPENAI_RETRY_STATE.get({})
        request_kwargs = retry_state.get("kwargs")
        emit_observability_log(
            logger,
            level=logging.WARNING,
            event_type="api.retry",
            component="llm.provider.openai",
            phase="retry",
            payload_kind="chat.completions",
            kwargs=request_kwargs,
            data={
                "provider": "openai",
                "model": retry_state.get("model", self.model_name),
                "base_url": retry_state.get("base_url", self.config.base_url),
                "request_path": request_path,
                "stream": retry_state.get("stream"),
                "request_count": retry_state.get("request_count", self.request_count),
                "attempt": attempt,
                "max_retries": max_retries,
                "backoff_seconds": backoff_seconds,
                "reason": reason,
                "status_code": status_code,
            },
            timing={"backoff_seconds": backoff_seconds},
            message="api.retry",
        )

    @staticmethod
    def _request_path() -> str:
        return "/chat/completions"

    @staticmethod
    def _response_id(response: Any) -> str:
        return str(getattr(response, "id", "") or "")

    @staticmethod
    def _status_code(raw_response: LegacyAPIResponse | None) -> int | None:
        if raw_response is None:
            return None
        return getattr(raw_response, "status_code", None)

    @staticmethod
    def _response_request_id(raw_response: LegacyAPIResponse | None) -> str:
        if raw_response is None:
            return ""
        headers = getattr(raw_response, "headers", None) or {}
        return str(headers.get("x-request-id", "") or "")

    @staticmethod
    def _finish_reason(response: Any) -> str:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""
        return str(getattr(choices[0], "finish_reason", "") or "")

    @staticmethod
    def _output_length(response: Any, *, stream: bool) -> int:
        if stream:
            return 0

        choices = getattr(response, "choices", None) or []
        if not choices:
            return 0

        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", "") if message else ""
        thinking = ""
        if message:
            for field in (
                "reasoning_content",
                "reasoningContent",
                "reasoning",
                "thought",
                "thought_content",
                "thoughtContent",
            ):
                candidate = getattr(message, field, None)
                if candidate:
                    thinking = str(candidate)
                    break
        return len(content or "") + len(thinking or "")

    def _emit_provider_log(
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
            component="llm.provider.openai",
            phase=phase,
            payload_kind=payload_kind,
            kwargs=kwargs,
            data=data,
            error=error,
            timing=timing,
            message=message,
            exc_info=exc_info,
        )

    def _make_chat_request(
        self,
        messages: list[ChatMessage],
        stream: bool = False,
        **kwargs,
    ) -> ChatCompletion | Stream[ChatCompletionChunk]:
        """执行 OpenAI 聊天请求

        Args:
            messages: 消息列表
            stream: 是否流式返回
            **kwargs: 额外参数（如 temperature, max_tokens 等）

        Returns:
            ChatCompletion 或流式响应
        """
        # 转换消息格式
        api_messages = [msg.to_dict() for msg in messages]
        extra_headers = self._get_extra_headers()
        request_path = self._request_path()
        request_timeout = kwargs.get("timeout", self.config.timeout)

        # 构建请求参数
        params = {
            "model": self.model_name,
            "messages": api_messages,
            "stream": stream,
            "extra_headers": extra_headers,
        }

        transport_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key not in {"request_envelope"}
        }

        # 合并额外参数
        params.update(transport_kwargs)
        request_payload = sanitize_for_log(params)
        request_state = {
            "kwargs": kwargs,
            "model": self.model_name,
            "base_url": self.config.base_url,
            "stream": stream,
            "request_count": self.request_count,
        }
        retry_token = _OPENAI_RETRY_STATE.set(request_state)
        started_at = time.perf_counter()

        self._emit_provider_log(
            event_type="api.request",
            phase="request",
            payload_kind="chat.completions",
            kwargs=kwargs,
            data={
                "provider": "openai",
                "base_url": self.config.base_url,
                "request_path": request_path,
                "model": self.model_name,
                "stream": stream,
                "timeout": request_timeout,
                "max_retries": self.config.max_retries,
                "request_count": self.request_count,
                "extra_headers": sanitize_for_log(extra_headers),
                "request_params": sanitize_for_log(
                    {key: value for key, value in params.items() if key != "messages"}
                ),
                "messages": sanitize_for_log(api_messages),
                **summarize_messages(messages),
                "payload": request_payload,
            },
            message="api.request",
        )

        try:
            raw_response = self.client.chat.completions.with_raw_response.create(**params)
            response = raw_response.parse()
            latency_ms = round((time.perf_counter() - started_at) * 1000, 3)

            response_usage = usage_to_log_data(getattr(response, "usage", None))
            response_request_id = self._response_request_id(raw_response)
            effective_kwargs = kwargs
            if response_request_id and not effective_kwargs.get("request_id"):
                effective_kwargs = {**kwargs, "request_id": response_request_id}

            self._emit_provider_log(
                event_type="api.response",
                phase="response",
                payload_kind="chat.completions",
                kwargs=effective_kwargs,
                data={
                    "provider": "openai",
                    "model": getattr(response, "model", self.model_name) or self.model_name,
                    "response_id": self._response_id(response),
                    "request_path": request_path,
                    "stream": stream,
                    "status_code": self._status_code(raw_response),
                    "finish_reason": self._finish_reason(response),
                    "usage": response_usage,
                    "output_length": self._output_length(response, stream=stream),
                    "retries_taken": getattr(raw_response, "retries_taken", 0),
                    "response_request_id": response_request_id,
                },
                timing={"latency_ms": latency_ms},
                message="api.response",
            )
            if stream:
                self._stream_retry_state[id(response)] = request_state
            return response
        except Exception as e:
            latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
            status_code = getattr(e, "status_code", None)
            response_body = getattr(e, "body", None)
            error_request_id = str(getattr(e, "request_id", "") or "")
            effective_kwargs = kwargs
            if error_request_id and not effective_kwargs.get("request_id"):
                effective_kwargs = {**kwargs, "request_id": error_request_id}

            self._emit_provider_log(
                event_type="api.error",
                phase="error",
                payload_kind="chat.completions",
                kwargs=effective_kwargs,
                data={
                    "provider": "openai",
                    "base_url": self.config.base_url,
                    "request_path": request_path,
                    "model": self.model_name,
                    "stream": stream,
                    "timeout": request_timeout,
                    "max_retries": self.config.max_retries,
                    "request_count": self.request_count,
                    "status_code": status_code,
                    "response_body": sanitize_for_log(response_body),
                },
                error=build_error_payload(
                    e,
                    status_code=status_code,
                    request_id=error_request_id,
                ),
                timing={"latency_ms": latency_ms},
                level=logging.ERROR,
                message="api.error",
                exc_info=True,
            )
            raise
        finally:
            _OPENAI_RETRY_STATE.reset(retry_token)

    def _extract_stream_chunks(self, response) -> Iterator[StreamChunk]:
        """从 OpenAI 流式响应中提取数据块

        Args:
            response: OpenAI 流式响应对象

        Yields:
            StreamChunk 实例
        """
        retry_state = self._stream_retry_state.pop(id(response), {})
        retry_token = _OPENAI_RETRY_STATE.set(retry_state)
        try:
            for chunk in response:
                yield StreamChunk.from_openai_chunk(chunk)
        except Exception as e:
            self._emit_provider_log(
                event_type="api.error",
                phase="error",
                payload_kind="chat.completions.stream",
                kwargs=retry_state.get("kwargs", {}),
                data={
                    "provider": "openai",
                    "base_url": self.config.base_url,
                    "request_path": self._request_path(),
                    "model": self.model_name,
                    "stream": True,
                    "request_count": retry_state.get("request_count", self.request_count),
                },
                error=build_error_payload(e),
                level=logging.ERROR,
                message="api.error",
                exc_info=True,
            )
            raise
        finally:
            _OPENAI_RETRY_STATE.reset(retry_token)

    def count_tokens(self, messages: list[ChatMessage]) -> int:
        """计算 Token 数量

        使用粗略估算，因为 openai 包的 tiktoken 可能未安装。

        Args:
            messages: 消息列表

        Returns:
            估算的 token 数量
        """
        # 尝试使用 tiktoken 进行精确计算
        try:
            import tiktoken

            try:
                encoding = tiktoken.encoding_for_model(self.model_name)
            except KeyError:
                encoding = tiktoken.get_encoding("cl100k_base")

            tokens_per_message = 3
            tokens_per_name = 1

            num_tokens = 0
            for message in messages:
                num_tokens += tokens_per_message
                num_tokens += encoding.encode(message.content)
                if message.name:
                    num_tokens += tokens_per_name

            num_tokens += 3  # 每个回复的 primer
            return num_tokens
        except ImportError:
            # 回退到粗略估算
            return super().count_tokens(messages)


__all__ = [
    "CURL_USER_AGENT",
    "OpenAIProvider",
    "OpenAIConfig",
    "RequestHeaderRotator",
    "ensure_curl_user_agent",
    "resolve_request_header_profiles",
]
