"""
Bridge Protocol Module

定义 Rust TUI 与 Python 后端之间的通信协议。
"""

from .messages import (
    MessageType,
    StatusType,
    BaseMessage,
    StatusMessage,
    ThinkingMessage,
    ContentMessage,
    TokensMessage,
    ErrorMessage,
    InterruptMessage,
    BridgeMessage,
    FrontendRequest,
    INTERRUPT_SIGNAL,
    OutputMessage,
)
from .codec import (
    MessageDecodeError,
    MessageEncodeError,
    message_from_dict,
    message_to_dict,
    message_to_json,
    message_from_json,
    create_status_message,
    create_thinking_message,
    create_content_message,
    create_tokens_message,
    create_error_message,
)

__all__ = [
    # Messages
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
    # Codec
    "MessageDecodeError",
    "MessageEncodeError",
    "message_from_dict",
    "message_to_dict",
    "message_to_json",
    "message_from_json",
    "create_status_message",
    "create_thinking_message",
    "create_content_message",
    "create_tokens_message",
    "create_error_message",
]
