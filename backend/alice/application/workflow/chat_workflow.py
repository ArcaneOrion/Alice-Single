"""
聊天工作流

实现 ReAct 模式的聊天工作流：思考 -> 行动 -> 观察。
"""

import logging
import re
import time
import traceback
from typing import Iterator, Optional
from uuid import uuid4

from .base_workflow import Workflow, WorkflowContext
from ..dto import (
    ApplicationResponse,
    RequestContext,
    StatusResponse,
    ThinkingResponse,
    ContentResponse,
    ExecutingToolResponse,
    DoneResponse,
    ErrorResponse,
    TokensResponse,
    StatusType,
)
from backend.alice.domain.llm.parsers.stream_parser import StreamParser


logger = logging.getLogger(__name__)


def _extract_workflow_logging_context(context: WorkflowContext) -> dict:
    """提取工作流日志上下文（兼容缺省字段）"""
    request_context = context.request_context
    metadata = request_context.metadata if isinstance(request_context.metadata, dict) else {}
    session_id = str(metadata.get("session_id") or "")
    trace_id = str(metadata.get("trace_id") or metadata.get("request_id") or "")
    request_id = str(metadata.get("request_id") or trace_id)
    task_id = str(metadata.get("task_id") or request_id or session_id)
    span_id = str(metadata.get("span_id") or f"workflow.{uuid4().hex[:12]}")

    return {
        "trace_id": trace_id,
        "task_id": task_id,
        "request_id": request_id,
        "session_id": session_id,
        "span_id": span_id,
        "component": "chat_workflow",
        "phase": "idle",
        "request_type": request_context.request_type.value,
        "workflow": "chat_workflow",
    }


