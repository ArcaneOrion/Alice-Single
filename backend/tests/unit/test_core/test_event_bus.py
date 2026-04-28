"""
事件总线单元测试

测试 EventBus 的发布-订阅功能、通配符订阅、过滤器等
"""

from unittest.mock import Mock

import pytest

from backend.alice.core.event_bus import (
    EventBus,
    EventType,
    Event,
    Subscription,
)
from backend.alice.core.event_bus.event import LLMStartEvent, ExecCompleteEvent


# ============================================================================
# 基础功能测试
# ============================================================================

class TestEventBusBasics:
    """事件总线基础功能测试"""

    def test_create_event_bus(self):
        """测试创建事件总线"""
        bus = EventBus()

        assert bus is not None
        assert len(bus._subscriptions) == 0
        assert len(bus._wildcard_subscriptions) == 0

    def test_subscribe_and_publish(self, mock_event_handler):
        """测试订阅和发布"""
        bus = EventBus()
        bus.subscribe(EventType.LLM_START, mock_event_handler)

        event = Event(type=EventType.LLM_START, data={"test": "data"})
        bus.publish(event)

        assert mock_event_handler.call_count == 1

    def test_subscribe_returns_unsubscribe_function(self, mock_event_handler):
        """测试订阅返回取消订阅函数"""
        bus = EventBus()
        unsubscribe = bus.subscribe(EventType.LLM_START, mock_event_handler)

        assert callable(unsubscribe)

        # 发布事件，应该被处理
        bus.publish(Event(type=EventType.LLM_START))
        assert mock_event_handler.call_count == 1

        # 取消订阅
        unsubscribe()

        # 发布事件，不应该被处理
        bus.publish(Event(type=EventType.LLM_START))
        assert mock_event_handler.call_count == 1  # 仍然是 1

    def test_multiple_subscribers(self):
        """测试多个订阅者"""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()

        bus.subscribe(EventType.LLM_START, handler1)
        bus.subscribe(EventType.LLM_START, handler2)

        bus.publish(Event(type=EventType.LLM_START))

        assert handler1.call_count == 1
        assert handler2.call_count == 1

    def test_different_event_types(self):
        """测试不同事件类型"""
        bus = EventBus()
        llm_handler = Mock()
        exec_handler = Mock()

        bus.subscribe(EventType.LLM_START, llm_handler)
        bus.subscribe(EventType.EXEC_START, exec_handler)

        bus.publish(Event(type=EventType.LLM_START))
        bus.publish(Event(type=EventType.EXEC_START))

        assert llm_handler.call_count == 1
        assert exec_handler.call_count == 1

    def test_event_data_passed_to_handler(self):
        """测试事件数据传递给处理器"""
        bus = EventBus()
        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe(EventType.LLM_START, handler)

        event = Event(
            type=EventType.LLM_START,
            data={"model": "gpt-4", "messages": 3}
        )
        bus.publish(event)

        assert len(received_events) == 1
        assert received_events[0].type == EventType.LLM_START
        assert received_events[0].data["model"] == "gpt-4"


# ============================================================================
# 通配符订阅测试
# ============================================================================

class TestWildcardSubscription:
    """通配符订阅测试"""

    def test_wildcard_receives_all_events(self):
        """测试通配符接收所有事件"""
        bus = EventBus()
        handler = Mock()

        bus.subscribe_wildcard(handler)

        bus.publish(Event(type=EventType.LLM_START))
        bus.publish(Event(type=EventType.EXEC_START))
        bus.publish(Event(type=EventType.MEMORY_ADD))

        assert handler.call_count == 3

    def test_wildcard_unsubscribe(self):
        """测试取消通配符订阅"""
        bus = EventBus()
        handler = Mock()

        unsubscribe = bus.subscribe_wildcard(handler)
        bus.publish(Event(type=EventType.LLM_START))
        assert handler.call_count == 1

        unsubscribe()
        bus.publish(Event(type=EventType.EXEC_START))
        assert handler.call_count == 1  # 仍然是 1

    def test_wildcard_and_specific_subscription(self):
        """测试通配符和特定订阅同时工作"""
        bus = EventBus()
        wildcard_handler = Mock()
        specific_handler = Mock()

        bus.subscribe_wildcard(wildcard_handler)
        bus.subscribe(EventType.LLM_START, specific_handler)

        bus.publish(Event(type=EventType.LLM_START))
        bus.publish(Event(type=EventType.EXEC_START))

        assert wildcard_handler.call_count == 2  # 接收所有事件
        assert specific_handler.call_count == 1  # 只接收 LLM_START


# ============================================================================
# 过滤器测试
# ============================================================================

