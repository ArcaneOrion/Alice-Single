"""Phase-2 本地时间提供器。"""

from __future__ import annotations

from datetime import datetime

from .models import LocalTimeContext


class TimeProvider:
    """本机优先的轻量时间提供器。"""

    def now(self) -> LocalTimeContext:
        current = datetime.now().astimezone()
        timezone = current.tzname() or str(current.tzinfo or "local")
        return LocalTimeContext(
            iso=current.isoformat(),
            timezone=timezone,
            source="local",
        )


__all__ = ["TimeProvider"]
