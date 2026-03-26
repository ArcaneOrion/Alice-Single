"""
Memory Entry Model

内存条目数据模型，定义存储在内存系统中的基本单元。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MemoryEntry:
    """内存条目

    表示存储在内存系统中的单个条目，包含内容、时间戳和元数据。

    Attributes:
        content: 内存条目的文本内容
        timestamp: 条目创建时间
        metadata: 附加的元数据信息（可选）
    """

    content: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """确保元数据不为 None"""
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        """从字典创建实例"""
        return cls(
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


__all__ = ["MemoryEntry"]
