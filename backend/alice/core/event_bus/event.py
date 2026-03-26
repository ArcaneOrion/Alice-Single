"""
事件类型定义

定义系统中所有事件的类型
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime


class EventType(str, Enum):
    """事件类型枚举"""
    # LLM 相关
    LLM_START = "llm.start"
    LLM_CHUNK = "llm.chunk"
    LLM_COMPLETE = "llm.complete"
    LLM_ERROR = "llm.error"

    # 内存相关
    MEMORY_ADD = "memory.add"
    MEMORY_DELETE = "memory.delete"
    MEMORY_UPDATE = "memory.update"
    MEMORY_DISTILL = "memory.distill"

    # 执行相关
    EXEC_START = "exec.start"
    EXEC_COMPLETE = "exec.complete"
    EXEC_ERROR = "exec.error"
    EXEC_INTERRUPT = "exec.interrupt"

    # 技能相关
    SKILL_LOAD = "skill.load"
    SKILL_UNLOAD = "skill.unload"
    SKILL_REFRESH = "skill.refresh"

    # 桥接相关
    BRIDGE_MESSAGE = "bridge.message"
    BRIDGE_ERROR = "bridge.error"
    BRIDGE_DISCONNECT = "bridge.disconnect"

    # 系统相关
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"


@dataclass
class Event:
    """事件基类"""
    type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""  # 事件源标识

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = EventType(self.type)


@dataclass
class LLMStartEvent(Event):
    """LLM 开始事件"""
    type: EventType = EventType.LLM_START
    model: str = ""
    messages_count: int = 0


@dataclass
class LLMChunkEvent(Event):
    """LLM 流式块事件"""
    type: EventType = EventType.LLM_CHUNK
    content: str = ""
    thinking: str = ""
    is_first: bool = False
    is_last: bool = False


@dataclass
class LLMCompleteEvent(Event):
    """LLM 完成事件"""
    type: EventType = EventType.LLM_COMPLETE
    content: str = ""
    thinking: str = ""
    tokens_used: int = 0
    duration_ms: float = 0.0


@dataclass
class ExecStartEvent(Event):
    """执行开始事件"""
    type: EventType = EventType.EXEC_START
    command: str = ""
    is_python: bool = False


@dataclass
class ExecCompleteEvent(Event):
    """执行完成事件"""
    type: EventType = EventType.EXEC_COMPLETE
    command: str = ""
    success: bool = True
    output: str = ""
    duration_ms: float = 0.0


@dataclass
class MemoryAddEvent(Event):
    """内存添加事件"""
    type: EventType = EventType.MEMORY_ADD
    memory_type: str = ""  # "working", "stm", "ltm", "todo"
    content: str = ""


@dataclass
class SkillLoadEvent(Event):
    """技能加载事件"""
    type: EventType = EventType.SKILL_LOAD
    skill_name: str = ""
    skill_count: int = 0
