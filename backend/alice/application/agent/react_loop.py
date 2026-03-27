"""
ReAct 循环引擎

实现 ReAct (Reasoning + Acting) 模式的循环逻辑。
"""

import logging
from typing import Iterator, Optional, Callable
from dataclasses import dataclass, field

from ..dto import (
    ApplicationResponse,
    RequestContext,
    WorkflowContext,
    StatusResponse,
    ThinkingResponse,
    ContentResponse,
    ExecutingToolResponse,
    DoneResponse,
    ErrorResponse,
    TokensResponse,
    StatusType,
)


logger = logging.getLogger(__name__)


@dataclass
class ReActConfig:
    """ReAct 循环配置

    Attributes:
        max_iterations: 最大迭代次数
        enable_thinking: 是否启用思考模式
        timeout_seconds: 超时时间（秒）
    """

    max_iterations: int = 10
    enable_thinking: bool = True
    timeout_seconds: int = 300


@dataclass
class ReActState:
    """ReAct 循环状态

    Attributes:
        iteration: 当前迭代次数
        phase: 当前阶段
        full_content: 累积的完整内容
        full_thinking: 累积的思考内容
        tool_calls_found: 是否找到工具调用
        interrupted: 是否被中断
    """

    iteration: int = 0
    phase: str = "idle"  # idle, thinking, acting, observing, done
    full_content: str = ""
    full_thinking: str = ""
    tool_calls_found: bool = False
    interrupted: bool = False

    def reset(self) -> None:
        """重置状态"""
        self.iteration = 0
        self.phase = "idle"
        self.full_content = ""
        self.full_thinking = ""
        self.tool_calls_found = False
        self.interrupted = False


class ReActLoop:
    """ReAct 循环引擎

    实现推理-行动循环：
    1. Reasoning: LLM 生成思考和响应
    2. Acting: 检测并执行工具调用
    3. Observing: 将执行结果反馈给 LLM
    4. 重复直到无工具调用或达到最大迭代次数
    """

    def __init__(
        self,
        config: Optional[ReActConfig] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        on_content: Optional[Callable[[str], None]] = None,
    ):
        """初始化 ReAct 循环

        Args:
            config: 循环配置
            on_thinking: 思考内容回调
            on_content: 正文内容回调
        """
        self.config = config or ReActConfig()
        self._state = ReActState()
        self._on_thinking = on_thinking
        self._on_content = on_content

    @property
    def state(self) -> ReActState:
        """获取当前状态"""
        return self._state

    def reset(self) -> None:
        """重置循环状态"""
        self._state.reset()

    def should_continue(self) -> bool:
        """判断是否应该继续循环

        Returns:
            是否继续
        """
        if self._state.interrupted:
            return False
        if self._state.iteration >= self.config.max_iterations:
            return False
        return True

    def start_iteration(self) -> None:
        """开始新迭代"""
        self._state.iteration += 1
        self._state.phase = "thinking"
        logger.debug(f"ReAct 迭代 #{self._state.iteration}")

    def transition_to_acting(self) -> None:
        """转换到行动阶段"""
        self._state.phase = "acting"

    def transition_to_observing(self) -> None:
        """转换到观察阶段"""
        self._state.phase = "observing"

    def transition_to_done(self) -> None:
        """转换到完成阶段"""
        self._state.phase = "done"

    def interrupt(self) -> None:
        """中断循环"""
        self._state.interrupted = True
        self._state.phase = "done"
        logger.info("ReAct 循环被中断")

    def emit_thinking(self, content: str) -> Iterator[ApplicationResponse]:
        """发送思考内容

        Args:
            content: 思考内容

        Yields:
            思考响应
        """
        self._state.full_thinking += content
        if self._on_thinking:
            self._on_thinking(content)
        yield ThinkingResponse(content=content)

    def emit_content(self, content: str) -> Iterator[ApplicationResponse]:
        """发送正文内容

        Args:
            content: 正文内容

        Yields:
            正文响应
        """
        self._state.full_content += content
        if self._on_content:
            self._on_content(content)
        yield ContentResponse(content=content)

    def emit_tokens(
        self, total: int, prompt: int, completion: int
    ) -> Iterator[ApplicationResponse]:
        """发送 Token 统计

        Args:
            total: 总 token 数
            prompt: 输入 token 数
            completion: 输出 token 数

        Yields:
            Token 响应
        """
        yield TokensResponse(total=total, prompt=prompt, completion=completion)

    def emit_status(self, status: StatusType) -> Iterator[ApplicationResponse]:
        """发送状态更新

        Args:
            status: 状态类型

        Yields:
            状态响应
        """
        yield StatusResponse(status=status)

    def emit_executing_tool(
        self, tool_type: str
    ) -> Iterator[ApplicationResponse]:
        """发送工具执行通知

        Args:
            tool_type: 工具类型

        Yields:
            执行工具响应
        """
        yield ExecutingToolResponse(tool_type=tool_type)

    def emit_done(self) -> Iterator[ApplicationResponse]:
        """发送完成信号

        Yields:
            完成响应
        """
        yield DoneResponse()

    def emit_error(self, content: str, code: str = "") -> Iterator[ApplicationResponse]:
        """发送错误

        Args:
            content: 错误内容
            code: 错误代码

        Yields:
            错误响应
        """
        yield ErrorResponse(content=content, code=code)

    def get_result_summary(self) -> dict:
        """获取循环结果摘要

        Returns:
            结果摘要字典
        """
        return {
            "iterations": self._state.iteration,
            "content_length": len(self._state.full_content),
            "thinking_length": len(self._state.full_thinking),
            "interrupted": self._state.interrupted,
            "max_iterations_reached": self._state.iteration >= self.config.max_iterations,
        }


__all__ = [
    "ReActLoop",
    "ReActConfig",
    "ReActState",
]
