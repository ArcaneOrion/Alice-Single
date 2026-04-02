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


def _serialize_response(response: Any) -> dict[str, Any] | None:
    """惰性导入 DTO 序列化函数，避免 bridge 初始化环。"""
    from backend.alice.application.dto.responses import response_to_dict

    return response_to_dict(response)


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

        forwarded_messages = 0
        skipped_responses = 0

        try:
            self._processing = True
            for response in agent.chat(user_input):
                data = _serialize_response(response)
                if data is None:
                    skipped_responses += 1
                    continue

                self.server.send_message(data)
                forwarded_messages += 1

            logger.info(
                "Bridge handler forwarded agent responses",
                extra=_handler_log_extra(
                    "bridge.message_sent",
                    data={
                        "phase": "handle_input",
                        "forwarded_messages": forwarded_messages,
                        "skipped_responses": skipped_responses,
                    },
                ),
            )
        except Exception as e:
            logger.error(
                "Error while processing user input",
                exc_info=True,
                extra=_handler_log_extra(
                    "bridge.error",
                    data={
                        "phase": "handle_input",
                        "input_length": len(user_input),
                        "forwarded_messages": forwarded_messages,
                        "skipped_responses": skipped_responses,
                    },
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                    },
                ),
            )
            self.server.send_error(f"Processing error: {str(e)}")
        finally:
            self._processing = False

    @property
    def is_processing(self) -> bool:
        """检查是否正在处理消息。"""
        return self._processing


__all__ = [
    "MessageHandler",
]
