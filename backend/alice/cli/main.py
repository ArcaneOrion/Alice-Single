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
from backend.alice.application.services import OrchestrationService, LifecycleService
from backend.alice.application.workflow import WorkflowChain, ChatWorkflow
from backend.alice.application.dto import response_to_dict
from backend.alice.core.config.loader import load_config
from backend.alice.core.logging import configure_logging
from backend.alice.domain.llm.providers.base import ProviderCapability
from backend.alice.domain.llm.providers.openai_provider import resolve_request_header_profiles
from backend.alice.infrastructure.bridge.legacy_compatibility_serializer import (
    serialize_error_message,
    serialize_status_message,
)
from backend.alice.infrastructure.bridge.protocol.messages import INTERRUPT_SIGNAL

logger = logging.getLogger("AliceCLI")


def _print_legacy_message(message: dict) -> None:
    print(json.dumps(message), flush=True)


def _parse_request_header_profiles(profiles_str: str) -> list[dict]:
    """解析环境变量中的请求头轮询配置。"""
    if not profiles_str.strip():
        return []

    try:
        parsed = json.loads(profiles_str)
    except json.JSONDecodeError:
        import ast

        parsed = ast.literal_eval(profiles_str)

    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError("REQUEST_HEADER_PROFILES 必须是对象数组")

    return parsed


class TUIBridge:
    """TUI 桥接器

    处理与 Rust TUI 的通信。
    """

    def __init__(self):
        """初始化桥接器"""
        self.agent: AliceAgent | None = None
        self.input_queue = queue.Queue()
        self._running = False

        # 初始化异步输入监听
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
        """初始化 Agent

        Returns:
            是否初始化成功
        """
        try:
            # 加载配置
            from dotenv import load_dotenv

            load_dotenv()
            settings = load_config()
            settings.logging.console_level = "ERROR"
            configure_logging(settings.logging)

            api_key = os.getenv("API_KEY", "")
            base_url = os.getenv("API_BASE_URL", "https://api-inference.modelscope.cn/v1/")
            model_name = os.getenv("MODEL_NAME", "")

            if not api_key:
                raise ValueError("API_KEY 环境变量未设置")
            if not model_name:
                raise ValueError("MODEL_NAME 环境变量未设置")

            # 解析请求头配置
            request_header_profiles = []
            profiles_str = os.getenv("REQUEST_HEADER_PROFILES", "")
            if profiles_str:
                try:
                    request_header_profiles = _parse_request_header_profiles(profiles_str)
                except Exception:
                    logger.warning("解析 REQUEST_HEADER_PROFILES 失败")
            request_header_profiles = resolve_request_header_profiles(
                base_url,
                request_header_profiles,
            )

            # 解析 provider capability 覆盖
            capabilities = None
            if os.getenv("PROVIDER_SUPPORTS_TOOL_CALLING", "").lower() in ("false", "0", "no"):
                capabilities = ProviderCapability(supports_tool_calling=False)

            # 创建编排服务
            orchestration = OrchestrationService.create_from_config(
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                project_root=project_root,
                extra_headers={},
                request_header_profiles=request_header_profiles,
                capabilities=capabilities,
            )

            # 创建生命周期服务
            lifecycle = LifecycleService(project_root=project_root)

            # 创建工作流链
            workflow_chain = WorkflowChain()
            workflow_chain.add_workflow(
                ChatWorkflow(
                    chat_service=orchestration.chat_service,
                    execution_service=orchestration.execution_service,
                    tool_registry=orchestration.tool_registry,
                    function_calling_orchestrator=orchestration.function_calling_orchestrator,
                )
            )

            # 创建 Agent
            self.agent = AliceAgent(
                orchestration_service=orchestration,
                lifecycle_service=lifecycle,
                workflow_chain=workflow_chain,
            )

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

        # 发送就绪信号
        self._send_status("ready")

        logger.info("TUI Bridge 进程启动，开始主循环")

        while self._running:
            try:
                # 从异步队列获取输入
                user_input = self.input_queue.get()

                if user_input is None:
                    logger.info("接收到 EOF，退出主循环")
                    break

                if not user_input or user_input == INTERRUPT_SIGNAL:
                    continue

                logger.info(f"收到 TUI 输入: {user_input[:100]}...")

                # 处理请求
                self._process_user_input(user_input)

            except KeyboardInterrupt:
                logger.info("接收到键盘中断")
                break
            except Exception as e:
                error_trace = traceback.format_exc()
                logger.error(f"TUI Bridge 运行时异常:\n{error_trace}")
                self._send_error(f"Runtime Error: {str(e)}. 请查看日志输出。")
                break

        # 清理
        if self.agent:
            self.agent.shutdown()

        logger.info("TUI Bridge 主循环结束")

    def _process_user_input(self, user_input: str):
        """处理用户输入

        Args:
            user_input: 用户输入内容
        """
        if self.agent is None:
            self._send_error("Agent not initialized")
            return

        agent = self.agent

        # 检查中断信号
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

        # 创建请求并处理
        try:
            for response in agent.chat(user_input):
                # 检查中断
                while not self.input_queue.empty():
                    msg = self.input_queue.get_nowait()
                    if msg == INTERRUPT_SIGNAL:
                        agent.interrupt()
                        self._send_status("done")
                        return

                # 发送响应
                self._send_response(response)

        except Exception as e:
            logger.error(f"处理用户输入时发生错误: {e}", exc_info=True)
            self._send_error(f"Processing error: {str(e)}")

    def _send_response(self, response):
        """发送响应到 TUI

        Args:
            response: 应用响应
        """
        try:
            data = response_to_dict(response)
            if data is None:
                return
            _print_legacy_message(data)
        except Exception as e:
            logger.error(f"发送响应失败: {e}")

    def _send_status(self, status: str):
        """发送状态消息

        Args:
            status: 状态字符串
        """
        try:
            _print_legacy_message(serialize_status_message(status))
        except Exception as e:
            logger.error(f"发送状态失败: {e}")

    def _send_error(self, content: str, code: str = ""):
        """发送错误消息

        Args:
            content: 错误内容
            code: 错误代码
        """
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
