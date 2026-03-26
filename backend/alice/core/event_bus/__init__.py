"""
事件总线包

提供发布-订阅模式的事件总线系统
"""

from .event import (
    EventType,
    Event,
    LLMStartEvent,
    LLMChunkEvent,
    LLMCompleteEvent,
    ExecStartEvent,
    ExecCompleteEvent,
    MemoryAddEvent,
    SkillLoadEvent,
)
from .event_bus import EventBus, Subscription, get_event_bus
from .handler_trait import EventHandler, EventFilter, EventHandlerFunc

__all__ = [
    # 事件类型
    "EventType",
    "Event",
    "LLMStartEvent",
    "LLMChunkEvent",
    "LLMCompleteEvent",
    "ExecStartEvent",
    "ExecCompleteEvent",
    "MemoryAddEvent",
    "SkillLoadEvent",
    # 事件总线
    "EventBus",
    "Subscription",
    "get_event_bus",
    # 处理器
    "EventHandler",
    "EventFilter",
    "EventHandlerFunc",
]
