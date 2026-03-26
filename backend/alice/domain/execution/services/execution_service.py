"""
执行服务

提供统一的命令执行服务，协调内置命令和容器执行
"""

import logging
import os
import re
import subprocess
from typing import Callable, Optional

from ..executors.docker_executor import DockerExecutor
from ..models.command import Command, CommandType
from ..models.execution_result import ExecutionResult
from ..builtin.memory_command import MemoryCommandHandler
from ..builtin.todo_command import TodoCommandHandler
from ..builtin.toolkit_command import ToolkitCommandHandler

logger = logging.getLogger(__name__)


class ExecutionService:
    """命令执行服务

    统一的命令执行入口，处理内置命令拦截和容器执行路由
    """

    def __init__(
        self,
        executor: Optional[DockerExecutor] = None,
        snapshot_manager=None
    ):
        self.executor = executor or DockerExecutor()
        self.snapshot_manager = snapshot_manager

        # 内置命令处理器
        self._builtin_handlers: dict[str, Callable] = {
            "toolkit": self._handle_toolkit,
            "update_prompt": self._handle_update_prompt,
            "todo": self._handle_todo,
            "memory": self._handle_memory,
        }

        # 具体命令处理器实例
        self._memory_handler = MemoryCommandHandler()
        self._todo_handler = TodoCommandHandler()
        self._toolkit_handler = ToolkitCommandHandler(snapshot_manager)

    def execute(self, command: str, is_python_code: bool = False) -> ExecutionResult | str:
        """执行命令

        Args:
            command: 要执行的命令字符串
            is_python_code: 是否为 Python 代码

        Returns:
            ExecutionResult | str: 执行结果（兼容旧接口返回字符串）
        """
        # 0. 安全审查
        is_safe, warning = self.executor.validate(command)
        if not is_safe:
            logger.warning(f"命令被安全审查拦截: {command}")
            return warning

        # 1. 拦截内置指令（在宿主机执行）
        if not is_python_code:
            cmd_strip = command.strip()
            builtin_result = self._try_handle_builtin(cmd_strip)
            if builtin_result is not None:
                return builtin_result

            # 性能优化：拦截 cat skills/* 命令，使用宿主机缓存读取
            cat_result = self._try_handle_cat_skills(cmd_strip)
            if cat_result is not None:
                return cat_result

        # 2. Docker 容器执行
        result = self.executor.execute(command, is_python_code)

        # 兼容旧接口：返回字符串
        if isinstance(result, ExecutionResult):
            return result.output
        return result

    def _try_handle_builtin(self, command: str) -> Optional[str]:
        """尝试处理内置命令

        Args:
            command: 命令字符串

        Returns:
            Optional[str]: 如果是内置命令，返回处理结果；否则返回 None
        """
        parts = command.split(None, 1)
        if not parts:
            return None

        cmd_name = parts[0]
        args = parts[1].split() if len(parts) > 1 else []

        if cmd_name in self._builtin_handlers:
            return self._builtin_handlers[cmd_name](command, args)

        return None

    def _try_handle_cat_skills(self, command: str) -> Optional[str]:
        """尝试处理 cat skills/* 命令（缓存优化）

        Args:
            command: 命令字符串

        Returns:
            Optional[str]: 如果是 cat skills 命令且缓存命中，返回内容；否则返回 None
        """
        if self.snapshot_manager is None:
            return None

        cat_match = re.match(r'cat\s+skills/(.+)', command.strip())
        if cat_match:
            file_path = cat_match.group(1)
            content = self.snapshot_manager.read_skill_file(file_path)
            if content is not None:
                logger.info(f"通过宿主机缓存读取技能文件: skills/{file_path}")
                return content

        return None

    def _handle_toolkit(self, full_command: str, args: list[str]) -> str:
        """处理 toolkit 命令"""
        return self._toolkit_handler.handle(args)

    def _handle_update_prompt(self, full_command: str, args: list[str]) -> str:
        """处理 update_prompt 命令"""
        # 提取 update_prompt 之后的所有内容
        parts = full_command.split(None, 1)
        if len(parts) > 1:
            content = parts[1].strip().strip('"\'')
            return self._update_prompt_file(content)
        return "错误: update_prompt 需要提供新的提示词内容。"

    def _handle_todo(self, full_command: str, args: list[str]) -> str:
        """处理 todo 命令"""
        import config

        # 尝试匹配引号包裹的内容
        content_match = re.search(r'["\'](.*?)["\']', full_command, re.DOTALL)
        if content_match:
            return self._todo_handler.handle_write(content_match.group(1), config.TODO_FILE_PATH)

        parts = full_command.split(None, 1)
        if len(parts) > 1:
            content = parts[1].strip().strip('"\'')
            return self._todo_handler.handle_write(content, config.TODO_FILE_PATH)

        return "错误: todo 指令需要提供任务清单内容。"

    def _handle_memory(self, full_command: str, args: list[str]) -> str:
        """处理 memory 命令"""
        import config

        # 极简解析: memory "content" [--ltm]
        ltm_mode = "--ltm" in full_command
        content_match = re.search(r'["\'](.*?)["\']', full_command, re.DOTALL)
        if content_match:
            target_path = config.MEMORY_FILE_PATH if ltm_mode else config.SHORT_TERM_MEMORY_FILE_PATH
            return self._memory_handler.handle_write(
                content_match.group(1),
                target_path,
                target="ltm" if ltm_mode else "stm"
            )
        else:
            parts = full_command.split(None, 1)
            if len(parts) > 1:
                content = parts[1].replace("--ltm", "").strip().strip('"\'')
                target_path = config.MEMORY_FILE_PATH if ltm_mode else config.SHORT_TERM_MEMORY_FILE_PATH
                return self._memory_handler.handle_write(
                    content,
                    target_path,
                    target="ltm" if ltm_mode else "stm"
                )

        return "错误: memory 指令需要提供记忆内容。"

    def _update_prompt_file(self, content: str) -> str:
        """更新提示词文件"""
        import config

        try:
            with open(config.DEFAULT_PROMPT_PATH, "w", encoding="utf-8") as f:
                f.write(content.strip())
            return "已成功更新宿主机人设文件 (prompts/alice.md)。新指令将在下一轮对话生效。"
        except Exception as e:
            return f"更新人设文件失败: {str(e)}"

    def validate(self, command: str) -> tuple[bool, str]:
        """验证命令安全性

        Args:
            command: 要验证的命令字符串

        Returns:
            tuple[bool, str]: (is_safe, warning_message)
        """
        return self.executor.validate(command)

    def add_security_rule(self, rule) -> None:
        """添加安全规则"""
        self.executor.add_security_rule(rule)

    def interrupt(self) -> bool:
        """中断当前执行"""
        return self.executor.interrupt()


__all__ = [
    "ExecutionService",
]
