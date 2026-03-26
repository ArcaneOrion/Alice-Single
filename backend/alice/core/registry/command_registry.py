"""
命令注册表

管理内置命令的注册与分发
"""

from typing import Dict, Callable, Optional, List
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class CommandSpec:
    """命令规范"""
    name: str
    description: str
    handler: Callable
    patterns: List[str] = None
    category: str = "general"

    def __post_init__(self):
        if self.patterns is None:
            self.patterns = []


class CommandRegistry(ABC):
    """命令注册表接口"""

    @abstractmethod
    def register(self, spec: CommandSpec) -> None:
        """注册命令"""
        ...

    @abstractmethod
    def unregister(self, name: str) -> None:
        """注销命令"""
        ...

    @abstractmethod
    def get(self, name: str) -> Optional[CommandSpec]:
        """获取命令规范"""
        ...

    @abstractmethod
    def match(self, input_text: str) -> Optional[CommandSpec]:
        """匹配输入文本对应的命令"""
        ...

    @abstractmethod
    def list_all(self) -> List[CommandSpec]:
        """列出所有命令"""
        ...


class InMemoryCommandRegistry(CommandRegistry):
    """内存命令注册表实现"""

    def __init__(self):
        self._commands: Dict[str, CommandSpec] = {}

    def register(self, spec: CommandSpec) -> None:
        """注册命令"""
        self._commands[spec.name] = spec

    def unregister(self, name: str) -> None:
        """注销命令"""
        if name in self._commands:
            del self._commands[name]

    def get(self, name: str) -> Optional[CommandSpec]:
        """获取命令规范"""
        return self._commands.get(name)

    def match(self, input_text: str) -> Optional[CommandSpec]:
        """匹配输入文本对应的命令"""
        stripped = input_text.strip()

        # 首先检查直接命令名匹配
        first_word = stripped.split()[0] if stripped else ""
        if first_word in self._commands:
            return self._commands[first_word]

        # 检查模式匹配
        for spec in self._commands.values():
            for pattern in spec.patterns:
                if stripped.startswith(pattern):
                    return spec

        return None

    def list_all(self) -> List[CommandSpec]:
        """列出所有命令"""
        return list(self._commands.values())

    def list_by_category(self, category: str) -> List[CommandSpec]:
        """按类别列出命令"""
        return [spec for spec in self._commands.values() if spec.category == category]

    def clear(self) -> None:
        """清空所有命令"""
        self._commands.clear()


# 全局命令注册表实例
_global_command_registry: Optional[InMemoryCommandRegistry] = None


def get_command_registry() -> InMemoryCommandRegistry:
    """获取全局命令注册表实例"""
    global _global_command_registry
    if _global_command_registry is None:
        _global_command_registry = InMemoryCommandRegistry()
    return _global_command_registry
