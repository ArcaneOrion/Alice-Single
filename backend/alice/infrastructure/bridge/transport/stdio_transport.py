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
from typing import Optional, Callable

from .transport_trait import (
    TransportProtocol,
    TransportError,
    MessageCallback,
    EofCallback,
)
from ..protocol.messages import OutputMessage, INTERRUPT_SIGNAL

logger = logging.getLogger(__name__)


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
            logger.warning("StdioTransport already running")
            return

        self._running = True
        self._reader_thread = threading.Thread(
            target=self._stdin_reader,
            daemon=True,
            name="StdioReader"
        )
        self._reader_thread.start()
        logger.info("StdioTransport started")

    def stop(self) -> None:
        """停止传输层。"""
        if not self._running:
            return

        self._running = False
        if self._reader_thread and self._reader_thread.is_alive():
            # 等待线程结束（最多 1 秒）
            self._reader_thread.join(timeout=1.0)
        logger.info("StdioTransport stopped")

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
        except Exception as e:
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
        logger.debug("stdin reader thread started")

        while self._running:
            try:
                line = self._stdin.readline()
                if not line:
                    # EOF
                    logger.info("stdin EOF received")
                    self._input_queue.put(None)
                    if self._eof_callback:
                        self._eof_callback()
                    break

                stripped = line.strip()
                self._input_queue.put(stripped)

                # 调用消息回调
                if self._message_callback and stripped:
                    try:
                        self._message_callback(stripped)
                    except Exception as e:
                        logger.error(f"Error in message callback: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Error reading stdin: {e}", exc_info=True)
                self._input_queue.put(None)
                if self._eof_callback:
                    self._eof_callback()
                break

        logger.debug("stdin reader thread stopped")


__all__ = [
    "StdioTransport",
]
