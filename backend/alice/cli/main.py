"""
Alice CLI - 命令行入口

提供与 Rust TUI 交互的桥接层。
这是新的应用层入口，替代旧的 tui_bridge.py。
"""

import sys
import json
import io
import logging
import os
import threading
import queue
import traceback
from pathlib import Path

# 添加项目根目录到 Python 路径
# backend/alice/cli/main.py -> 向上4级到项目根目录
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def _prepare_process_environment() -> None:
    """仅在 CLI 真实运行时准备工作目录与 stdout。"""
    os.chdir(project_root)
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        sys.stdout = io.TextIOWrapper(buffer, encoding="utf-8", line_buffering=True)


from backend.alice.application.agent import AliceAgent
from backend.alice.cli.bootstrap import (
    configure_runtime_logging,
    create_agent_from_env,
    ensure_runtime_scaffold,
)
from backend.alice.infrastructure.bridge.legacy_compatibility_serializer import (
    response_to_dict,
    serialize_error_message,
    serialize_status_message,
)
from backend.alice.infrastructure.bridge.protocol.messages import INTERRUPT_SIGNAL

logger = logging.getLogger("AliceCLI")


def _print_legacy_message(message: dict) -> None:
    print(json.dumps(message), flush=True)



class TUIBridge:
    """TUI 桥接器

    处理与 Rust TUI 的通信。
    """

    def __init__(self):
        self.agent: AliceAgent | None = None
        self.input_queue = queue.Queue()
        self._running = False
        self._start_stdin_reader()

    def _start_stdin_reader(self):
        """启动 stdin 监听线程"""

        def stdin_reader():
            while True:
                try:
                    line = sys.stdin.readline()
                    if not line:
                        self.input_queue.put(None)
                        break
                    self.input_queue.put(line.strip())
                except Exception:
                    self.input_queue.put(None)
                    break

        threading.Thread(target=stdin_reader, daemon=True).start()

    def initialize(self) -> bool:
        """初始化 Agent"""
        try:
            ensure_runtime_scaffold(project_root=project_root)
            configure_runtime_logging(console_level="ERROR")
            self.agent = create_agent_from_env(project_root=project_root)
            logger.info("Alice Agent 初始化成功")
            return True

        except Exception as e:
            error_msg = f"初始化失败: {traceback.format_exc()}"
            logger.error(error_msg)
            self._send_error(f"Initialization failed: {str(e)}")
            return False

    def run(self):
        """运行主循环"""
        if not self.agent:
            logger.error("Agent 未初始化")
            return

        self._running = True
        self._send_status("ready")
        logger.info("TUI Bridge 进程启动，开始主循环")

        while self._running:
            try:
                user_input = self.input_queue.get()

                if user_input is None:
                    logger.info("接收到 EOF，退出主循环")
                    break

                if not user_input or user_input == INTERRUPT_SIGNAL:
                    continue

                logger.info(f"收到 TUI 输入: {user_input[:100]}...")
                self._on_message_received(user_input)

            except KeyboardInterrupt:
                logger.info("接收到键盘中断")
                break
            except Exception as e:
                error_trace = traceback.format_exc()
                logger.error(f"TUI Bridge 运行时异常:\n{error_trace}")
                self._send_error(f"Runtime Error: {str(e)}. 请查看日志输出。")
                break

        if self.agent:
            self.agent.shutdown()

        logger.info("TUI Bridge 主循环结束")

    def _on_message_received(self, message: str) -> None:
        """通过 callback wrapper 处理消息，保持 legacy 异常边界。"""
        try:
            self._process_user_input(message)
        except Exception as e:
            logger.error(f"TUI Bridge 回调处理异常: {e}", exc_info=True)
            self._send_error(f"Error: {str(e)}")

    def _process_user_input(self, user_input: str):
        """处理用户输入"""
        if self.agent is None:
            self._send_error("Agent not initialized")
            return

        agent = self.agent

        interrupted = False
        while not self.input_queue.empty():
            msg = self.input_queue.get_nowait()
            if msg == INTERRUPT_SIGNAL:
                logger.info("检测到中断信号")
                agent.interrupt()
                interrupted = True
                break

        if interrupted:
            self._send_status("done")
            return

        try:
            for response in agent.chat(user_input):
                while not self.input_queue.empty():
                    msg = self.input_queue.get_nowait()
                    if msg == INTERRUPT_SIGNAL:
                        agent.interrupt()
                        self._send_status("done")
                        return

                self._send_response(response)

        except Exception as e:
            logger.error(f"处理用户输入时发生错误: {e}", exc_info=True)
            self._send_error(f"Processing error: {str(e)}")

    def _send_response(self, response):
        """发送响应到 TUI"""
        try:
            data = response_to_dict(response)
            if data is None:
                return
            _print_legacy_message(data)
        except Exception as e:
            logger.error(f"发送响应失败: {e}")

    def _send_status(self, status: str):
        """发送状态消息"""
        try:
            _print_legacy_message(serialize_status_message(status))
        except Exception as e:
            logger.error(f"发送状态失败: {e}")

    def _send_error(self, content: str, code: str = ""):
        """发送错误消息"""
        try:
            _print_legacy_message(serialize_error_message(content=content, code=code))
        except Exception as e:
            logger.error(f"发送错误失败: {e}")

    def stop(self):
        """停止桥接器"""
        self._running = False


def main():
    """主入口"""
    _prepare_process_environment()
    bridge = TUIBridge()

    if bridge.initialize():
        bridge.run()
    else:
        logger.error("TUI Bridge 初始化失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
