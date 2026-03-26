"""流式响应块模型

定义 LLM 流式响应中的单个数据块。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class StreamChunkType(str, Enum):
    """流式块类型"""

    CONTENT = "content"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    METADATA = "metadata"


@dataclass(frozen=True)
class TokenUsageUpdate:
    """Token 使用统计更新

    Attributes:
        prompt_tokens: 输入 token 数量
        completion_tokens: 输出 token 数量
        total_tokens: 总 token 数量
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "TokenUsageUpdate":
        """从 API 响应创建"""
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
        )


@dataclass
class ToolCallDelta:
    """工具调用增量信息

    Attributes:
        index: 工具调用索引
        id: 工具调用 ID
        type: 工具类型（如 function）
        function: 函数相关信息
    """

    index: int
    id: str | None = None
    type: str | None = None
    function_name: str | None = None
    function_arguments: str | None = None

    @classmethod
    def from_openai_delta(cls, delta: dict, index: int) -> "ToolCallDelta":
        """从 OpenAI delta 创建"""
        function = delta.get("function", {})
        return cls(
            index=index,
            id=delta.get("id"),
            type=delta.get("type"),
            function_name=function.get("name"),
            function_arguments=function.get("arguments"),
        )


@dataclass(frozen=True)
class StreamChunk:
    """流式响应块

    Attributes:
        content: 正文内容片段
        thinking: 思考内容片段
        tool_calls: 工具调用增量列表
        usage: Token 使用统计（仅在流结束时提供）
        is_complete: 是否为最后一个块
        raw_delta: 原始 delta 数据（用于调试）
    """

    content: str = ""
    thinking: str = ""
    tool_calls: list[ToolCallDelta] = field(default_factory=list)
    usage: TokenUsageUpdate | None = None
    is_complete: bool = False
    raw_delta: dict | None = None

    @property
    def has_content(self) -> bool:
        """是否有正文内容"""
        return bool(self.content)

    @property
    def has_thinking(self) -> bool:
        """是否有思考内容"""
        return bool(self.thinking)

    @property
    def has_tool_calls(self) -> bool:
        """是否有工具调用"""
        return bool(self.tool_calls)

    @property
    def has_usage(self) -> bool:
        """是否有使用统计"""
        return self.usage is not None

    @classmethod
    def from_openai_chunk(cls, chunk, raw_delta: dict | None = None) -> "StreamChunk":
        """从 OpenAI 流式响应块创建

        Args:
            chunk: OpenAI API 返回的流式块
            raw_delta: 原始 delta 数据
        """
        content = ""
        thinking = ""
        tool_calls = []
        usage = None
        is_complete = False

        if not chunk.choices:
            # 无选择，可能是最终的使用统计块
            if hasattr(chunk, "usage") and chunk.usage:
                usage = TokenUsageUpdate.from_dict(
                    chunk.usage.model_dump() if hasattr(chunk.usage, "model_dump") else chunk.usage
                )
            return cls(content=content, thinking=thinking, tool_calls=tool_calls, usage=usage, is_complete=True)

        choice = chunk.choices[0]
        delta = getattr(choice, "delta", None) or choice

        # 提取结束状态
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason:
            is_complete = True

        # 提取内容
        content = getattr(delta, "content", None) or ""

        # 提取思考内容（兼容多种字段名）
        thinking_fields = [
            "reasoning_content",
            "reasoningContent",
            "reasoning",
            "thought",
            "thought_content",
            "thoughtContent",
        ]
        for field in thinking_fields:
            value = getattr(delta, field, None)
            if value:
                thinking = value
                break

        # 提取工具调用
        if hasattr(delta, "tool_calls") and delta.tool_calls:
            for tool_call in delta.tool_calls:
                tool_delta = ToolCallDelta.from_openai_delta(
                    tool_call.model_dump() if hasattr(tool_call, "model_dump") else tool_call,
                    getattr(tool_call, "index", 0),
                )
                tool_calls.append(tool_delta)

        # 提取使用统计
        if hasattr(chunk, "usage") and chunk.usage:
            usage = TokenUsageUpdate.from_dict(
                chunk.usage.model_dump() if hasattr(chunk.usage, "model_dump") else chunk.usage
            )

        return cls(
            content=content,
            thinking=thinking,
            tool_calls=tool_calls,
            usage=usage,
            is_complete=is_complete,
            raw_delta=raw_delta,
        )

    @classmethod
    def create_content(cls, content: str) -> "StreamChunk":
        """创建内容块"""
        return cls(content=content)

    @classmethod
    def create_thinking(cls, thinking: str) -> "StreamChunk":
        """创建思考块"""
        return cls(thinking=thinking)

    @classmethod
    def create_complete(cls) -> "StreamChunk":
        """创建完成块"""
        return cls(is_complete=True)

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "content": self.content,
            "thinking": self.thinking,
            "tool_calls": [
                {
                    "index": tc.index,
                    "id": tc.id,
                    "type": tc.type,
                    "function_name": tc.function_name,
                    "function_arguments": tc.function_arguments,
                }
                for tc in self.tool_calls
            ],
            "is_complete": self.is_complete,
        }
        if self.usage:
            result["usage"] = {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
            }
        return result


__all__ = [
    "StreamChunk",
    "StreamChunkType",
    "TokenUsageUpdate",
    "ToolCallDelta",
]
