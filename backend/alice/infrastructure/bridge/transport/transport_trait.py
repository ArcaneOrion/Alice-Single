"""
Transport Protocol Interface

定义传输层抽象接口，支持不同的通信方式（stdin/stdout、socket等）。
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Callable

from ..protocol.messages import FrontendRequest, OutputMessage

logger = logging.getLogger(__name__)


# 消息回调类型
MessageCallback = Callable[[str], None]
# EOF 回调类型
EofCallback = Callable[[], None]


class TransportError(Exception):
    """传输层异常"""
    pass


class TransportProtocol(ABC):
    """
    传输层协议抽象接口。

    定义前后端之间的双向通信接口。
    """

    @abstractmethod
    def start(self) -> None:
        """
        启动传输层。

        开始监听输入并准备发送输出。
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
        停止传输层。

        清理资源并关闭连接。
        """
        pass

    @abstractmethod
    def send_message(self, message: OutputMessage) -> None:
        """
        发送消息到前端。

        Args:
            message: 要发送的消息字典
        """
        pass

    @abstractmethod
    def send_raw(self, data: str) -> None:
        """
        发送原始字符串到前端。

        Args:
            data: 要发送的字符串
        """
        pass

    @abstractmethod
    def set_message_callback(self, callback: Optional[MessageCallback]) -> None:
        """
        设置接收到消息时的回调函数。

        Args:
            callback: 消息回调函数，接收输入字符串
        """
        pass

    @abstractmethod
    def set_eof_callback(self, callback: Optional[EofCallback]) -> None:
        """
        设置接收到 EOF 时的回调函数。

        Args:
            callback: EOF 回调函数
        """
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """
        检查传输层是否正在运行。

        Returns:
            bool: 是否正在运行
        """
        pass


__all__ = [
    "TransportProtocol",
    "TransportError",
    "MessageCallback",
    "EofCallback",
]
