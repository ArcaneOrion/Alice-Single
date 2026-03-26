"""
Bridge Infrastructure Module

TUI (Rust) 与 Agent (Python) 之间的桥接层。
通过 stdin/stdout 传递 JSON Lines 格式消息。

模块结构：
- protocol: 消息定义和编解码器
- transport: 传输层抽象和实现
- event_handlers: 事件处理器
- server: 桥接服务器
- stream_manager: 流式数据管理器
"""

from .server import (
    BridgeServer,
    DefaultStreamManagerClass,
    create_bridge_server,
    main_with_agent,
)
from .stream_manager import StreamManager

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
    "DefaultStreamManagerClass",
    "create_bridge_server",
    "main_with_agent",
    # Stream Manager
    "StreamManager",
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
