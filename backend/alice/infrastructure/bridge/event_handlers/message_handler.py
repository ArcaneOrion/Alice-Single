"""
Message Handler

处理来自前端的消息，协调 Agent 进行响应。
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from ..protocol.messages import INTERRUPT_SIGNAL

if TYPE_CHECKING:
    from ..server import BridgeServer


logger = logging.getLogger(__name__)


def _handler_log_extra(
    event_type: str,
    *,
    data: Optional[dict[str, Any]] = None,
    error: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """构造 MessageHandler 结构化日志字段。"""
    payload: dict[str, Any] = {
        "event_type": event_type,
        "log_category": "bridge.message_handler",
        "context": {
            "component": "bridge_message_handler",
        },
        "data": data or {},
    }
    if error is not None:
        payload["error"] = error
    return payload


def _summarize_text(text: str, limit: int = 120) -> str:
    """生成可观测日志摘要。"""
    cleaned = text.replace("\n", "\\n")
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit]}..."


class MessageHandler:
    """
    消息处理器。

    负责处理来自前端的消息并协调 Agent 生成响应。

    Args:
        server: BridgeServer 实例
    """

    def __init__(self, server: "BridgeServer"):
        self.server = server
        self._processing: bool = False

    def handle_input(self, user_input: str) -> None:
        """
        处理用户输入。

        Args:
            user_input: 用户输入字符串
        """
        if not user_input or user_input == INTERRUPT_SIGNAL:
            return

        logger.info(
            "TUI input received",
            extra=_handler_log_extra(
                "bridge.message_received",
                data={
                    "direction": "frontend->backend",
                    "message_type": "user_input",
                    "message_length": len(user_input),
                    "message_summary": _summarize_text(user_input),
                },
            ),
        )

        # 通知状态变更
        self.server.send_status("thinking")

        # 获取 Agent 实例
        agent = self.server.agent
        if agent is None:
            logger.error(
                "Agent not initialized",
                extra=_handler_log_extra(
                    "bridge.error",
                    data={"phase": "handle_input"},
                    error={
                        "type": "RuntimeError",
                        "message": "Agent not initialized",
                    },
                ),
            )
            self.server.send_error("Agent not initialized")
            return

        try:
            # 添加用户消息到对话历史
            agent.messages.append({"role": "user", "content": user_input})

            # 进入处理循环（支持工具调用迭代）
            self._processing = True
            self._process_response_loop(agent)

        except Exception as e:
            logger.error(
                "Error while processing user input",
                exc_info=True,
                extra=_handler_log_extra(
                    "bridge.error",
                    data={
                        "phase": "handle_input",
                        "input_length": len(user_input),
                    },
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                    },
                ),
            )
            self.server.send_error(f"Error processing input: {str(e)}")
        finally:
            self._processing = False
            self.server.send_status("done")

    def _process_response_loop(self, agent) -> None:
        """
        处理响应循环（支持工具调用迭代）。

        Args:
            agent: AliceAgent 实例
        """
        while True:
            # 检查中断状态
            if agent.interrupted:
                logger.info(
                    "Interrupted before next response step",
                    extra=_handler_log_extra(
                        "bridge.interrupt",
                        data={"phase": "response_loop.pre_llm"},
                    ),
                )
                agent.interrupted = False
                self.server.send_status("done")
                break

            # 执行 LLM 请求
            response_data = self._execute_llm_request(agent)

            if response_data is None:
                # 被中断
                break

            full_content, thinking_content = response_data

            # 检查工具调用
            tool_calls = self._detect_tool_calls(full_content)

            # 更新工作记忆
            user_input = agent.messages[-2]["content"] if len(agent.messages) >= 2 else ""
            agent._update_working_memory(user_input, thinking_content, full_content)

            # 检查中断状态
            if agent.interrupted:
                logger.info(
                    "Interrupted after LLM response",
                    extra=_handler_log_extra(
                        "bridge.interrupt",
                        data={"phase": "response_loop.post_llm"},
                    ),
                )
                agent.interrupted = False
                self.server.send_status("done")
                break

            if not tool_calls:
                # 无工具调用，结束对话
                logger.info(
                    "Model output returned without tool calls",
                    extra=_handler_log_extra(
                        "bridge.message_sent",
                        data={
                            "direction": "backend->frontend",
                            "message_type": "model_output",
                            "content_length": len(full_content),
                            "thinking_length": len(thinking_content),
                            "message_summary": _summarize_text(full_content),
                            "tool_calls_detected": 0,
                        },
                    ),
                )
                agent.messages.append({"role": "assistant", "content": full_content})
                self.server.send_status("done")
                break

            # 有工具调用，执行并继续
            agent.messages.append({"role": "assistant", "content": full_content})

            self.server.send_status("executing_tool")
            feedback = self._execute_tool_calls(agent, tool_calls)

            if agent.interrupted:
                logger.info(
                    "Interrupted during tool execution",
                    extra=_handler_log_extra(
                        "bridge.interrupt",
                        data={"phase": "tool_execution"},
                    ),
                )
                agent.interrupted = False
                self.server.send_status("done")
                break

            # 添加反馈到对话历史
            agent.messages.append({
                "role": "user",
                "content": f"容器执行反馈：\n{feedback}"
            })
            agent._refresh_context()

    def _execute_llm_request(self, agent) -> Optional[tuple[str, str]]:
        """
        执行 LLM 请求并流式输出。

        Args:
            agent: AliceAgent 实例

        Returns:
            Optional[tuple[str, str]]: (完整内容, 思考内容)，被中断时返回 None
        """
        extra_body = {"enable_thinking": True}
        response = agent._create_chat_completion(
            model=agent.model_name,
            messages=agent.messages,
            stream=True,
            extra_body=extra_body
        )

        full_content = ""
        thinking_content = ""
        stream_mgr = self.server.stream_manager_class()
        usage = None

        logger.info("开始流式请求 (chat.completions.create)...")

        for chunk in response:
            # 实时检查中断信号
            while self.server.transport.has_pending_input():
                msg = self.server.transport.get_input(block=False)
                if msg == INTERRUPT_SIGNAL:
                    logger.info(
                        "Interrupt signal detected while streaming",
                        extra=_handler_log_extra(
                            "bridge.interrupt",
                            data={"phase": "llm_streaming"},
                        ),
                    )
                    agent.interrupted = True

            if agent.interrupted:
                break

            # 获取 Token 使用情况
            if hasattr(chunk, 'usage') and chunk.usage:
                usage = chunk.usage
                self.server.send_tokens(
                    total=usage.total_tokens,
                    prompt=usage.prompt_tokens,
                    completion=usage.completion_tokens
                )

            if chunk.choices:
                choice = chunk.choices[0]
                delta = getattr(choice, 'delta', None) or choice

                # 极度兼容的读取函数
                def get_val(obj, names):
                    for name in names:
                        res = getattr(obj, name, None)
                        if res:
                            return res
                        if isinstance(obj, dict):
                            res = obj.get(name)
                            if res:
                                return res
                        if hasattr(obj, 'model_extra') and obj.model_extra:
                            res = obj.model_extra.get(name)
                            if res:
                                return res
                    return ""

                # 扩充字段名变体
                think_names = [
                    'reasoning_content', 'reasoningContent', 'reasoning',
                    'thought', 'thought_content', 'thoughtContent'
                ]
                t_chunk = get_val(delta, think_names)
                if not t_chunk:
                    t_chunk = get_val(choice, think_names)

                c_chunk = get_val(delta, ['content'])

                if t_chunk:
                    thinking_content += t_chunk
                    self.server.send_thinking(t_chunk)

                if c_chunk:
                    full_content += c_chunk
                    # 通过流管理器处理内容块
                    msgs = stream_mgr.process_chunk(c_chunk)
                    for msg in msgs:
                        self.server.send_raw_message(msg)

        # 强制冲刷管理器缓冲区
        final_msgs = stream_mgr.flush()
        if final_msgs:
            logger.info(
                "StreamManager flush completed",
                extra=_handler_log_extra(
                    "bridge.message_sent",
                    data={
                        "direction": "backend->frontend",
                        "message_type": "stream_flush",
                        "chunk_count": len(final_msgs),
                    },
                ),
            )
            for msg in final_msgs:
                self.server.send_raw_message(msg)

        if agent.interrupted:
            logger.info(
                "LLM request interrupted before completion",
                extra=_handler_log_extra(
                    "bridge.interrupt",
                    data={"phase": "llm_request"},
                ),
            )
            return None

        logger.info(
            "LLM request completed",
            extra=_handler_log_extra(
                "bridge.message_sent",
                data={
                    "direction": "backend->frontend",
                    "message_type": "model_output",
                    "content_length": len(full_content),
                    "thinking_length": len(thinking_content),
                    "message_summary": _summarize_text(full_content),
                },
            ),
        )
        return full_content, thinking_content

    def _detect_tool_calls(self, content: str) -> dict[str, list[str]]:
        """
        检测内容中的工具调用。

        Args:
            content: LLM 响应内容

        Returns:
            dict[str, list[str]]: {"python": [...], "bash": [...]}
        """
        import re

        python_codes = re.findall(
            r'```python\s*\n?(.*?)\s*```',
            content,
            re.DOTALL
        )
        bash_commands = re.findall(
            r'```bash\s*\n?(.*?)\s*```',
            content,
            re.DOTALL
        )

        return {
            "python": python_codes,
            "bash": bash_commands
        }

    def _execute_tool_calls(
        self,
        agent,
        tool_calls: dict[str, list[str]]
    ) -> str:
        """
        执行工具调用。

        Args:
            agent: AliceAgent 实例
            tool_calls: 工具调用字典

        Returns:
            str: 执行结果反馈
        """
        results = []

        for code in tool_calls.get("python", []):
            if agent.interrupted:
                break
            res = agent.execute_command(code.strip(), is_python_code=True)
            results.append(f"Python 代码执行结果:\n{res}")

        for cmd in tool_calls.get("bash", []):
            if agent.interrupted:
                break
            res = agent.execute_command(cmd.strip(), is_python_code=False)
            results.append(f"Shell 命令 `{cmd.strip()}` 的结果:\n{res}")

        return "\n\n".join(results)

    @property
    def is_processing(self) -> bool:
        """检查是否正在处理消息。"""
        return self._processing


__all__ = [
    "MessageHandler",
]
