"""
Bridge Server

桥接服务器，协调传输层、协议层和事件处理器。
这是 Bridge Infrastructure 模块的核心组件。
"""

import logging
import os
import traceback
from typing import TYPE_CHECKING, Optional, Type

from .protocol import (
    StatusType,
    OutputMessage,
    INTERRUPT_SIGNAL,
)
from .transport import StdioTransport
from .stream_manager import StreamManager
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


# 默认的 StreamManager 类（允许外部注入替代实现）
DefaultStreamManagerClass = StreamManager


class BridgeServer:
    """
    桥接服务器。

    负责协调 TUI (Rust) 与 Agent (Python) 之间的通信。

    架构：
    ```
    Rust TUI <--(JSON stdin/stdout)--> BridgeServer --> AliceAgent
    ```

    Args:
        agent: AliceAgent 实例
        transport: 传输层实例（默认使用 StdioTransport）
        stream_manager_class: StreamManager 类（允许依赖注入）
    """

    def __init__(
        self,
        agent: Optional["AliceAgent"] = None,
        transport: Optional[StdioTransport] = None,
        stream_manager_class: Type[StreamManager] = DefaultStreamManagerClass,
    ):
        self.agent = agent
        self.transport = transport or StdioTransport()
        self.stream_manager_class = stream_manager_class
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
                    "bridge_already_running",
                    data={"reason": "already_running"},
                ),
            )
            return

        logger.info(
            "Bridge server starting",
            extra=_bridge_log_extra(
                "bridge_start",
                data={"transport": type(self.transport).__name__},
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
            extra=_bridge_log_extra("bridge_ready"),
        )

    def stop(self) -> None:
        """停止桥接服务器。"""
        if not self._running:
            return

        self._running = False
        self.transport.stop()
        logger.info(
            "Bridge server stopped",
            extra=_bridge_log_extra("bridge_stop"),
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
                extra=_bridge_log_extra("bridge_interrupt"),
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
        self.transport.send_message(message)

    def send_raw_message(self, message: OutputMessage) -> None:
        """
        发送原始消息到前端（不经过编解码器）。

        Args:
            message: 消息字典
        """
        self.transport.send_message(message)

    def send_status(self, status: StatusType | str) -> None:
        """
        发送状态消息。

        Args:
            status: 状态值
        """
        if isinstance(status, str):
            status = StatusType(status)
        self.send_message({"type": "status", "content": status.value})

    def send_thinking(self, content: str) -> None:
        """
        发送思考消息。

        Args:
            content: 思考内容
        """
        self.send_message({"type": "thinking", "content": content})

    def send_content(self, content: str) -> None:
        """
        发送正文消息。

        Args:
            content: 正文内容
        """
        self.send_message({"type": "content", "content": content})

    def send_tokens(self, total: int, prompt: int, completion: int) -> None:
        """
        发送 Token 统计消息。

        Args:
            total: 总 token 数
            prompt: 提示词 token 数
            completion: 补全 token 数
        """
        self.send_message({
            "type": "tokens",
            "total": total,
            "prompt": prompt,
            "completion": completion
        })

    def send_error(self, content: str, code: str = "") -> None:
        """
        发送错误消息。

        Args:
            content: 错误内容
            code: 错误代码
        """
        self.send_message({"type": "error", "content": content, "code": code})

    # ========== 传输层回调 ==========

    def _on_message_received(self, message: str) -> None:
        """
        接收到消息时的回调。

        Args:
            message: 接收到的消息字符串
        """
        try:
            # 检查是否为中断信号
            if message == INTERRUPT_SIGNAL:
                logger.info(
                    "Bridge interrupt signal received",
                    extra=_bridge_log_extra("bridge_interrupt"),
                )
                self.interrupt_handler.check_interrupt()
                return

            # 处理用户输入
            if self.agent is not None:
                logger.info(
                    "Bridge message received",
                    extra=_bridge_log_extra(
                        "bridge_message_received",
                        data={"message_length": len(message)},
                    ),
                )
                self.message_handler.handle_input(message)

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(
                "Bridge message handling failed",
                exc_info=True,
                extra=_bridge_log_extra(
                    "bridge_message_error",
                    context={
                        "message_preview": message[:120],
                    },
                    data={
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
            extra=_bridge_log_extra("bridge_eof"),
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
    stream_manager_class: Type[StreamManager] = DefaultStreamManagerClass,
) -> BridgeServer:
    """
    创建并配置桥接服务器。

    Args:
        agent: AliceAgent 实例
        stream_manager_class: StreamManager 类

    Returns:
        BridgeServer: 配置好的服务器实例
    """
    return BridgeServer(
        agent=agent,
        stream_manager_class=stream_manager_class,
    )


def main_with_agent(agent_class=None, **agent_kwargs) -> None:
    """
    使用 Agent 运行桥接服务器的主入口。

    这是 tui_bridge.py main() 函数的重构版本。

    Args:
        agent_class: Agent 类（默认为 AliceAgent）
        **agent_kwargs: Agent 初始化参数
    """
    import sys
    import json

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
                "bridge_runtime_error",
                data={"phase": "initialization"},
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": error_msg,
                },
            ),
        )
        print(json.dumps({
            "type": "error",
            "content": f"Initialization failed: {str(e)}"
        }), flush=True)
        return

    # 创建并运行服务器
    server = create_bridge_server(agent=agent)

    try:
        server.run()
    except EOFError:
        logger.info(
            "Bridge EOFError received",
            extra=_bridge_log_extra("bridge_eof"),
        )
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(
            "Bridge runtime error",
            extra=_bridge_log_extra(
                "bridge_runtime_error",
                data={"phase": "run"},
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": error_trace,
                },
            ),
        )
        print(json.dumps({
            "type": "error",
            "content": f"Runtime Error: {str(e)}. 请查看日志输出。"
        }), flush=True)


__all__ = [
    "BridgeServer",
    "DefaultStreamManagerClass",
    "create_bridge_server",
    "main_with_agent",
]
