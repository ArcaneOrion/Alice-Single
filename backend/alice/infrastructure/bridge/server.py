"""
Bridge Server

兼容桥接服务器，协调传输层、协议层和事件处理器。
当前职责是作为 legacy bridge 协议的兼容入口薄壳。
"""

import json
import logging
import os
import traceback
from typing import TYPE_CHECKING, Any, Optional

from .legacy_compatibility_serializer import (
    serialize_error_message,
    serialize_status_message,
    serialize_thinking_message,
    serialize_content_message,
    serialize_tokens_message,
)
from .protocol import (
    StatusType,
    OutputMessage,
    INTERRUPT_SIGNAL,
)
from .transport import StdioTransport, TransportProtocol
from .event_handlers import MessageHandler, InterruptHandler

if TYPE_CHECKING:
    from agent import AliceAgent


logger = logging.getLogger(__name__)


def _bridge_log_extra(
    event_type: str,
    *,
    data: Optional[dict] = None,
    context: Optional[dict] = None,
    error: Optional[dict] = None,
) -> dict:
    """构造 bridge 结构化日志字段"""
    merged_context = {
        "component": "bridge_server",
        "task_id": "",
        "request_id": "",
        "session_id": "",
        **(context or {}),
    }
    payload = {
        "event_type": event_type,
        "log_category": "bridge.server",
        "context": merged_context,
        "data": data or {},
    }
    if error is not None:
        payload["error"] = error
    return payload


def _summarize_text(text: str, limit: int = 120) -> str:
    """生成日志摘要，避免输出完整内容。"""
    cleaned = text.replace("\n", "\\n")
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit]}..."


def _summarize_frontend_message(message: str) -> dict[str, Any]:
    """提取前端输入消息元信息。"""
    message_type = "interrupt" if message == INTERRUPT_SIGNAL else "user_input"
    return {
        "direction": "frontend->backend",
        "message_type": message_type,
        "message_length": len(message),
        "message_summary": _summarize_text(message),
    }


def _normalize_output_message(message: Any) -> OutputMessage | Any:
    """将 bridge 输出统一收口到 legacy compatibility serializer。"""
    if not isinstance(message, dict):
        return message

    raw_type = message.get("type", "")
    message_type = getattr(raw_type, "value", raw_type)

    if message_type == "status":
        raw_status = message.get("content", "")
        status = getattr(raw_status, "value", raw_status)
        return serialize_status_message(str(status))
    if message_type == "thinking":
        return serialize_thinking_message(str(message.get("content", "")))
    if message_type == "content":
        return serialize_content_message(str(message.get("content", "")))
    if message_type == "tokens":
        return serialize_tokens_message(
            total=int(message.get("total", 0) or 0),
            prompt=int(message.get("prompt", 0) or 0),
            completion=int(message.get("completion", 0) or 0),
        )
    if message_type == "error":
        return serialize_error_message(
            content=str(message.get("content", "")),
            code=str(message.get("code", "") or ""),
        )

    return message


def _summarize_output_message(message: OutputMessage) -> dict[str, Any]:
    """提取输出消息元信息。"""
    normalized_message = _normalize_output_message(message)
    msg_type = "unknown"
    content_summary = ""
    content_length = 0

    if isinstance(normalized_message, dict):
        raw_type = normalized_message.get("type", "unknown")
        msg_type = str(getattr(raw_type, "value", raw_type))
        content = normalized_message.get("content")
        if isinstance(content, str):
            content_length = len(content)
            content_summary = _summarize_text(content)

    try:
        payload_length = len(json.dumps(normalized_message, ensure_ascii=False))
    except TypeError:
        payload_length = len(str(normalized_message))

    return {
        "direction": "backend->frontend",
        "message_type": msg_type,
        "payload_length": payload_length,
        "content_length": content_length,
        "message_summary": content_summary,
    }


def _write_stdout_message(message: OutputMessage) -> None:
    """直接向 stdout 输出归一化后的 legacy 协议消息。"""
    print(json.dumps(_normalize_output_message(message), ensure_ascii=False), flush=True)


