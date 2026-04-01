"""
执行服务

提供统一的命令执行服务，协调内置命令和容器执行
"""

import logging
import re
import time
import traceback
from typing import Callable, Optional

from backend.alice.core.config import load_config

from ..executors.docker_executor import DockerExecutor
from ..models.execution_result import ExecutionResult, ExecutionStatus
from ..models.tool_calling import ToolExecutionResult, ToolInvocation, ToolResultPayload
from ..builtin.memory_command import MemoryCommandHandler
from ..builtin.todo_command import TodoCommandHandler
from ..builtin.toolkit_command import ToolkitCommandHandler

logger = logging.getLogger(__name__)


def _command_preview(command: str, limit: int = 200) -> str:
    normalized = " ".join(command.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


class _ExecutionServiceBase:
    """命令执行服务

    统一的命令执行入口，处理内置命令拦截和容器执行路由
    """

    def __init__(
        self,
        executor: Optional[DockerExecutor] = None,
        snapshot_manager=None
    ):
        self.executor = executor or DockerExecutor()
        self.snapshot_manager = None

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
        self._toolkit_handler = ToolkitCommandHandler()
        self.set_snapshot_manager(snapshot_manager)

    def execute_tool_call(
        self,
        invocation: ToolInvocation,
        log_context: Optional[dict] = None,
    ) -> ToolExecutionResult:
        raise NotImplementedError

    def _handle_toolkit(self, full_command: str, args: list[str]) -> str:
        raise NotImplementedError

    def _handle_update_prompt(self, full_command: str, args: list[str]) -> str:
        raise NotImplementedError

    def _handle_todo(self, full_command: str, args: list[str]) -> str:
        raise NotImplementedError

    def _handle_memory(self, full_command: str, args: list[str]) -> str:
        raise NotImplementedError

    def set_snapshot_manager(self, snapshot_manager) -> None:
        """同步更新技能快照依赖。"""
        self.snapshot_manager = snapshot_manager
        self._toolkit_handler.snapshot_manager = snapshot_manager

    def set_skill_registry(self, skill_registry) -> None:
        """将 SkillRegistry 适配为 toolkit 与 skills 文件读取依赖。"""
        self.set_snapshot_manager(SkillSnapshotManager(skill_registry))

    def set_skill_snapshot(self, skill_registry, skill_cache) -> None:
        """同时接入 SkillRegistry 与 SkillCache。"""
        self.set_snapshot_manager(SkillSnapshotManager(skill_registry, skill_cache))

    def execute_tool_invocation(
        self,
        invocation: ToolInvocation,
        log_context: Optional[dict] = None,
    ) -> ToolExecutionResult:
        return self.execute_tool_call(invocation, log_context=log_context)

    @staticmethod
    def _parse_tool_arguments(arguments: str) -> dict:
        import json

        try:
            payload = json.loads(arguments or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"无效的工具参数 JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("工具参数必须是 JSON object")
        return payload

    @staticmethod
    def _coerce_tool_result(
        invocation: ToolInvocation,
        raw_result: ExecutionResult | str,
    ) -> ToolExecutionResult:
        if isinstance(raw_result, ExecutionResult):
            execution_result = raw_result
        else:
            output_text = str(raw_result)
            execution_result = ExecutionResult(
                success=True,
                output=output_text,
                status=ExecutionStatus.SUCCESS,
                error="",
                exit_code=0,
            )

        payload = ToolResultPayload(
            tool_name=invocation.name,
            success=execution_result.success,
            output=execution_result.output,
            error=execution_result.error,
            exit_code=execution_result.exit_code,
            status=execution_result.status.value,
            metadata=dict(execution_result.metadata or {}),
        )
        return ToolExecutionResult(
            invocation=invocation,
            payload=payload,
            execution_result=execution_result,
        )


class SkillSnapshotManager:
    """统一适配 SkillRegistry / SkillCache 给 execution/toolkit 使用。"""

    def __init__(self, skill_registry, skill_cache=None):
        self._skill_registry = skill_registry
        self._skill_cache = skill_cache

    @property
    def skills(self) -> dict[str, dict]:
        if not self._skill_registry:
            return {}
        return {
            name: skill.to_dict()
            for name, skill in self._skill_registry.get_all_skills().items()
        }

    def refresh(self) -> int:
        if self._skill_registry is None:
            return 0
        count = self._skill_registry.refresh()
        if self._skill_cache is not None:
            self._skill_cache.clear_cache()
        return count

    def read_skill_file(self, relative_path: str) -> str | None:
        if self._skill_cache is not None:
            cached = self._skill_cache.read_skill_file(relative_path)
            if cached is not None:
                return cached

        if self._skill_registry is None:
            return None

        normalized = relative_path.strip().lstrip("/")
        if not normalized:
            return None

        skill_name, _, remainder = normalized.partition("/")
        skill = self._skill_registry.get_skill(skill_name)
        if skill is None:
            return None

        if not remainder or remainder == "SKILL.md":
            return skill.path.read_text(encoding="utf-8", errors="ignore")
        if skill.script_path and remainder == skill.script_path.name:
            return skill.script_path.read_text(encoding="utf-8", errors="ignore")
        return None


class ExecutionService(_ExecutionServiceBase):
    """命令执行服务

    统一的命令执行入口，处理内置命令拦截和容器执行路由
    """


    def _build_log_context(self, log_context: Optional[dict], phase: str) -> dict:
        """构建执行链路日志上下文。"""
        base = dict(log_context or {})
        trace_id = str(base.get("trace_id") or base.get("request_id") or "")
        request_id = str(base.get("request_id") or trace_id)
        session_id = str(base.get("session_id") or "")
        task_id = str(base.get("task_id") or request_id or session_id)
        span_root = str(base.get("span_id") or "execution")

        return {
            "trace_id": trace_id,
            "request_id": request_id,
            "task_id": task_id,
            "session_id": session_id,
            "span_id": f"{span_root}.{phase}",
            "component": "execution_service",
            "phase": phase,
        }

    def _log_execution_event(
        self,
        *,
        event_type: str,
        message: str,
        phase: str,
        log_context: Optional[dict],
        data: Optional[dict] = None,
        error: Optional[dict] = None,
        level: str = "info",
        legacy_event_type: str = "",
        with_exc_info: bool = False,
    ) -> None:
        context = self._build_log_context(log_context, phase=phase)
        payload_data = dict(data or {})
        if legacy_event_type:
            payload_data["legacy_event_type"] = legacy_event_type
        payload_data.setdefault("timing", {"duration_ms": 0})

        extra = {
            "event_type": event_type,
            "log_category": "tasks",
            "task_id": context["task_id"],
            "context": context,
            "data": payload_data,
        }
        if error is not None:
            extra["error"] = error

        if level == "warning":
            logger.warning(message, extra=extra)
        elif level == "error":
            logger.error(message, exc_info=with_exc_info, extra=extra)
        else:
            logger.info(message, extra=extra)

    def execute(
        self,
        command: str,
        is_python_code: bool = False,
        log_context: Optional[dict] = None,
    ) -> ExecutionResult | str:
        """执行命令

        Args:
            command: 要执行的命令字符串
            is_python_code: 是否为 Python 代码
            log_context: 链路追踪上下文

        Returns:
            ExecutionResult | str: 执行结果（兼容旧接口返回字符串）
        """
        started_at = time.monotonic()
        command_preview = _command_preview(command)
        command_type = "python" if is_python_code else "bash"
        execution_environment = "docker"

        self._log_execution_event(
            event_type="executor.command_prepared",
            message="Execution service prepared command",
            phase="command_prepared",
            log_context=log_context,
            legacy_event_type="tool_call",
            data={
                "command": command,
                "command_preview": command_preview,
                "command_type": command_type,
                "execution_environment": execution_environment,
            },
        )

        # 0. 安全审查
        is_safe, warning = self.executor.validate(command)
        if not is_safe:
            self._log_execution_event(
                event_type="executor.command_result",
                message="Command blocked by security rules",
                phase="command_blocked",
                log_context=log_context,
                level="warning",
                legacy_event_type="tool_error",
                data={
                    "command": command,
                    "command_preview": command_preview,
                    "command_type": command_type,
                    "execution_environment": execution_environment,
                    "status": "blocked",
                    "success": False,
                    "timing": {"duration_ms": int((time.monotonic() - started_at) * 1000)},
                },
                error={
                    "type": "SECURITY_BLOCKED",
                    "message": warning,
                },
            )
            return warning

        # 1. 拦截内置指令（在宿主机执行）
        if not is_python_code:
            cmd_strip = command.strip()
            builtin_result = self._try_handle_builtin(cmd_strip)
            if builtin_result is not None:
                self._log_execution_event(
                    event_type="executor.command_result",
                    message="Builtin command executed on host",
                    phase="builtin_executed",
                    log_context=log_context,
                    data={
                        "command": command,
                        "command_preview": command_preview,
                        "command_type": "builtin",
                        "execution_environment": "host",
                        "status": "success",
                        "success": True,
                        "output_length": len(builtin_result),
                        "timing": {"duration_ms": int((time.monotonic() - started_at) * 1000)},
                    },
                )
                return builtin_result

            # 性能优化：拦截 cat skills/* 命令，使用宿主机缓存读取
            cat_result = self._try_handle_cat_skills(cmd_strip)
            if cat_result is not None:
                self._log_execution_event(
                    event_type="executor.command_result",
                    message="Skill file served from host cache",
                    phase="cache_hit",
                    log_context=log_context,
                    data={
                        "command": command,
                        "command_preview": command_preview,
                        "command_type": command_type,
                        "execution_environment": "host",
                        "status": "success",
                        "success": True,
                        "output_length": len(cat_result),
                        "timing": {"duration_ms": int((time.monotonic() - started_at) * 1000)},
                    },
                )
                return cat_result

        # 2. Docker 容器执行
        try:
            docker_log_context = self._build_log_context(log_context, phase="docker_execute")
            try:
                result = self.executor.execute(
                    command,
                    is_python_code,
                    log_context=docker_log_context,
                )
            except TypeError:
                result = self.executor.execute(command, is_python_code)
        except Exception as e:
            self._log_execution_event(
                event_type="executor.command_result",
                message="Execution service failed to run command",
                phase="docker_execute",
                log_context=log_context,
                level="error",
                with_exc_info=True,
                legacy_event_type="tool_error",
                data={
                    "command": command,
                    "command_preview": command_preview,
                    "command_type": command_type,
                    "execution_environment": execution_environment,
                    "status": "failure",
                    "success": False,
                    "timing": {"duration_ms": int((time.monotonic() - started_at) * 1000)},
                },
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc(),
                },
            )
            raise

        # 兼容旧接口：返回字符串
        if isinstance(result, ExecutionResult):
            self._log_execution_event(
                event_type="executor.command_result",
                message="Execution service completed command",
                phase="command_result",
                log_context=log_context,
                legacy_event_type="tool_result",
                data={
                    "command": command,
                    "command_preview": command_preview,
                    "command_type": command_type,
                    "execution_environment": execution_environment,
                    "status": result.status.value,
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "output_length": len(result.output or ""),
                    "error_length": len(result.error or ""),
                    "timing": {"duration_ms": int((time.monotonic() - started_at) * 1000)},
                },
                error=(
                    None
                    if result.success
                    else {
                        "type": result.status.value.upper(),
                        "message": result.error or "Command execution failed",
                    }
                ),
                level="info" if result.success else "warning",
            )
            return result.output

        self._log_execution_event(
            event_type="executor.command_result",
            message="Execution service completed command",
            phase="command_result",
            log_context=log_context,
            legacy_event_type="tool_result",
            data={
                "command": command,
                "command_preview": command_preview,
                "command_type": command_type,
                "execution_environment": execution_environment,
                "status": "success",
                "success": True,
                "output_length": len(str(result)),
                "timing": {"duration_ms": int((time.monotonic() - started_at) * 1000)},
            },
        )
        return result

    def execute_tool_invocation(
        self,
        invocation: ToolInvocation,
        log_context: Optional[dict] = None,
    ) -> ToolExecutionResult:
        """兼容 ChatWorkflow 的结构化工具调用入口。"""
        return self.execute_tool_call(invocation, log_context=log_context)

    def execute_tool_call(
        self,
        invocation: ToolInvocation,
        log_context: Optional[dict] = None,
    ) -> ToolExecutionResult:
        """执行结构化工具调用。"""
        payload = self._parse_tool_arguments(invocation.arguments)

        if invocation.name == "run_bash":
            command = str(payload.get("command") or "")
            if not command:
                raise ValueError("run_bash 缺少 command 参数")
            raw_result = self.execute(command, is_python_code=False, log_context=log_context)
        elif invocation.name == "run_python":
            command = str(payload.get("code") or "")
            if not command:
                raise ValueError("run_python 缺少 code 参数")
            raw_result = self.execute(command, is_python_code=True, log_context=log_context)
        else:
            raise ValueError(f"不支持的工具: {invocation.name}")

        return self._coerce_tool_result(invocation, raw_result)

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
        settings = load_config()
        todo_path = str(settings.get_absolute_path(settings.memory.todo_path))

        # 尝试匹配引号包裹的内容
        content_match = re.search(r'["\'](.*?)["\']', full_command, re.DOTALL)
        if content_match:
            return self._todo_handler.handle_write(content_match.group(1), todo_path)

        parts = full_command.split(None, 1)
        if len(parts) > 1:
            content = parts[1].strip().strip('"\'')
            return self._todo_handler.handle_write(content, todo_path)

        return "错误: todo 指令需要提供任务清单内容。"

    def _handle_memory(self, full_command: str, args: list[str]) -> str:
        """处理 memory 命令"""
        settings = load_config()

        # 极简解析: memory "content" [--ltm]
        ltm_mode = "--ltm" in full_command
        target_path = str(
            settings.get_absolute_path(
                settings.memory.ltm_path if ltm_mode else settings.memory.stm_path
            )
        )
        if content_match := re.search(r'["\'](.*?)["\']', full_command, re.DOTALL):
            return self._memory_handler.handle_write(
                content_match.group(1),
                target_path,
                target="ltm" if ltm_mode else "stm"
            )

        parts = full_command.split(None, 1)
        if len(parts) > 1:
            content = parts[1].replace("--ltm", "").strip().strip('"\'')
            return self._memory_handler.handle_write(
                content,
                target_path,
                target="ltm" if ltm_mode else "stm"
            )

        return "错误: memory 指令需要提供记忆内容。"

    def _update_prompt_file(self, content: str) -> str:
        """更新提示词文件"""
        settings = load_config()
        prompt_path = settings.get_absolute_path(settings.prompt_path)

        try:
            with open(prompt_path, "w", encoding="utf-8") as f:
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
