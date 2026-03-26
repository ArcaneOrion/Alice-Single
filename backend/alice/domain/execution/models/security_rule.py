"""
安全规则模型

定义命令安全审查的规则结构
"""

from dataclasses import dataclass, field
from enum import Enum
from re import Pattern
from typing import Union


class SecurityAction(Enum):
    """安全动作枚举"""
    BLOCK = "block"    # 阻止执行
    WARN = "warn"      # 警告但允许执行
    ALLOW = "allow"    # 允许执行


@dataclass
class SecurityRule:
    """安全规则

    定义命令安全检查的规则，支持正则表达式和前缀匹配
    """

    name: str  # 规则名称
    pattern: Union[str, Pattern]  # 正则表达式或命令前缀
    action: SecurityAction  # 安全动作
    reason: str = field(default="")  # 规则说明
    priority: int = field(default=0)  # 优先级，越高越先检查

    def matches(self, command: str) -> bool:
        """检查命令是否匹配此规则"""
        if isinstance(self.pattern, Pattern):
            return bool(self.pattern.search(command))

        pattern_str = str(self.pattern)
        command_lower = command.lower()

        # 前缀匹配
        if command_lower.startswith(pattern_str.lower()):
            return True

        # 包含匹配（针对 " rm " 这种子串检测）
        if pattern_str.startswith(" ") and pattern_str.endswith(" "):
            return f" {pattern_str.strip()} " in f" {command_lower} "

        return False

    def is_blocked(self) -> bool:
        """是否为阻止规则"""
        return self.action == SecurityAction.BLOCK

    def is_warning(self) -> bool:
        """是否为警告规则"""
        return self.action == SecurityAction.WARN


# 预定义的安全规则
DEFAULT_SECURITY_RULES = [
    SecurityRule(
        name="dangerous_rm",
        pattern=r"rm\s+-rf?\s+/",
        action=SecurityAction.BLOCK,
        reason="禁止在容器内使用 rm 指令删除根目录。如需删除文件，请通过其他方式操作。"
    ),
    SecurityRule(
        name="rm_command",
        pattern=r"rm\s",
        action=SecurityAction.BLOCK,
        reason="为了系统安全，禁止在容器内使用 rm 指令。如需删除文件，请通过其他方式操作。"
    ),
]


__all__ = [
    "SecurityRule",
    "SecurityAction",
    "DEFAULT_SECURITY_RULES",
]