class BridgeServer:
    """
    兼容桥接服务器。

    负责协调 TUI (Rust) 与 Agent (Python) 之间的通信，并将应用层响应
    归一化为冻结的 legacy bridge 协议输出。

    架构：
    ```
    Rust TUI <--(JSON stdin/stdout)--> BridgeServer --> AliceAgent
    ```

    Args:
        agent: AliceAgent 实例
        transport: 传输层实例（默认使用 StdioTransport）
    """

    def __init__(
        self,
        agent: Optional["AliceAgent"] = None,
        transport: Optional[TransportProtocol] = None,
    ):
        self.agent = agent
        self.transport = transport or StdioTransport()
        self._running = False

        # 事件处理器
        self.message_handler = MessageHandler(self)
        self.interrupt_handler = InterruptHandler(self)

    def start(self) -> None:
        """
        启动桥接服务器。

        初始化传输层并发送就绪信号。
        """
        if self._running:
            logger.warning(
                "BridgeServer already running",
                extra=_bridge_log_extra(
                    "system.start",
                    data={"phase": "bridge_server.start", "reason": "already_running"},
                ),
            )
            return

        logger.info(
            "Bridge server starting",
            extra=_bridge_log_extra(
                "system.start",
                data={
                    "phase": "bridge_server.start",
                    "transport": type(self.transport).__name__,
                },
            ),
        )

        # 设置传输层回调
        self.transport.set_message_callback(self._on_message_received)
        self.transport.set_eof_callback(self._on_eof_received)

        # 启动传输层
        self.transport.start()

        self._running = True

        # 发送就绪信号
        self.send_status(StatusType.READY)
        logger.info(
            "Bridge server ready",
            extra=_bridge_log_extra(
                "system.start",
                data={"phase": "bridge_server.ready"},
            ),
        )

    def stop(self) -> None:
        """停止桥接服务器。"""
        if not self._running:
            return

        self._running = False
        self.transport.stop()
        logger.info(
            "Bridge server stopped",
            extra=_bridge_log_extra(
                "system.shutdown",
                data={"phase": "bridge_server.stop"},
            ),
        )

    def run(self) -> None:
        """
        运行主循环。

        阻塞直到收到 EOF 信号。
        """
        self.start()

        try:
            while self._running and self.transport.is_running():
                import time
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info(
                "Bridge server interrupted by keyboard",
                extra=_bridge_log_extra(
                    "bridge.interrupt",
                    data={"phase": "run_loop", "source": "keyboard_interrupt"},
                ),
            )
        finally:
            self.stop()

    # ========== 消息发送方法 ==========

    def send_message(self, message: OutputMessage) -> None:
        """
        发送消息到前端。

        Args:
            message: 消息字典
        """
        self._send_message_with_logging(message, raw=False)

    def send_raw_message(self, message: OutputMessage) -> None:
        """
        发送消息到前端，并保留 raw 路径日志标记。

        该方法仍会经过 legacy compatibility serializer，不能绕过兼容层。

        Args:
            message: 消息字典
        """
        self._send_message_with_logging(message, raw=True)

    def _send_message_with_logging(self, message: OutputMessage, *, raw: bool) -> None:
        """发送消息并记录结构化可观测日志。"""
        normalized_message = _normalize_output_message(message)
        message_data = _summarize_output_message(normalized_message)
        message_data["raw"] = raw
        message_data["normalized"] = normalized_message != message
        logger.info(
            "Bridge message sent",
            extra=_bridge_log_extra("bridge.message_sent", data=message_data),
        )
        try:
            self.transport.send_message(normalized_message)
        except Exception as e:
            logger.error(
                "Bridge transport send failed",
                exc_info=True,
                extra=_bridge_log_extra(
                    "bridge.error",
                    data={
                        "phase": "transport.send",
                        **message_data,
                    },
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                    },
                ),
            )
            raise

    def send_status(self, status: StatusType | str) -> None:
        """
        发送状态消息。

        Args:
            status: 状态值
        """
        if isinstance(status, str):
            status = StatusType(status)
        self.send_message(serialize_status_message(status.value))

    def send_thinking(self, content: str) -> None:
        """
        发送思考消息。

        Args:
            content: 思考内容
        """
        self.send_message(serialize_thinking_message(content))

    def send_content(self, content: str) -> None:
        """
        发送正文消息。

        Args:
            content: 正文内容
        """
        self.send_message(serialize_content_message(content))

    def send_tokens(self, total: int, prompt: int, completion: int) -> None:
        """
        发送 Token 统计消息。

        Args:
            total: 总 token 数
            prompt: 提示词 token 数
            completion: 补全 token 数
        """
        self.send_message(serialize_tokens_message(total=total, prompt=prompt, completion=completion))

    def send_error(self, content: str, code: str = "") -> None:
        """
        发送错误消息。

        Args:
            content: 错误内容
            code: 错误代码
        """
        logger.error(
            "Bridge error emitted",
            extra=_bridge_log_extra(
                "bridge.error",
                data={
                    "phase": "send_error",
                    "code": code,
                    "content_length": len(content),
                    "content_summary": _summarize_text(content),
                },
            ),
        )
        self.send_message(serialize_error_message(content=content, code=code))

    # ========== 传输层回调 ==========

    def _on_message_received(self, message: str) -> None:
        """
        接收到消息时的回调。

        Args:
            message: 接收到的消息字符串
        """
        try:
            incoming_data = _summarize_frontend_message(message)
            logger.info(
                "Bridge message received",
                extra=_bridge_log_extra("bridge.message_received", data=incoming_data),
            )

            # 检查是否为中断信号
            if message == INTERRUPT_SIGNAL:
                logger.info(
                    "Bridge interrupt signal received",
                    extra=_bridge_log_extra(
                        "bridge.interrupt",
                        data={
                            "phase": "input_callback",
                            "source": "frontend_signal",
                            **incoming_data,
                        },
                    ),
                )
                self.interrupt_handler.check_interrupt()
                return

            # 处理用户输入
            if self.agent is not None:
                self.message_handler.handle_input(message)

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(
                "Bridge message handling failed",
                exc_info=True,
                extra=_bridge_log_extra(
                    "bridge.error",
                    context={
                        "message_preview": message[:120],
                    },
                    data={
                        "phase": "input_callback",
                        "message_length": len(message),
                    },
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": error_trace,
                    },
                ),
            )
            self.send_error(f"Error: {str(e)}")

    def _on_eof_received(self) -> None:
        """接收到 EOF 时的回调。"""
        logger.info(
            "Bridge EOF received",
            extra=_bridge_log_extra(
                "bridge.eof",
                data={"phase": "stdin_reader", "source": "transport"},
            ),
        )
        self._running = False

    # ========== 状态查询 ==========

    @property
    def is_running(self) -> bool:
        """检查服务器是否正在运行。"""
        return self._running

    @property
    def is_processing(self) -> bool:
        """检查是否正在处理消息。"""
        return self.message_handler.is_processing


