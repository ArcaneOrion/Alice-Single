"""OpenAI 兼容 LLM Provider

实现 OpenAI API 兼容的 LLM 提供商。
"""

import logging
from dataclasses import dataclass, field
from typing import Iterator, Any
from collections.abc import MutableMapping

try:
    from openai import OpenAI, Stream
    from openai.types.chat import ChatCompletion, ChatCompletionChunk
except ImportError:
    OpenAI = None
    Stream = None

from backend.alice.domain.llm.providers.base import BaseLLMProvider
from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.stream_chunk import StreamChunk

logger = logging.getLogger(__name__)


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

        super().__init__(config.model_name or config.api_key)
        self.config = config
        self._client: OpenAI | None = None
        self._header_rotator = RequestHeaderRotator(config.request_header_profiles)

    @property
    def client(self) -> OpenAI:
        """延迟初始化 OpenAI 客户端"""
        if self._client is None:
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            )
        return self._client

    def _get_extra_headers(self) -> dict:
        """获取额外的请求头"""
        headers = dict(self.config.extra_headers)

        # 如果配置了轮换 profiles，使用轮换
        if self._header_rotator.profiles:
            _, profile_headers = self._header_rotator.next_profile()
            headers.update(profile_headers)
            logger.debug(f"使用请求头 profile #{self._header_rotator._current_index - 1}")

        return headers

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

        # 构建请求参数
        params = {
            "model": self.model_name,
            "messages": api_messages,
            "stream": stream,
            "extra_headers": self._get_extra_headers(),
        }

        # 合并额外参数
        params.update(kwargs)

        logger.debug(
            f"发送 OpenAI 请求: model={self.model_name}, "
            f"messages={len(api_messages)}, stream={stream}"
        )

        try:
            response = self.client.chat.completions.create(**params)
            return response
        except Exception as e:
            logger.error(f"OpenAI 请求失败: {e}")
            raise

    def _extract_stream_chunks(self, response) -> Iterator[StreamChunk]:
        """从 OpenAI 流式响应中提取数据块

        Args:
            response: OpenAI 流式响应对象

        Yields:
            StreamChunk 实例
        """
        try:
            for chunk in response:
                yield StreamChunk.from_openai_chunk(chunk)
        except Exception as e:
            logger.error(f"流式响应解析失败: {e}")
            raise

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


__all__ = ["OpenAIProvider", "OpenAIConfig", "RequestHeaderRotator"]
