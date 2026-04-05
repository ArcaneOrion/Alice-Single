"""
命令注册表

管理内置命令的注册与分发
"""

from __future__ import annotations

from typing import Dict, Callable, Optional, List, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from pathlib import Path

from ..interfaces.command_executor import HarnessBundle
from backend.alice.domain.execution.executors.docker_executor import DockerExecutor
from backend.alice.infrastructure.docker.config import DockerConfig
from backend.alice.infrastructure.docker.container_manager import DockerExecutionBackend


@dataclass
class CommandSpec:
    """命令规范"""

    name: str
    description: str
    handler: Callable
    patterns: List[str] = field(default_factory=list)
    category: str = "general"

    def __post_init__(self):
        pass


@dataclass
class HarnessSpec:
    """执行后端装配规范。"""

    name: str
    factory: Callable[..., HarnessBundle]
    description: str = ""


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

    @abstractmethod
    def register_harness(self, spec: HarnessSpec) -> None:
        """注册 execution harness。"""
        ...

    @abstractmethod
    def get_harness(self, name: str) -> Optional[HarnessSpec]:
        """获取 execution harness。"""
        ...

    @abstractmethod
    def create_harness(self, name: str = "docker", **kwargs: Any) -> HarnessBundle:
        """创建 execution harness。"""
        ...


def _create_docker_harness(*, project_root: Path, **_kwargs: Any) -> HarnessBundle:
    docker_config = DockerConfig(project_root=project_root)
    backend = DockerExecutionBackend(docker_config)
    executor = DockerExecutor(docker_config=docker_config, backend=backend)
    return HarnessBundle(backend=backend, executor=executor)


class InMemoryCommandRegistry(CommandRegistry):
    """内存命令注册表实现"""

    def __init__(self):
        self._commands: Dict[str, CommandSpec] = {}
        self._harnesses: Dict[str, HarnessSpec] = {}
        self.register_harness(
            HarnessSpec(
                name="docker",
                factory=_create_docker_harness,
                description="默认 Docker execution harness",
            )
        )

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
        first_word = stripped.split()[0] if stripped else ""
        if first_word in self._commands:
            return self._commands[first_word]

        for spec in self._commands.values():
            for pattern in spec.patterns:
                if stripped.startswith(pattern):
                    return spec

        return None

    def list_all(self) -> List[CommandSpec]:
        """列出所有命令"""
        return list(self._commands.values())

    def register_harness(self, spec: HarnessSpec) -> None:
        """注册 execution harness。"""
        self._harnesses[spec.name] = spec

    def get_harness(self, name: str) -> Optional[HarnessSpec]:
        """获取 execution harness。"""
        return self._harnesses.get(name)

    def create_harness(self, name: str = "docker", **kwargs: Any) -> HarnessBundle:
        """创建 execution harness。"""
        spec = self.get_harness(name)
        if spec is None:
            raise ValueError(f"未注册的 execution harness: {name}")
        return spec.factory(**kwargs)

    def list_by_category(self, category: str) -> List[CommandSpec]:
        """按类别列出命令"""
        return [spec for spec in self._commands.values() if spec.category == category]

    def clear(self) -> None:
        """清空所有命令"""
        self._commands.clear()
        self._harnesses.clear()
        self.register_harness(
            HarnessSpec(
                name="docker",
                factory=_create_docker_harness,
                description="默认 Docker execution harness",
            )
        )


_global_command_registry: Optional[InMemoryCommandRegistry] = None


def get_command_registry() -> InMemoryCommandRegistry:
    """获取全局命令注册表实例"""
    global _global_command_registry
    if _global_command_registry is None:
        _global_command_registry = InMemoryCommandRegistry()
    return _global_command_registry
