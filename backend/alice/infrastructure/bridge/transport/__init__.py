"""
Transport Module

定义传输层接口和实现。
"""

from .transport_trait import (
    TransportProtocol,
    TransportError,
    MessageCallback,
    EofCallback,
)
from .stdio_transport import (
    StdioTransport,
)

__all__ = [
    # Interface
    "TransportProtocol",
    "TransportError",
    "MessageCallback",
    "EofCallback",
    # Implementation
    "StdioTransport",
]
