"""
内存类型注册表

管理内存存储类型的注册
"""

from typing import Dict, Type, Optional, List
from dataclasses import dataclass
from abc import ABC, abstractmethod

from ..interfaces.memory_store import MemoryStore


@dataclass
class MemoryTypeSpec:
    """内存类型规范"""
    name: str
    store_class: Type[MemoryStore]
    description: str = ""
    file_path: str = ""  # 持久化文件路径


class MemoryRegistry(ABC):
    """内存注册表接口"""

    @abstractmethod
    def register(self, spec: MemoryTypeSpec) -> None:
        """注册内存类型"""
        ...

    @abstractmethod
    def unregister(self, name: str) -> None:
        """注销内存类型"""
        ...

    @abstractmethod
    def get(self, name: str) -> Optional[MemoryTypeSpec]:
        """获取内存类型规范"""
        ...

    @abstractmethod
    def list_all(self) -> List[MemoryTypeSpec]:
        """列出所有内存类型"""
        ...


class InMemoryMemoryRegistry(MemoryRegistry):
    """内存注册表实现"""

    # 预定义的内存类型
    WORKING = "working"
    STM = "stm"  # Short Term Memory
    LTM = "ltm"  # Long Term Memory
    TODO = "todo"

    def __init__(self):
        self._memory_types: Dict[str, MemoryTypeSpec] = {}

    def register(self, spec: MemoryTypeSpec) -> None:
        """注册内存类型"""
        self._memory_types[spec.name] = spec

    def unregister(self, name: str) -> None:
        """注销内存类型"""
        if name in self._memory_types:
            del self._memory_types[name]

    def get(self, name: str) -> Optional[MemoryTypeSpec]:
        """获取内存类型规范"""
        return self._memory_types.get(name)

    def list_all(self) -> List[MemoryTypeSpec]:
        """列出所有内存类型"""
        return list(self._memory_types.values())

    def get_standard_types(self) -> List[str]:
        """获取标准内存类型列表"""
        return [self.WORKING, self.STM, self.LTM, self.TODO]

    def clear(self) -> None:
        """清空所有内存类型"""
        self._memory_types.clear()


# 全局内存注册表实例
_global_memory_registry: Optional[InMemoryMemoryRegistry] = None


def get_memory_registry() -> InMemoryMemoryRegistry:
    """获取全局内存注册表实例"""
    global _global_memory_registry
    if _global_memory_registry is None:
        _global_memory_registry = InMemoryMemoryRegistry()
    return _global_memory_registry