class TestEventFilter:
    """事件过滤器测试"""

    def test_filter_with_function(self):
        """测试函数过滤器"""
        bus = EventBus()
        handler = Mock()

        def filter_func(event):
            return event.data.get("priority") == "high"

        bus.subscribe(
            EventType.LLM_START,
            handler,
            event_filter=lambda e: e.data.get("priority") == "high"
        )

        # 高优先级事件
        bus.publish(Event(type=EventType.LLM_START, data={"priority": "high"}))
        assert handler.call_count == 1

        # 低优先级事件
        bus.publish(Event(type=EventType.LLM_START, data={"priority": "low"}))
        assert handler.call_count == 1  # 仍然是 1

    def test_wildcard_with_filter(self):
        """测试通配符订阅带过滤器"""
        bus = EventBus()
        handler = Mock()

        bus.subscribe_wildcard(
            handler,
            event_filter=lambda e: e.type == EventType.LLM_START
        )

        bus.publish(Event(type=EventType.LLM_START))
        bus.publish(Event(type=EventType.EXEC_START))

        assert handler.call_count == 1


# ============================================================================
# Once 订阅测试
# ============================================================================

class TestOnceSubscription:
    """一次性订阅测试"""

    def test_once_subscription_fires_only_once(self):
        """测试一次性订阅只触发一次"""
        bus = EventBus()
        handler = Mock()

        bus.subscribe(EventType.LLM_START, handler, once=True)

        bus.publish(Event(type=EventType.LLM_START))
        assert handler.call_count == 1

        bus.publish(Event(type=EventType.LLM_START))
        assert handler.call_count == 1  # 仍然是 1

    def test_once_subscription_removed_after_fire(self):
        """测试一次性订阅触发后移除"""
        bus = EventBus()
        handler = Mock()

        bus.subscribe(EventType.LLM_START, handler, once=True)
        bus.publish(Event(type=EventType.LLM_START))

        assert len(bus._subscriptions.get(EventType.LLM_START, [])) == 0


# ============================================================================
# 特定事件类型测试
# ============================================================================

class TestSpecificEventTypes:
    """特定事件类型测试"""

    def test_llm_start_event(self):
        """测试 LLM 开始事件"""
        bus = EventBus()
        handler = Mock()

        bus.subscribe(EventType.LLM_START, handler)

        event = LLMStartEvent(model="gpt-4", messages_count=5)
        bus.publish(event)

        assert handler.call_count == 1
        called_event = handler.call_args[0][0]
        assert isinstance(called_event, LLMStartEvent)
        assert called_event.model == "gpt-4"
        assert called_event.messages_count == 5

    def test_exec_complete_event(self):
        """测试执行完成事件"""
        bus = EventBus()
        handler = Mock()

        bus.subscribe(EventType.EXEC_COMPLETE, handler)

        event = ExecCompleteEvent(
            command="echo test",
            success=True,
            output="test",
            duration_ms=50
        )
        bus.publish(event)

        assert handler.call_count == 1
        called_event = handler.call_args[0][0]
        assert called_event.success is True
        assert called_event.output == "test"


# ============================================================================
# 错误处理测试
# ============================================================================

class TestErrorHandling:
    """错误处理测试"""

    def test_handler_exception_doesnt_interrupt_other_handlers(self):
        """测试处理器异常不中断其他处理器"""
        bus = EventBus()

        def failing_handler(event):
            raise RuntimeError("Handler failed")

        working_handler = Mock()

        bus.subscribe(EventType.LLM_START, failing_handler)
        bus.subscribe(EventType.LLM_START, working_handler)

        # 应该不抛出异常
        bus.publish(Event(type=EventType.LLM_START))

        # 工作的处理器应该被调用
        assert working_handler.call_count == 1


# ============================================================================
# 订阅计数测试
# ============================================================================

class TestSubscriberCount:
    """订阅计数测试"""

    def test_get_subscriber_count_for_type(self):
        """测试获取特定类型的订阅者数量"""
        bus = EventBus()
        bus.subscribe(EventType.LLM_START, Mock())
        bus.subscribe(EventType.LLM_START, Mock())
        bus.subscribe(EventType.EXEC_START, Mock())

        assert bus.get_subscriber_count(EventType.LLM_START) == 2
        assert bus.get_subscriber_count(EventType.EXEC_START) == 1

    def test_get_wildcard_subscriber_count(self):
        """测试获取通配符订阅者数量"""
        bus = EventBus()
        bus.subscribe_wildcard(Mock())
        bus.subscribe_wildcard(Mock())

        assert bus.get_subscriber_count(None) == 2

    def test_clear_removes_all_subscriptions(self):
        """测试清除所有订阅"""
        bus = EventBus()
        bus.subscribe(EventType.LLM_START, Mock())
        bus.subscribe_wildcard(Mock())

        bus.clear()

        assert bus.get_subscriber_count(EventType.LLM_START) == 0
        assert bus.get_subscriber_count(None) == 0


# ============================================================================
# 线程安全测试
# ============================================================================

class TestThreadSafety:
    """线程安全测试"""

    def test_concurrent_publish(self):
        """测试并发发布"""
        import threading

        bus = EventBus()
        handler = Mock()
        bus.subscribe(EventType.LLM_START, handler)

        def publish_events():
            for _ in range(100):
                bus.publish(Event(type=EventType.LLM_START))

        threads = [threading.Thread(target=publish_events) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert handler.call_count == 500


__all__ = []
