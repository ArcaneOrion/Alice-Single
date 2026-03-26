"""
聊天工作流

实现 ReAct 模式的聊天工作流：思考 -> 行动 -> 观察。
"""

import logging
import re
from typing import Iterator, Optional

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
    ResponseType,
    StatusType,
)
from backend.alice.domain.llm.parsers.stream_parser import StreamParser, StreamParserConfig
from backend.alice.domain.llm.models.stream_chunk import StreamChunk


logger = logging.getLogger(__name__)


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

        while iteration < self.max_iterations:
            iteration += 1

            if context.interrupted:
                logger.info("聊天工作流被中断")
                yield DoneResponse()
                break

            # 流式生成响应
            try:
                if self.chat_service:
                    response_iter = self.chat_service.provider.stream_chat(
                        self.chat_service.messages
                    )
                else:
                    yield ErrorResponse(content="Chat service not available", code="NO_SERVICE")
                    break
            except Exception as e:
                logger.error(f"聊天请求失败: {e}")
                yield ErrorResponse(content=f"Chat request failed: {str(e)}", code="CHAT_ERROR")
                break

            # 处理流式响应
            self.stream_parser.reset()
            usage = None

            for chunk in response_iter:
                if context.interrupted:
                    break

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
                yield DoneResponse()
                break

            # 检查工具调用
            tool_calls = self._extract_tool_calls(full_content)

            if not tool_calls:
                # 无工具调用，结束
                if self.chat_service:
                    self.chat_service.add_assistant_message(full_content)
                yield DoneResponse()
                break

            # 有工具调用，执行并继续
            yield ExecutingToolResponse(tool_type="mixed")

            # 添加助手响应到历史
            if self.chat_service:
                self.chat_service.add_assistant_message(full_content)

            # 执行工具调用
            results = []
            for tool_type, code in tool_calls:
                if context.interrupted:
                    break

                try:
                    if self.execution_service:
                        result = self.execution_service.execute(
                            code, is_python_code=(tool_type == "python")
                        )
                        results.append(f"{tool_type.capitalize()} 执行结果:\n{result}")
                    else:
                        results.append(f"执行服务不可用")
                except Exception as e:
                    results.append(f"{tool_type.capitalize()} 执行失败: {str(e)}")

            if context.interrupted:
                yield DoneResponse()
                break

            # 添加执行反馈到历史
            feedback = "\n\n".join(results)
            if self.chat_service:
                self.chat_service.add_user_message(f"容器执行反馈：\n{feedback}")

            # 重置内容，准备下一轮
            full_content = ""
            full_thinking = ""

        # 更新工作内存
        if iteration >= self.max_iterations:
            logger.warning(f"达到最大迭代次数 ({self.max_iterations})")
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
