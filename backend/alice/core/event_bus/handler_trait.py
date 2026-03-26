"""
事件处理器接口

定义事件处理器的协议
"""

from typing import Protocol, Callable, Any
from abc import abstractmethod
from .event import Event


class EventHandler(Protocol):
    """事件处理器接口"""

    @abstractmethod
    def handle(self, event: Event) -> None:
        """处理事件"""
        ...


class EventFilter(Protocol):
    """事件过滤器接口"""

    @abstractmethod
    def should_handle(self, event: Event) -> bool:
        """判断是否应该处理此事件"""
        ...


EventHandlerFunc = Callable[[Event], Any]
"""事件处理器函数类型"""


class TypedEventHandler(Protocol):
    """类型化事件处理器接口"""

    @abstractmethod
    def can_handle(self, event_type: str) -> bool:
        """判断是否能处理指定类型的事件"""
        ...
