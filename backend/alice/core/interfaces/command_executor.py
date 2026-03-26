"""
Command Executor Protocol

定义命令执行器的接口规范
"""

from typing import Protocol
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
