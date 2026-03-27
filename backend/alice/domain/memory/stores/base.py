"""
Base Store

内存存储的基础抽象类，实现 MemoryStore 和 WorkingMemoryStore 接口。
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from backend.alice.core.interfaces.memory_store import MemoryStore, WorkingMemoryStore, MemoryEntry, RoundEntry


class BaseMemoryStore(ABC):
    """内存存储基础抽象类

    实现 MemoryStore 接口的基础功能，子类只需实现核心存储逻辑。
    """

    def __init__(self, file_path: str):
        """初始化存储

        Args:
            file_path: 关联的文件路径
        """
        self.file_path = file_path

    def add(self, entry: MemoryEntry) -> None:
        """添加内存条目（需要子类实现）"""
        raise NotImplementedError

    def get(self, key: str) -> Optional[MemoryEntry]:
        """获取内存条目（需要子类实现）"""
        raise NotImplementedError

    def list(self, limit: int = 100) -> list[MemoryEntry]:
        """列出内存条目（需要子类实现）"""
        raise NotImplementedError

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """搜索内存条目（需要子类实现）"""
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        """删除内存条目（需要子类实现）"""
        raise NotImplementedError

    def clear(self) -> None:
        """清空所有条目（需要子类实现）"""
        raise NotImplementedError


class BaseWorkingMemoryStore(ABC):
    """工作内存存储基础抽象类

    实现 WorkingMemoryStore 接口的基础功能。
    """

    def __init__(self, file_path: str):
        """初始化工作内存存储"""
        self.file_path = file_path

    def add_round(self, round_entry: RoundEntry) -> None:
        """添加对话轮次（需要子类实现）"""
        raise NotImplementedError

    def get_recent_rounds(self, count: int) -> list[RoundEntry]:
        """获取最近的对话轮次（需要子类实现）"""
        raise NotImplementedError

    def trim_to_max_rounds(self, max_rounds: int) -> None:
        """裁剪到最大轮数（需要子类实现）"""
        raise NotImplementedError

    # 从 MemoryStore 继承的方法
    def add(self, entry: MemoryEntry) -> None:
        """添加内存条目（需要子类实现）"""
        raise NotImplementedError

    def get(self, key: str) -> Optional[MemoryEntry]:
        """获取内存条目（需要子类实现）"""
        raise NotImplementedError

    def list(self, limit: int = 100) -> list[MemoryEntry]:
        """列出内存条目（需要子类实现）"""
        raise NotImplementedError

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """搜索内存条目（需要子类实现）"""
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        """删除内存条目（需要子类实现）"""
        raise NotImplementedError

    def clear(self) -> None:
        """清空所有条目（需要子类实现）"""
        raise NotImplementedError


__all__ = ["BaseMemoryStore", "BaseWorkingMemoryStore"]
