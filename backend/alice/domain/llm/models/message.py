"""聊天消息模型

定义 LLM 通信中使用的消息结构。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class MessageRole(str, Enum):
    """消息角色枚举"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class ChatMessage:
    """聊天消息

    Attributes:
        role: 消息角色 (system/user/assistant/tool)
        content: 消息内容
        name: 可选的消息名称（用于标识不同的工具调用）
        tool_call_id: 可选的工具调用 ID
        tool_calls: 可选的工具调用列表
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None

    def to_dict(self) -> dict:
        """转换为字典格式，用于 API 调用"""
        result = {"role": self.role, "content": self.content}
        if self.name is not None:
            result["name"] = self.name
        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            result["tool_calls"] = self.tool_calls
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        """从字典创建消息"""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
        )

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        """创建系统消息"""
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        """创建用户消息"""
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str, tool_calls: list[dict] | None = None) -> "ChatMessage":
        """创建助手消息"""
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, content: str, tool_call_id: str) -> "ChatMessage":
        """创建工具消息"""
        return cls(role="tool", content=content, tool_call_id=tool_call_id)


__all__ = ["ChatMessage", "MessageRole"]
