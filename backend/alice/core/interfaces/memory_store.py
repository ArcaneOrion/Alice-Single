"""
Memory Store Protocol

定义内存存储的接口规范
"""

from typing import Protocol, Iterator
from dataclasses import dataclass
from abc import abstractmethod
from datetime import datetime


@dataclass
class MemoryEntry:
    """内存条目"""
    content: str
    timestamp: datetime
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class RoundEntry:
    """对话轮次"""
    user_input: str
    assistant_thinking: str = ""
    assistant_response: str = ""
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class MemoryStore(Protocol):
    """内存存储接口"""

    @abstractmethod
    def add(self, entry: MemoryEntry) -> None:
        """添加内存条目"""
        ...

    @abstractmethod
    def get(self, key: str) -> MemoryEntry | None:
        """获取内存条目"""
        ...

    @abstractmethod
    def list(self, limit: int = 100) -> list[MemoryEntry]:
        """列出内存条目"""
        ...

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """搜索内存条目"""
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除内存条目"""
        ...

    @abstractmethod
    def clear(self) -> None:
        """清空所有条目"""
        ...


class WorkingMemoryStore(MemoryStore, Protocol):
    """工作内存接口（对话轮次管理）"""

    @abstractmethod
    def add_round(self, round_entry: RoundEntry) -> None:
        """添加对话轮次"""
        ...

    @abstractmethod
    def get_recent_rounds(self, count: int) -> list[RoundEntry]:
        """获取最近的对话轮次"""
        ...

    @abstractmethod
    def trim_to_max_rounds(self, max_rounds: int) -> None:
        """裁剪到最大轮数"""
        ...
