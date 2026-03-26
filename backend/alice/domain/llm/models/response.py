"""聊天响应模型

定义 LLM 响应的数据结构。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TokenUsage:
    """Token 使用统计

    Attributes:
        prompt_tokens: 输入 token 数量
        completion_tokens: 输出 token 数量
        total_tokens: 总 token 数量
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @classmethod
    def from_dict(cls, data: dict) -> "TokenUsage":
        """从 API 响应创建"""
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ChatResponse:
    """完整聊天响应

    Attributes:
        content: 响应正文内容
        thinking: 思考内容（推理过程）
        tool_calls: 工具调用列表
        usage: Token 使用统计
        model: 使用的模型名称
        finish_reason: 结束原因
    """

    content: str
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    usage: TokenUsage | None = None
    model: str = ""
    finish_reason: str = ""

    @classmethod
    def from_openai_response(cls, response, model: str = "") -> "ChatResponse":
        """从 OpenAI 响应对象创建

        Args:
            response: OpenAI API 返回的响应对象
            model: 模型名称
        """
        # 提取消息内容
        message = response.choices[0].message if response.choices else None
        content = ""
        thinking = ""
        tool_calls = []

        if message:
            content = getattr(message, "content", "") or ""
            tool_calls = getattr(message, "tool_calls", None) or []

            # 尝试提取思考内容
            thinking_fields = [
                "reasoning_content",
                "reasoningContent",
                "reasoning",
                "thought",
                "thought_content",
                "thoughtContent",
            ]
            for field in thinking_fields:
                value = getattr(message, field, None)
                if value:
                    thinking = value
                    break

        # 提取使用统计
        usage = None
        if hasattr(response, "usage") and response.usage:
            usage = TokenUsage.from_dict(response.usage.model_dump() if hasattr(response.usage, "model_dump") else response.usage)

        # 提取结束原因
        finish_reason = ""
        if response.choices:
            choice = response.choices[0]
            finish_reason = getattr(choice, "finish_reason", "") or ""

        return cls(
            content=content,
            thinking=thinking,
            tool_calls=tool_calls,
            usage=usage,
            model=model or getattr(response, "model", ""),
            finish_reason=finish_reason,
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "content": self.content,
            "thinking": self.thinking,
            "tool_calls": self.tool_calls,
            "model": self.model,
            "finish_reason": self.finish_reason,
        }
        if self.usage:
            result["usage"] = self.usage.to_dict()
        return result


__all__ = ["ChatResponse", "TokenUsage"]
