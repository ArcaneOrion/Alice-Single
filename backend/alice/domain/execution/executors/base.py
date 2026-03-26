"""
执行器基类

定义命令执行器的抽象基类和接口规范
"""

from abc import ABC, abstractmethod
from typing import Protocol

from ..models.command import Command, CommandType
from ..models.execution_result import ExecutionResult, ExecutionStatus
from ..models.security_rule import SecurityRule


class CommandExecutor(Protocol):
    """命令执行器接口协议

    遵循 core/interfaces/command_executor.py 中的接口定义
    """

    @abstractmethod
    def execute(self, command: str, is_python_code: bool = False) -> ExecutionResult:
        """执行命令

        Args:
            command: 要执行的命令字符串
            is_python_code: 是否为 Python 代码

        Returns:
            ExecutionResult: 执行结果
        """
        ...

    @abstractmethod
    def validate(self, command: str) -> tuple[bool, str]:
        """验证命令安全性

        Args:
            command: 要验证的命令字符串

        Returns:
            tuple[bool, str]: (is_safe, warning_message)
        """
        ...

    @abstractmethod
    def add_security_rule(self, rule: SecurityRule) -> None:
        """添加安全规则

        Args:
            rule: 安全规则对象
        """
        ...

    @abstractmethod
    def interrupt(self) -> bool:
        """中断当前执行

        Returns:
            bool: 是否成功中断
        """
        ...


class BaseExecutor(ABC):
    """命令执行器抽象基类

    提供通用的执行逻辑和状态管理
    """

    def __init__(self):
        self._interrupted: bool = False
        self._security_rules: list[SecurityRule] = []

    @abstractmethod
    def _do_execute(self, command: Command) -> ExecutionResult:
        """实际执行命令的抽象方法

        Args:
            command: 命令对象

        Returns:
            ExecutionResult: 执行结果
        """
        ...

    def execute(self, command: str, is_python_code: bool = False) -> ExecutionResult:
        """执行命令

        Args:
            command: 要执行的命令字符串
            is_python_code: 是否为 Python 代码

        Returns:
            ExecutionResult: 执行结果
        """
        # 检查中断状态
        if self._interrupted:
            self._interrupted = False
            return ExecutionResult.error_result(
                "执行被用户中断",
                status=ExecutionStatus.INTERRUPTED
            )

        # 构造命令对象
        cmd_type = CommandType.PYTHON if is_python_code else CommandType.BASH
        cmd = Command(
            raw=command,
            type=cmd_type,
            environment=self._get_environment()
        )

        # 安全验证
        is_safe, warning = self.validate(command)
        if not is_safe:
            return ExecutionResult.blocked_result(warning)

        # 执行命令
        return self._do_execute(cmd)

    def validate(self, command: str) -> tuple[bool, str]:
        """验证命令安全性

        Args:
            command: 要验证的命令字符串

        Returns:
            tuple[bool, str]: (is_safe, warning_message)
        """
        for rule in sorted(self._security_rules, key=lambda r: r.priority, reverse=True):
            if rule.matches(command):
                if rule.is_blocked():
                    return False, rule.reason or f"命令被安全规则 '{rule.name}' 拦截"
                elif rule.is_warning():
                    return True, f"警告: {rule.reason}"

        return True, ""

    def add_security_rule(self, rule: SecurityRule) -> None:
        """添加安全规则

        Args:
            rule: 安全规则对象
        """
        self._security_rules.append(rule)

    def interrupt(self) -> bool:
        """中断当前执行

        Returns:
            bool: 是否成功中断
        """
        self._interrupted = True
        return True

    def reset_interrupt(self) -> None:
        """重置中断状态"""
        self._interrupted = False

    @abstractmethod
    def _get_environment(self):
        """获取执行环境枚举值"""
        ...


__all__ = [
    "CommandExecutor",
    "BaseExecutor",
]
