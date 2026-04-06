"""
执行器基类

定义命令执行器的抽象基类和 execution backend 接口规范。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol

from ..models.command import Command, CommandType, ExecutionEnvironment
from ..models.execution_result import ExecutionResult, ExecutionStatus
from ..models.security_rule import SecurityRule


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
    """统一 execution backend seam。"""

    def ensure_ready(
        self,
        *,
        force_rebuild: bool = False,
        on_build_progress: Any = None,
    ) -> ExecutionBackendStatus:
        ...

    def exec(
        self,
        command: Command,
        *,
        log_context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        ...

    def status(self) -> ExecutionBackendStatus:
        ...

    def interrupt(self) -> bool:
        ...

    def cleanup(self, *, remove: bool = False, force: bool = False) -> bool:
        ...


class CommandExecutor(Protocol):
    """命令执行器接口协议"""

    @abstractmethod
    def execute(self, command: str, is_python_code: bool = False) -> ExecutionResult:
        """执行命令"""
        ...

    @abstractmethod
    def validate(self, command: str) -> tuple[bool, str]:
        """验证命令安全性"""
        ...

    @abstractmethod
    def add_security_rule(self, rule: SecurityRule) -> None:
        """添加安全规则"""
        ...

    @abstractmethod
    def interrupt(self) -> bool:
        """中断当前执行"""
        ...


class BaseExecutor(ABC):
    """命令执行器抽象基类

    提供通用的执行逻辑和状态管理。
    """

    def __init__(self):
        self._interrupted: bool = False
        self._security_rules: list[SecurityRule] = []

    @abstractmethod
    def _do_execute(self, command: Command) -> ExecutionResult:
        """实际执行命令的抽象方法"""
        ...

    def execute(self, command: str, is_python_code: bool = False) -> ExecutionResult:
        """执行命令"""
        if self._interrupted:
            self._interrupted = False
            return ExecutionResult.error_result(
                "执行被用户中断",
                status=ExecutionStatus.INTERRUPTED,
            )

        cmd_type = CommandType.PYTHON if is_python_code else CommandType.BASH
        cmd = Command(
            raw=command,
            type=cmd_type,
            environment=self._get_environment(),
        )

        is_safe, warning = self.validate(command)
        if not is_safe:
            return ExecutionResult.blocked_result(warning)

        return self._do_execute(cmd)

    def validate(self, command: str) -> tuple[bool, str]:
        """验证命令安全性"""
        for rule in sorted(self._security_rules, key=lambda r: r.priority, reverse=True):
            if rule.matches(command):
                if rule.is_blocked():
                    return False, rule.reason or f"命令被安全规则 '{rule.name}' 拦截"
                if rule.is_warning():
                    return True, f"警告: {rule.reason}"

        return True, ""

    def add_security_rule(self, rule: SecurityRule) -> None:
        """添加安全规则"""
        self._security_rules.append(rule)

    def interrupt(self) -> bool:
        """中断当前执行"""
        self._interrupted = True
        return True

    def reset_interrupt(self) -> None:
        """重置中断状态"""
        self._interrupted = False

    @abstractmethod
    def _get_environment(self) -> ExecutionEnvironment:
        """获取执行环境枚举值"""
        ...


__all__ = [
    "ExecutionBackendStatus",
    "ExecutionBackend",
    "CommandExecutor",
    "BaseExecutor",
]
