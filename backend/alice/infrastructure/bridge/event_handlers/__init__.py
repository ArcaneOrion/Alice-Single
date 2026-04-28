"""
Event Handlers Module (DEPRECATED)

.. deprecated::
   旧 bridge 事件处理器，已由 cli/main.py 主链路替代。
"""

import warnings

from .message_handler import MessageHandler
from .interrupt_handler import InterruptHandler

warnings.warn(
    "bridge.event_handlers 模块已废弃，当前默认入口是 cli/main.py",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "MessageHandler",
    "InterruptHandler",
]
