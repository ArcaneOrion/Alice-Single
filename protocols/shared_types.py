"""
共享协议类型定义

Frontend (Rust) ↔ Backend (Python) 通信协议
通过 stdin/stdout 传递 JSON Lines 格式消息
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Union


class MessageType(str, Enum):
    """消息类型枚举"""
    STATUS = "status"
    THINKING = "thinking"
    CONTENT = "content"
    TOKENS = "tokens"
    ERROR = "error"
    INTERRUPT = "interrupt"


class StatusType(str, Enum):
    """状态类型枚举"""
    READY = "ready"
    THINKING = "thinking"
    EXECUTING_TOOL = "executing_tool"
    DONE = "done"


@dataclass
class BaseMessage:
    """消息基类"""
    type: MessageType


@dataclass
class StatusMessage(BaseMessage):
    """状态消息：用于通知前端当前运行状态"""
    type: Literal[MessageType.STATUS] = MessageType.STATUS
    content: StatusType = StatusType.READY


@dataclass
class ThinkingMessage(BaseMessage):
    """思考消息：LLM 思考过程内容（显示在侧边栏）"""
    type: Literal[MessageType.THINKING] = MessageType.THINKING
    content: str = ""


@dataclass
class ContentMessage(BaseMessage):
    """正文消息：LLM 主要回复内容（显示在主聊天区）"""
    type: Literal[MessageType.CONTENT] = MessageType.CONTENT
    content: str = ""


@dataclass
class TokensMessage(BaseMessage):
    """Token 统计消息"""
    type: Literal[MessageType.TOKENS] = MessageType.TOKENS
    total: int = 0
    prompt: int = 0
    completion: int = 0


@dataclass
class ErrorMessage(BaseMessage):
    """错误消息"""
    type: Literal[MessageType.ERROR] = MessageType.ERROR
    content: str = ""
    code: str = ""


@dataclass
class InterruptMessage(BaseMessage):
    """中断消息：用于从 Rust 发送中断信号到 Python"""
    type: Literal[MessageType.INTERRUPT] = MessageType.INTERRUPT


# 联合类型：所有可能的 Bridge 消息
BridgeMessage = Union[
    StatusMessage,
    ThinkingMessage,
    ContentMessage,
    TokensMessage,
    ErrorMessage,
    InterruptMessage,
]


# 前端 → 后端的消息（通过 stdin 发送）
@dataclass
class FrontendRequest:
    """前端发送给后端的请求"""
    input: str = ""


# 中断信号常量
INTERRUPT_SIGNAL = "__INTERRUPT__"


def message_from_dict(data: dict) -> BridgeMessage:
    """从字典解析消息"""
    msg_type = data.get("type")

    if msg_type == MessageType.STATUS:
        return StatusMessage(type=MessageType.STATUS, content=StatusType(data.get("content", "ready")))
    elif msg_type == MessageType.THINKING:
        return ThinkingMessage(type=MessageType.THINKING, content=data.get("content", ""))
    elif msg_type == MessageType.CONTENT:
        return ContentMessage(type=MessageType.CONTENT, content=data.get("content", ""))
    elif msg_type == MessageType.TOKENS:
        return TokensMessage(
            type=MessageType.TOKENS,
            total=data.get("total", 0),
            prompt=data.get("prompt", 0),
            completion=data.get("completion", 0)
        )
    elif msg_type == MessageType.ERROR:
        return ErrorMessage(
            type=MessageType.ERROR,
            content=data.get("content", ""),
            code=data.get("code", "")
        )
    elif msg_type == MessageType.INTERRUPT:
        return InterruptMessage(type=MessageType.INTERRUPT)
    else:
        raise ValueError(f"Unknown message type: {msg_type}")


def message_to_dict(message: BridgeMessage) -> dict:
    """将消息转换为字典（用于 JSON 序列化）"""
    if isinstance(message, StatusMessage):
        return {"type": "status", "content": message.content.value}
    elif isinstance(message, ThinkingMessage):
        return {"type": "thinking", "content": message.content}
    elif isinstance(message, ContentMessage):
        return {"type": "content", "content": message.content}
    elif isinstance(message, TokensMessage):
        return {
            "type": "tokens",
            "total": message.total,
            "prompt": message.prompt,
            "completion": message.completion
        }
    elif isinstance(message, ErrorMessage):
        return {"type": "error", "content": message.content, "code": message.code}
    elif isinstance(message, InterruptMessage):
        return {"type": "interrupt"}
    else:
        raise ValueError(f"Unknown message type: {type(message)}")
