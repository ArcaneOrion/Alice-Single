from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GatewayConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    token: str = ""
    protocol_version: str = "1"
    outbound_queue_limit: int = 256
    replay_limit: int = 512
    session_ttl_seconds: int = 1800

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        return cls(
            host=os.getenv("GATEWAY_HOST", "127.0.0.1"),
            port=int(os.getenv("GATEWAY_PORT", "8765")),
            token=os.getenv("GATEWAY_TOKEN", ""),
            protocol_version=os.getenv("GATEWAY_PROTOCOL_VERSION", "1"),
            outbound_queue_limit=int(os.getenv("GATEWAY_OUTBOUND_QUEUE_LIMIT", "256")),
            replay_limit=int(os.getenv("GATEWAY_REPLAY_LIMIT", "512")),
            session_ttl_seconds=int(os.getenv("GATEWAY_SESSION_TTL_SECONDS", "1800")),
        )


__all__ = ["GatewayConfig"]
