from __future__ import annotations

"""
Command Executor Protocol

定义命令执行器与 execution backend 的接口规范。
"""

from typing import Protocol, Any
from dataclasses import dataclass
from abc import abstractmethod


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: str
    error: str = ""
    exit_code: int = 0
    execution_time: float = 0.0


@dataclass
class SecurityRule:
    """安全规则"""
    name: str
    pattern: str  # 正则表达式或命令前缀
    action: str  # "block", "warn", "allow"
    reason: str = ""


@dataclass(frozen=True)
class ExecutionBackendStatus:
    """统一 execution backend 状态快照。"""

    engine_ready: bool
    image_ready: bool
    container_exists: bool
    container_running: bool
    status_raw: str = ""

    @property
    def ready(self) -> bool:
        return self.engine_ready and self.image_ready and self.container_running


class ExecutionBackend(Protocol):
    """execution harness backend 替换边界。"""

    @abstractmethod
    def ensure_ready(
        self,
        *,
        force_rebuild: bool = False,
        on_build_progress: Any = None,
    ) -> ExecutionBackendStatus:
        """确保执行环境就绪。"""
        ...

    @abstractmethod
    def exec(
        self,
        command: Any,
        *,
        log_context: dict[str, Any] | None = None,
    ) -> Any:
        """执行结构化命令。"""
        ...

    @abstractmethod
    def status(self) -> ExecutionBackendStatus:
        """获取 backend 状态。"""
        ...

    @abstractmethod
    def interrupt(self) -> bool:
        """中断当前执行。"""
        ...

    @abstractmethod
    def cleanup(self, *, remove: bool = False, force: bool = False) -> bool:
        """清理执行环境。"""
        ...


class CommandExecutor(Protocol):
    """命令执行器接口"""

    @abstractmethod
    def execute(self, command: str, is_python_code: bool = False) -> ExecutionResult:
        """执行命令"""
        ...

    @abstractmethod
    def validate(self, command: str) -> tuple[bool, str]:
        """验证命令安全性，返回 (is_safe, warning_message)"""
        ...

    @abstractmethod
    def add_security_rule(self, rule: SecurityRule) -> None:
        """添加安全规则"""
        ...

    @abstractmethod
    def interrupt(self) -> bool:
        """中断当前执行"""
        ...


@dataclass(frozen=True)
class HarnessBundle:
    """统一返回 execution backend 与 executor 的装配结果。"""

    backend: Any
    executor: Any


__all__ = [
    "ExecutionResult",
    "SecurityRule",
    "ExecutionBackendStatus",
    "ExecutionBackend",
    "CommandExecutor",
    "HarnessBundle",
]