def create_bridge_server(
    agent: Optional["AliceAgent"] = None,
) -> BridgeServer:
    """
    创建并配置桥接服务器。

    Args:
        agent: AliceAgent 实例

    Returns:
        BridgeServer: 配置好的服务器实例
    """
    return BridgeServer(agent=agent)


def main_with_agent(agent_class=None, **agent_kwargs) -> None:
    """
    使用 Agent 运行桥接服务器的主入口。

    这是 tui_bridge.py main() 函数的重构版本。

    Args:
        agent_class: Agent 类（默认为 AliceAgent）
        **agent_kwargs: Agent 初始化参数
    """
    import sys

    # 强制切换到脚本所在目录（根目录）
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.getcwd()

    # 动态导入 Agent
    if agent_class is None:
        # 添加项目根目录到路径
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from agent import AliceAgent
        agent_class = AliceAgent

    # 初始化 Agent
    try:
        agent = agent_class(**agent_kwargs)
    except Exception as e:
        error_msg = f"初始化失败: {traceback.format_exc()}"
        logger.error(
            "Bridge agent initialization failed",
            extra=_bridge_log_extra(
                "bridge.error",
                data={"phase": "initialization"},
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": error_msg,
                },
            ),
        )
        _write_stdout_message(
            serialize_error_message(content=f"Initialization failed: {str(e)}")
        )
        return

    # 创建并运行服务器
    server = create_bridge_server(agent=agent)

    logger.info(
        "Bridge runtime start",
        extra=_bridge_log_extra(
            "system.start",
            data={"phase": "bridge_runtime.run"},
        ),
    )
    try:
        server.run()
    except EOFError:
        logger.info(
            "Bridge EOFError received",
            extra=_bridge_log_extra(
                "bridge.eof",
                data={"phase": "bridge_runtime.run", "source": "EOFError"},
            ),
        )
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(
            "Bridge runtime error",
            extra=_bridge_log_extra(
                "bridge.error",
                data={"phase": "run"},
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": error_trace,
                },
            ),
        )
        _write_stdout_message(
            serialize_error_message(content=f"Runtime Error: {str(e)}. 请查看日志输出。")
        )
    finally:
        logger.info(
            "Bridge runtime shutdown",
            extra=_bridge_log_extra(
                "system.shutdown",
                data={"phase": "bridge_runtime.exit"},
            ),
        )


__all__ = [
    "BridgeServer",
    "create_bridge_server",
    "main_with_agent",
]
