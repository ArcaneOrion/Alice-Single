"""
Interrupt Handler

处理中断信号，协调各模块的中断状态。
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from ..legacy_compatibility_serializer import serialize_status_message

if TYPE_CHECKING:
    from ..server import BridgeServer


logger = logging.getLogger(__name__)


def _interrupt_log_extra(
    event_type: str,
    *,
    data: Optional[dict[str, Any]] = None,
    error: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """构造 InterruptHandler 结构化日志字段。"""
    payload: dict[str, Any] = {
        "event_type": event_type,
        "log_category": "bridge.interrupt_handler",
        "context": {
            "component": "bridge_interrupt_handler",
        },
        "data": data or {},
    }
    if error is not None:
        payload["error"] = error
    return payload


class InterruptHandler:
    """
    中断处理器。

    负责检测和处理来自前端的中断信号。

    Args:
        server: BridgeServer 实例
    """

    def __init__(self, server: "BridgeServer"):
        self.server = server
        self._interrupt_count: int = 0

    def check_interrupt(self) -> bool:
        """
        检查是否有中断信号。

        Returns:
            bool: 是否检测到中断信号
        """
        # 检查待处理的中断信号
        try:
            drain_pending_interrupts = getattr(self.server.transport, "drain_pending_interrupts", None)
            if not callable(drain_pending_interrupts):
                return False

            found = drain_pending_interrupts()
            if found:
                self._interrupt_count += 1
                logger.info(
                    "Interrupt signal detected",
                    extra=_interrupt_log_extra(
                        "bridge.interrupt",
                        data={
                            "phase": "check_interrupt",
                            "source": "transport_queue",
                            "interrupt_count": self._interrupt_count,
                        },
                    ),
                )

                # 传播中断到当前 Agent
                agent = self.server.agent
                if agent:
                    agent.interrupt()

                self.server.send_message(serialize_status_message("done"))
                return True

            return False
        except Exception as e:
            logger.error(
                "Interrupt handling failed",
                exc_info=True,
                extra=_interrupt_log_extra(
                    "bridge.error",
                    data={"phase": "check_interrupt"},
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                    },
                ),
            )
            return False

    def reset_interrupt(self) -> None:
        """重置中断状态。"""
        logger.info(
            "Interrupt state reset",
            extra=_interrupt_log_extra(
                "bridge.interrupt",
                data={"phase": "reset_interrupt", "action": "reset"},
            ),
        )

    @property
    def interrupt_count(self) -> int:
        """获取累计中断次数。"""
        return self._interrupt_count


__all__ = [
    "InterruptHandler",
]
