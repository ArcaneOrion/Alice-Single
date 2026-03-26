"""
安全服务

提供命令安全审查功能
"""

import logging
from typing import Optional

from ..models.command import Command
from ..models.execution_result import ExecutionResult
from ..models.security_rule import SecurityRule, SecurityAction, DEFAULT_SECURITY_RULES

logger = logging.getLogger(__name__)


class SecurityService:
    """命令安全审查服务

    集中管理安全规则，提供命令安全检查功能
    """

    def __init__(self, rules: Optional[list[SecurityRule]] = None):
        self._rules: list[SecurityRule] = rules or []

        # 加载默认规则
        for rule in DEFAULT_SECURITY_RULES:
            self.add_rule(rule)

    def add_rule(self, rule: SecurityRule) -> None:
        """添加安全规则

        Args:
            rule: 安全规则对象
        """
        self._rules.append(rule)
        logger.debug(f"添加安全规则: {rule.name} ({rule.action.value})")

    def remove_rule(self, rule_name: str) -> bool:
        """移除安全规则

        Args:
            rule_name: 规则名称

        Returns:
            bool: 是否成功移除
        """
        original_count = len(self._rules)
        self._rules = [r for r in self._rules if r.name != rule_name]
        return len(self._rules) < original_count

    def check_command(self, command: str) -> tuple[bool, str, Optional[SecurityRule]]:
        """检查命令安全性

        Args:
            command: 要检查的命令字符串

        Returns:
            tuple[bool, str, Optional[SecurityRule]]:
                - is_safe: 是否安全
                - message: 安全信息（警告或拦截原因）
                - matched_rule: 匹配的规则（如果有）
        """
        # 按优先级排序，高优先级先检查
        sorted_rules = sorted(self._rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if rule.matches(command):
                if rule.action == SecurityAction.BLOCK:
                    logger.warning(f"命令被规则 '{rule.name}' 拦截: {command[:100]}")
                    return False, rule.reason or f"命令被安全规则 '{rule.name}' 拦截", rule

                elif rule.action == SecurityAction.WARN:
                    logger.info(f"命令触发警告规则 '{rule.name}': {command[:100]}")
                    return True, f"警告: {rule.reason}", rule

                elif rule.action == SecurityAction.ALLOW:
                    logger.debug(f"命令被规则 '{rule.name}' 显式允许: {command[:100]}")
                    return True, "", rule

        # 没有匹配任何规则，默认允许
        return True, "", None

    def is_safe(self, command: str) -> bool:
        """快速检查命令是否安全

        Args:
            command: 要检查的命令字符串

        Returns:
            bool: 是否安全
        """
        is_safe, _, _ = self.check_command(command)
        return is_safe

    def get_warning(self, command: str) -> str:
        """获取命令的安全警告信息

        Args:
            command: 要检查的命令字符串

        Returns:
            str: 警告信息（如果没有警告则返回空字符串）
        """
        _, message, _ = self.check_command(command)
        return message

    def list_rules(self) -> list[dict]:
        """列出所有安全规则

        Returns:
            list[dict]: 规则列表
        """
        return [
            {
                "name": r.name,
                "action": r.action.value,
                "reason": r.reason,
                "priority": r.priority
            }
            for r in sorted(self._rules, key=lambda r: r.priority, reverse=True)
        ]

    def clear_rules(self) -> None:
        """清除所有安全规则（包括默认规则）"""
        self._rules.clear()
        logger.warning("已清除所有安全规则")

    def reset_to_defaults(self) -> None:
        """重置为默认安全规则"""
        self._rules.clear()
        for rule in DEFAULT_SECURITY_RULES:
            self.add_rule(rule)
        logger.info("已重置为默认安全规则")


__all__ = [
    "SecurityService",
]
