"""
Bridge Protocol Messages

Frontend (Rust) <-> Backend (Python) 通信协议消息定义。
通过 stdin/stdout 传递 JSON Lines 格式消息。

从 protocols/shared_types.py 迁移并扩展。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Union, Any, Optional


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


# 联合类型：所有可能的 Bridge 消息（Python -> Rust）
BridgeMessage = Union[
    StatusMessage,
    ThinkingMessage,
    ContentMessage,
    TokensMessage,
    ErrorMessage,
    InterruptMessage,
]


# 前端 -> 后端的消息（通过 stdin 发送）
@dataclass
class FrontendRequest:
    """前端发送给后端的请求"""
    input: str = ""


# 中断信号常量
INTERRUPT_SIGNAL = "__INTERRUPT__"


# 输出消息字典类型（用于 JSON 序列化）
OutputMessage = dict[str, Any]


__all__ = [
    "MessageType",
    "StatusType",
    "BaseMessage",
    "StatusMessage",
    "ThinkingMessage",
    "ContentMessage",
    "TokensMessage",
    "ErrorMessage",
    "InterruptMessage",
    "BridgeMessage",
    "FrontendRequest",
    "INTERRUPT_SIGNAL",
    "OutputMessage",
]
