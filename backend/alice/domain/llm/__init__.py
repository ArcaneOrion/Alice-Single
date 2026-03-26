"""LLM Domain 模块

提供 LLM 调用的核心功能：
- 消息和响应数据模型
- OpenAI 兼容的 Provider 实现
- 流式响应解析器
- 聊天服务
"""

from backend.alice.domain.llm.models.message import ChatMessage, MessageRole
from backend.alice.domain.llm.models.response import ChatResponse, TokenUsage
from backend.alice.domain.llm.models.stream_chunk import StreamChunk

from backend.alice.domain.llm.providers.base import BaseLLMProvider
from backend.alice.domain.llm.providers.openai_provider import OpenAIProvider

from backend.alice.domain.llm.parsers.stream_parser import StreamParser, StreamParserConfig

from backend.alice.domain.llm.services.chat_service import ChatService
from backend.alice.domain.llm.services.stream_service import StreamService

__all__ = [
    # Models
    "ChatMessage",
    "MessageRole",
    "ChatResponse",
    "TokenUsage",
    "StreamChunk",
    # Providers
    "BaseLLMProvider",
    "OpenAIProvider",
    # Parsers
    "StreamParser",
    "StreamParserConfig",
    # Services
    "ChatService",
    "StreamService",
]
