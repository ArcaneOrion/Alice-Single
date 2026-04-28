"""
Bridge Infrastructure Module

TUI (Rust) 与 Agent (Python) 之间的桥接层。

当前活跃路径：legacy_compatibility_serializer + protocol/messages + transport
已废弃路径：server (BridgeServer) + event_handlers + stream_manager
"""

from .server import (
    BridgeServer,
    create_bridge_server,
    main_with_agent,
)

# Protocol
from .protocol import (
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
    MessageDecodeError,
    MessageEncodeError,
    create_status_message,
    create_thinking_message,
    create_content_message,
    create_tokens_message,
    create_error_message,
)

# Transport
from .transport import (
    TransportProtocol,
    TransportError,
    StdioTransport,
)

# Event Handlers
from .event_handlers import (
    MessageHandler,
    InterruptHandler,
)

__all__ = [
    # Server
    "BridgeServer",
    "create_bridge_server",
    "main_with_agent",
    # Protocol - Messages
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
    # Protocol - Codec
    "MessageDecodeError",
    "MessageEncodeError",
    "create_status_message",
    "create_thinking_message",
    "create_content_message",
    "create_tokens_message",
    "create_error_message",
    # Transport
    "TransportProtocol",
    "TransportError",
    "StdioTransport",
    # Event Handlers
    "MessageHandler",
    "InterruptHandler",
]
