"""
Stdio Transport Implementation

使用 stdin/stdout 实现传输层，用于与 Rust TUI 通信。
"""

import io
import json
import logging
import queue
import sys
import threading
from typing import Any, Optional

from .transport_trait import (
    TransportProtocol,
    TransportError,
    MessageCallback,
    EofCallback,
)
from ..protocol.messages import OutputMessage, INTERRUPT_SIGNAL

logger = logging.getLogger(__name__)


def _transport_log_extra(
    event_type: str,
    *,
    data: Optional[dict[str, Any]] = None,
    error: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """构造 stdio transport 结构化日志字段。"""
    payload: dict[str, Any] = {
        "event_type": event_type,
        "log_category": "bridge.transport.stdio",
        "context": {
            "component": "bridge_stdio_transport",
        },
        "data": data or {},
    }
    if error is not None:
        payload["error"] = error
    return payload


def _summarize_text(text: str, limit: int = 120) -> str:
    """生成日志摘要，避免打印完整输入。"""
    cleaned = text.replace("\n", "\\n")
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit]}..."


class StdioTransport(TransportProtocol):
    """
    stdin/stdout 传输层实现。

    特性：
    - 异步读取 stdin，避免阻塞主线程
    - 线程安全的消息队列
    - 支持 UTF-8 编码
    - 行缓冲模式
    """

    def __init__(
        self,
        stdin_stream: Optional[io.TextIOBase] = None,
        stdout_stream: Optional[io.TextIOBase] = None,
        enable_utf8: bool = True,
    ):
        """
        初始化 Stdio 传输层。

        Args:
            stdin_stream: 输入流，默认为 sys.stdin
            stdout_stream: 输出流，默认为 sys.stdout
            enable_utf8: 是否强制 UTF-8 编码
        """
        self._stdin = stdin_stream or sys.stdin
        self._stdout = stdout_stream or sys.stdout
        self._input_queue: queue.Queue[str | None] = queue.Queue()
        self._running = False
        self._reader_thread: Optional[threading.Thread] = None
        self._message_callback: Optional[MessageCallback] = None
        self._eof_callback: Optional[EofCallback] = None

        # 强制 UTF-8 编码
        if enable_utf8 and hasattr(self._stdout, 'buffer'):
            self._stdout = io.TextIOWrapper(
                self._stdout.buffer,
                encoding='utf-8',
                line_buffering=True
            )

    def start(self) -> None:
        """启动传输层，创建异步读取线程。"""
        if self._running:
            logger.warning(
                "StdioTransport already running",
                extra=_transport_log_extra(
                    "system.start",
                    data={"phase": "transport.start", "reason": "already_running"},
                ),
            )
            return

        self._running = True
        self._reader_thread = threading.Thread(
            target=self._stdin_reader,
            daemon=True,
            name="StdioReader"
        )
        self._reader_thread.start()
        logger.info(
            "StdioTransport started",
            extra=_transport_log_extra(
                "system.start",
                data={
                    "phase": "transport.start",
                    "reader_thread": self._reader_thread.name,
                },
            ),
        )

    def stop(self) -> None:
        """停止传输层。"""
        if not self._running:
            return

        self._running = False
        if self._reader_thread and self._reader_thread.is_alive():
            # 等待线程结束（最多 1 秒）
            self._reader_thread.join(timeout=1.0)
        logger.info(
            "StdioTransport stopped",
            extra=_transport_log_extra(
                "system.shutdown",
                data={"phase": "transport.stop"},
            ),
        )

    def send_message(self, message: OutputMessage) -> None:
        """
        发送 JSON 消息到 stdout。

        Args:
            message: 要发送的消息字典
        """
        json_str = json.dumps(message, ensure_ascii=False)
        self.send_raw(json_str)

    def send_raw(self, data: str) -> None:
        """
        发送原始字符串到 stdout。

        Args:
            data: 要发送的字符串

        Raises:
            TransportError: 当写入失败时
        """
        try:
            print(data, flush=True, file=self._stdout)
            logger.info(
                "stdout write success",
                extra=_transport_log_extra(
                    "bridge.message_sent",
                    data={
                        "direction": "backend->frontend",
                        "payload_length": len(data),
                        "message_summary": _summarize_text(data),
                    },
                ),
            )
        except Exception as e:
            logger.error(
                "stdout write failed",
                extra=_transport_log_extra(
                    "bridge.error",
                    data={
                        "phase": "stdout.write",
                        "payload_length": len(data),
                    },
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                    },
                ),
            )
            raise TransportError(f"Failed to write to stdout: {e}") from e

    def set_message_callback(self, callback: Optional[MessageCallback]) -> None:
        """
        设置消息接收回调。

        Args:
            callback: 接收到输入时的回调函数
        """
        self._message_callback = callback

    def set_eof_callback(self, callback: Optional[EofCallback]) -> None:
        """
        设置 EOF 回调。

        Args:
            callback: 接收到 EOF 时的回调函数
        """
        self._eof_callback = callback

    def is_running(self) -> bool:
        """检查传输层是否正在运行。"""
        return self._running

    def get_input(self, block: bool = True, timeout: Optional[float] = None) -> Optional[str]:
        """
        从队列获取输入。

        Args:
            block: 是否阻塞等待
            timeout: 超时时间（秒）

        Returns:
            输入字符串，None 表示 EOF
        """
        try:
            return self._input_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def has_pending_input(self) -> bool:
        """检查是否有待处理的输入。"""
        return not self._input_queue.empty()

    def drain_pending_interrupts(self) -> bool:
        """
        排空待处理的中断信号。

        Returns:
            bool: 是否发现了中断信号
        """
        found_interrupt = False
        while not self._input_queue.empty():
            try:
                msg = self._input_queue.get_nowait()
                if msg == INTERRUPT_SIGNAL:
                    found_interrupt = True
            except queue.Empty:
                break
        return found_interrupt

    def _stdin_reader(self) -> None:
        """
        stdin 读取线程函数。

        持续读取 stdin 并将输入放入队列。
        """
        logger.info(
            "stdin reader thread started",
            extra=_transport_log_extra(
                "system.start",
                data={"phase": "stdin_reader.start"},
            ),
        )

        while self._running:
            try:
                line = self._stdin.readline()
                if not line:
                    # EOF
                    logger.info(
                        "stdin EOF received",
                        extra=_transport_log_extra(
                            "bridge.eof",
                            data={
                                "phase": "stdin_reader.read",
                                "source": "stdin",
                            },
                        ),
                    )
                    self._input_queue.put(None)
                    if self._eof_callback:
                        self._eof_callback()
                    break

                stripped = line.strip()
                self._input_queue.put(stripped)
                logger.info(
                    "stdin message received",
                    extra=_transport_log_extra(
                        "bridge.message_received",
                        data={
                            "direction": "frontend->backend",
                            "message_type": (
                                "interrupt" if stripped == INTERRUPT_SIGNAL else "user_input"
                            ),
                            "message_length": len(stripped),
                            "message_summary": _summarize_text(stripped),
                        },
                    ),
                )

                # 调用消息回调
                if self._message_callback and stripped:
                    try:
                        self._message_callback(stripped)
                    except Exception as e:
                        logger.error(
                            "Error in message callback",
                            exc_info=True,
                            extra=_transport_log_extra(
                                "bridge.error",
                                data={
                                    "phase": "stdin_reader.callback",
                                    "message_length": len(stripped),
                                },
                                error={
                                    "type": type(e).__name__,
                                    "message": str(e),
                                },
                            ),
                        )

            except Exception as e:
                logger.error(
                    "Error reading stdin",
                    exc_info=True,
                    extra=_transport_log_extra(
                        "bridge.error",
                        data={"phase": "stdin_reader.read"},
                        error={
                            "type": type(e).__name__,
                            "message": str(e),
                        },
                    ),
                )
                self._input_queue.put(None)
                if self._eof_callback:
                    self._eof_callback()
                break

        logger.info(
            "stdin reader thread stopped",
            extra=_transport_log_extra(
                "system.shutdown",
                data={"phase": "stdin_reader.stop"},
            ),
        )


__all__ = [
    "StdioTransport",
]
