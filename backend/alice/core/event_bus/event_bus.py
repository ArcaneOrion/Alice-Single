"""
事件总线实现

提供发布-订阅模式的事件总线
"""

import asyncio
import threading
from typing import Dict, List, Callable, Any, Optional
from collections import defaultdict
from queue import Queue, Empty
from dataclasses import dataclass

from .event import Event, EventType
from .handler_trait import EventHandler, EventHandlerFunc, EventFilter


def _apply_filter(
    filter_obj: EventFilter | Callable[[Event], bool], event: Event
) -> bool:
    """应用事件过滤器，兼容 EventFilter 协议和普通 callable。"""
    if hasattr(filter_obj, "should_handle"):
        return bool(filter_obj.should_handle(event))
    return bool(filter_obj(event))


@dataclass
class Subscription:
    """订阅信息"""
    handler: EventHandlerFunc
    filter: Optional[EventFilter] = None
    once: bool = False  # 是否只触发一次
    is_async: bool = False  # 是否异步处理


class EventBus:
    """
    事件总线

    使用示例:
        bus = EventBus()

        # 订阅事件
        bus.subscribe(EventType.LLM_START, lambda e: print(f"LLM started: {e.data}"))

        # 发布事件
        bus.publish(Event(type=EventType.LLM_START, data={"model": "gpt-4"}))

        # 异步发布
        await bus.apublish(Event(type=EventType.LLM_START))
    """

    def __init__(self, enable_async: bool = True):
        self._subscriptions: Dict[EventType, List[Subscription]] = defaultdict(list)
        self._wildcard_subscriptions: List[Subscription] = []
        self._event_queue: Queue = Queue()
        self._running: bool = False
        self._worker_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._enable_async = enable_async

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandlerFunc,
        event_filter: Optional[EventFilter] = None,
        once: bool = False
    ) -> Callable[[], None]:
        """
        订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理函数
            event_filter: 事件过滤器（可选）
            once: 是否只触发一次

        Returns:
            取消订阅的函数
        """
        with self._lock:
            subscription = Subscription(
                handler=handler,
                filter=event_filter,
                once=once
            )
            self._subscriptions[event_type].append(subscription)

        # 返回取消订阅的函数
        def unsubscribe():
            with self._lock:
                if event_type in self._subscriptions:
                    self._subscriptions[event_type] = [
                        s for s in self._subscriptions[event_type]
                        if s.handler != handler
                    ]

        return unsubscribe

    def subscribe_wildcard(
        self,
        handler: EventHandlerFunc,
        event_filter: Optional[EventFilter] = None
    ) -> Callable[[], None]:
        """
        订阅所有事件（通配符订阅）

        Args:
            handler: 事件处理函数
            event_filter: 事件过滤器（可选）

        Returns:
            取消订阅的函数
        """
        with self._lock:
            subscription = Subscription(
                handler=handler,
                filter=event_filter
            )
            self._wildcard_subscriptions.append(subscription)

        def unsubscribe():
            with self._lock:
                self._wildcard_subscriptions = [
                    s for s in self._wildcard_subscriptions
                    if s.handler != handler
                ]

        return unsubscribe

    def publish(self, event: Event) -> None:
        """
        同步发布事件

        Args:
            event: 事件对象
        """
        # 处理通配符订阅
        with self._lock:
            subscriptions = list(self._wildcard_subscriptions)

        for subscription in subscriptions:
            self._execute_handler(subscription, event)

        # 处理特定类型订阅
        with self._lock:
            subscriptions = list(self._subscriptions.get(event.type, []))

        # 收集需要移除的 once 订阅
        to_remove = []

        for subscription in subscriptions:
            self._execute_handler(subscription, event)
            if subscription.once:
                to_remove.append(subscription)

        # 移除 once 订阅
        if to_remove:
            with self._lock:
                for sub in to_remove:
                    if sub in self._subscriptions[event.type]:
                        self._subscriptions[event.type].remove(sub)

    async def apublish(self, event: Event) -> None:
        """
        异步发布事件

        Args:
            event: 事件对象
        """
        # 处理通配符订阅
        with self._lock:
            subscriptions = list(self._wildcard_subscriptions)

        for subscription in subscriptions:
            await self._aexecute_handler(subscription, event)

        # 处理特定类型订阅
        with self._lock:
            subscriptions = list(self._subscriptions.get(event.type, []))

        to_remove = []

        for subscription in subscriptions:
            await self._aexecute_handler(subscription, event)
            if subscription.once:
                to_remove.append(subscription)

        if to_remove:
            with self._lock:
                for sub in to_remove:
                    if sub in self._subscriptions[event.type]:
                        self._subscriptions[event.type].remove(sub)

    def _execute_handler(self, subscription: Subscription, event: Event) -> None:
        """执行事件处理器"""
        try:
            if subscription.filter is not None:
                if not _apply_filter(subscription.filter, event):
                    return

            subscription.handler(event)
        except Exception as e:
            self._handle_error(e, event, subscription.handler)

    async def _aexecute_handler(self, subscription: Subscription, event: Event) -> None:
        """异步执行事件处理器"""
        try:
            if subscription.filter is not None:
                if not _apply_filter(subscription.filter, event):
                    return

            handler = subscription.handler
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            self._handle_error(e, event, subscription.handler)

    def _handle_error(self, error: Exception, event: Event, handler: Any) -> None:
        """处理事件处理器错误"""
        import logging
        logger = logging.getLogger("EventBus")
        logger.error(
            f"Error in event handler for {event.type}: {error}",
            exc_info=error
        )

    def start(self) -> None:
        """启动事件总线工作线程"""
        if self._running:
            return

        self._running = True

        def worker():
            while self._running:
                try:
                    event = self._event_queue.get(timeout=0.1)
                    self.publish(event)
                except Empty:
                    continue
                except Exception as e:
                    self._handle_error(e, None, None)

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def stop(self) -> None:
        """停止事件总线工作线程"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)
            self._worker_thread = None

    def clear(self) -> None:
        """清空所有订阅"""
        with self._lock:
            self._subscriptions.clear()
            self._wildcard_subscriptions.clear()

    def get_subscriber_count(self, event_type: Optional[EventType] = None) -> int:
        """
        获取订阅者数量

        Args:
            event_type: 事件类型，为 None 时返回通配符订阅数

        Returns:
            订阅者数量
        """
        with self._lock:
            if event_type is None:
                return len(self._wildcard_subscriptions)
            return len(self._subscriptions.get(event_type, []))


# 全局事件总线实例
_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus
