"""
Interrupt Handler

处理中断信号，协调各模块的中断状态。
"""

import logging
from typing import TYPE_CHECKING

from ..protocol.messages import INTERRUPT_SIGNAL

if TYPE_CHECKING:
    from ..server import BridgeServer


logger = logging.getLogger(__name__)


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
        found = self.server.transport.drain_pending_interrupts()
        if found:
            self._interrupt_count += 1
            logger.info(f"检测到中断信号 (累计: {self._interrupt_count})")

            # 设置 Agent 中断状态
            agent = self.server.agent
            if agent:
                agent.interrupted = True

            return True

        return False

    def reset_interrupt(self) -> None:
        """重置中断状态。"""
        agent = self.server.agent
        if agent:
            agent.interrupted = False

    @property
    def interrupt_count(self) -> int:
        """获取累计中断次数。"""
        return self._interrupt_count


__all__ = [
    "InterruptHandler",
]