class ChatWorkflow(Workflow):
    """聊天工作流

    实现 ReAct 循环：
    1. 接收用户输入
    2. LLM 生成响应（可能包含工具调用）
    3. 如果有工具调用，执行并返回反馈
    4. 重复直到无工具调用
    """

    def __init__(
        self,
        chat_service=None,
        execution_service=None,
        stream_parser: Optional[StreamParser] = None,
        max_iterations: int = 10,
    ):
        """初始化聊天工作流

        Args:
            chat_service: 聊天服务
            execution_service: 执行服务
            stream_parser: 流解析器
            max_iterations: 最大迭代次数（防止无限循环）
        """
        self.chat_service = chat_service
        self.execution_service = execution_service
        self.stream_parser = stream_parser or StreamParser()
        self.max_iterations = max_iterations

    @property
    def name(self) -> str:
        return "ChatWorkflow"

    def can_handle(self, context: RequestContext) -> bool:
        """判断是否可以处理该请求"""
        return context.request_type.value == "chat"

    def execute(self, context: WorkflowContext) -> Iterator[ApplicationResponse]:
        """执行聊天工作流

        Args:
            context: 工作流上下文

        Yields:
            应用响应
        """
        # 发送开始思考信号
        yield StatusResponse(status=StatusType.THINKING)

        # 添加用户消息到历史
        if self.chat_service:
            self.chat_service.add_user_message(context.user_input)

        iteration = 0
        full_content = ""
        full_thinking = ""
        base_log_context = _extract_workflow_logging_context(context)

        def log_transition(
            phase: str,
            message: str,
            *,
            iteration_no: int | None = None,
            level: str = "info",
            legacy_event_type: str = "",
            data: Optional[dict] = None,
            error: Optional[dict] = None,
            with_exc_info: bool = False,
        ) -> None:
            log_context = dict(base_log_context)
            log_context["phase"] = phase
            span_parts = [str(base_log_context.get("span_id") or "workflow")]
            if iteration_no is not None:
                span_parts.append(f"iter{iteration_no}")
            span_parts.append(phase)
            log_context["span_id"] = ".".join(span_parts)

            payload_data = dict(data or {})
            if iteration_no is not None and "iteration" not in payload_data:
                payload_data["iteration"] = iteration_no
            if legacy_event_type:
                payload_data["legacy_event_type"] = legacy_event_type
            payload_data.setdefault("timing", {"duration_ms": 0})

            extra = {
                "event_type": "workflow.state_transition",
                "log_category": "tasks",
                "task_id": log_context["task_id"],
                "context": log_context,
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

        while iteration < self.max_iterations:
            iteration += 1
            iteration_started_at = time.monotonic()

            log_transition(
                phase="iteration_start",
                message="Chat workflow iteration started",
                iteration_no=iteration,
                legacy_event_type="iteration_start",
                data={"max_iterations": self.max_iterations},
            )

            if context.interrupted:
                log_transition(
                    phase="iteration_end",
                    message="Chat workflow interrupted",
                    iteration_no=iteration,
                    legacy_event_type="iteration_end",
                    data={
                        "end_reason": "interrupted",
                        "timing": {
                            "duration_ms": int((time.monotonic() - iteration_started_at) * 1000)
                        },
                    },
                )
                yield DoneResponse()
                break

            # 流式生成响应
            try:
                log_transition(
                    phase="waiting_for_model",
                    message="Chat workflow waiting for model stream",
                    iteration_no=iteration,
                    data={"message_count": len(self.chat_service.messages) if self.chat_service else 0},
                )
                if self.chat_service:
                    response_iter = self.chat_service.provider.stream_chat(
                        self.chat_service.messages
                    )
                else:
                    yield ErrorResponse(content="Chat service not available", code="NO_SERVICE")
                    break
            except Exception as e:
                error_trace = traceback.format_exc()
                log_transition(
                    phase="iteration_end",
                    message="Chat request failed",
                    iteration_no=iteration,
                    level="error",
                    with_exc_info=True,
                    legacy_event_type="iteration_end",
                    data={
                        "end_reason": "chat_error",
                        "timing": {
                            "duration_ms": int((time.monotonic() - iteration_started_at) * 1000)
                        },
                    },
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": error_trace,
                    },
                )
                yield ErrorResponse(content=f"Chat request failed: {str(e)}", code="CHAT_ERROR")
                break

            # 处理流式响应
            self.stream_parser.reset()
            usage = None
            chunk_count = 0
            log_transition(
                phase="parsing_stream",
                message="Chat workflow started parsing model stream",
                iteration_no=iteration,
            )

            for chunk in response_iter:
                if context.interrupted:
                    break
                chunk_count += 1

                # 处理 Token 统计
                if chunk.usage:
                    usage = chunk.usage
                    yield TokensResponse(
                        total=chunk.usage.total_tokens,
                        prompt=chunk.usage.prompt_tokens,
                        completion=chunk.usage.completion_tokens,
                    )

                # 处理思考内容
                if chunk.thinking:
                    full_thinking += chunk.thinking
                    yield ThinkingResponse(content=chunk.thinking)

                # 处理正文内容（通过流解析器分流）
                if chunk.content:
                    full_content += chunk.content
                    parsed_messages = self.stream_parser.process_chunk(chunk.content)
                    for msg in parsed_messages:
                        if msg.type.value == "thinking":
                            yield ThinkingResponse(content=msg.content)
                        else:
                            yield ContentResponse(content=msg.content)

            # 冲刷剩余内容
            for msg in self.stream_parser.flush():
                if msg.type.value == "thinking":
                    yield ThinkingResponse(content=msg.content)
                else:
                    yield ContentResponse(content=msg.content)

            if context.interrupted:
                log_transition(
                    phase="iteration_end",
                    message="Chat workflow interrupted during stream",
                    iteration_no=iteration,
                    legacy_event_type="iteration_end",
                    data={
                        "end_reason": "interrupted_during_stream",
                        "chunk_count": chunk_count,
                        "timing": {
                            "duration_ms": int((time.monotonic() - iteration_started_at) * 1000)
                        },
                    },
                )
                yield DoneResponse()
                break

            # 检查工具调用
            tool_calls = self._extract_tool_calls(full_content)
            tool_types = sorted({tool_type for tool_type, _ in tool_calls})

            log_transition(
                phase="tool_detection",
                message="Tool detection completed",
                iteration_no=iteration,
                legacy_event_type="tool_detection",
                data={
                    "chunk_count": chunk_count,
                    "content_length": len(full_content),
                    "thinking_length": len(full_thinking),
                    "tool_call_count": len(tool_calls),
                    "tool_types": tool_types,
                    "usage": {
                        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
                    },
                },
            )

            if not tool_calls:
                # 无工具调用，结束
                if self.chat_service:
                    self.chat_service.add_assistant_message(full_content)
                log_transition(
                    phase="iteration_end",
                    message="Chat workflow iteration completed",
                    iteration_no=iteration,
                    legacy_event_type="iteration_end",
                    data={
                        "end_reason": "completed_without_tool",
                        "tool_call_count": 0,
                        "content_length": len(full_content),
                        "thinking_length": len(full_thinking),
                        "timing": {
                            "duration_ms": int((time.monotonic() - iteration_started_at) * 1000)
                        },
                    },
                )
                yield DoneResponse()
                break

            # 有工具调用，执行并继续
            log_transition(
                phase="executing_tools",
                message="Chat workflow executing detected tools",
                iteration_no=iteration,
                data={
                    "tool_call_count": len(tool_calls),
                    "tool_types": tool_types,
                },
            )
            yield ExecutingToolResponse(tool_type="mixed")

            # 添加助手响应到历史
            if self.chat_service:
                self.chat_service.add_assistant_message(full_content)

            # 执行工具调用
            results = []
            for tool_index, (tool_type, code) in enumerate(tool_calls, start=1):
                if context.interrupted:
                    break

                try:
                    if self.execution_service:
                        tool_log_context = dict(base_log_context)
                        tool_log_context["component"] = "chat_workflow"
                        tool_log_context["phase"] = "executing_tools"
                        tool_log_context["span_id"] = (
                            f"{base_log_context['span_id']}.iter{iteration}.tool{tool_index}"
                        )
                        result = self.execution_service.execute(
                            code,
                            is_python_code=(tool_type == "python"),
                            log_context=tool_log_context,
                        )
                        results.append(f"{tool_type.capitalize()} 执行结果:\n{result}")
                    else:
                        results.append(f"执行服务不可用")
                except Exception as e:
                    results.append(f"{tool_type.capitalize()} 执行失败: {str(e)}")

            if context.interrupted:
                log_transition(
                    phase="iteration_end",
                    message="Chat workflow interrupted during tool execution",
                    iteration_no=iteration,
                    legacy_event_type="iteration_end",
                    data={
                        "end_reason": "interrupted_during_tool_execution",
                        "timing": {
                            "duration_ms": int((time.monotonic() - iteration_started_at) * 1000)
                        },
                    },
                )
                yield DoneResponse()
                break

            # 添加执行反馈到历史
            feedback = "\n\n".join(results)
            log_transition(
                phase="writing_feedback",
                message="Chat workflow writing tool feedback",
                iteration_no=iteration,
                data={
                    "feedback_length": len(feedback),
                    "tool_result_count": len(results),
                },
            )
            if self.chat_service:
                self.chat_service.add_user_message(f"容器执行反馈：\n{feedback}")

            # 重置内容，准备下一轮
            full_content = ""
            full_thinking = ""

            log_transition(
                phase="iteration_end",
                message="Chat workflow iteration completed",
                iteration_no=iteration,
                legacy_event_type="iteration_end",
                data={
                    "end_reason": "tools_executed",
                    "tool_call_count": len(tool_calls),
                    "tool_result_count": len(results),
                    "timing": {
                        "duration_ms": int((time.monotonic() - iteration_started_at) * 1000)
                    },
                },
            )

        # 更新工作内存
        if iteration >= self.max_iterations:
            log_transition(
                phase="max_iterations",
                message="Reached max chat workflow iterations",
                level="warning",
                legacy_event_type="max_iterations_warning",
                data={
                    "iteration": iteration,
                    "max_iterations": self.max_iterations,
                },
            )
            yield ErrorResponse(
                content="达到最大迭代次数，可能存在无限循环",
                code="MAX_ITERATIONS",
            )

    def _extract_tool_calls(self, content: str) -> list[tuple[str, str]]:
        """从内容中提取工具调用

        Args:
            content: LLM 响应内容

        Returns:
            (工具类型, 代码) 列表
        """
        tool_calls = []

        # 提取 Python 代码
        python_codes = re.findall(r"```python\s*\n?(.*?)\s*```", content, re.DOTALL)
        for code in python_codes:
            tool_calls.append(("python", code.strip()))

        # 提取 Bash 命令
        bash_commands = re.findall(r"```bash\s*\n?(.*?)\s*```", content, re.DOTALL)
        for cmd in bash_commands:
            tool_calls.append(("bash", cmd.strip()))

        return tool_calls


__all__ = ["ChatWorkflow"]
