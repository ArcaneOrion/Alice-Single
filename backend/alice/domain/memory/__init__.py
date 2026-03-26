"""
Memory Domain Module

内存领域模块，负责管理所有内存相关的数据模型、存储和服务。

包含：
- models: 数据模型（MemoryEntry, RoundEntry）
- stores: 存储实现（WorkingMemoryStore, STMStore, LTMStore）
- services: 服务层（MemoryManager, Distiller）
- repository: 文件存储（FileRepository）
"""

# 数据模型
from backend.alice.domain.memory.models.memory_entry import MemoryEntry
from backend.alice.domain.memory.models.round_entry import RoundEntry

# 存储实现
from backend.alice.domain.memory.stores.base import BaseMemoryStore, BaseWorkingMemoryStore
from backend.alice.domain.memory.stores.working_store import WorkingMemoryStore
from backend.alice.domain.memory.stores.stm_store import STMStore
from backend.alice.domain.memory.stores.ltm_store import LTMStore

# 服务层
from backend.alice.domain.memory.services.memory_manager import MemoryManager
from backend.alice.domain.memory.services.distiller import Distiller

# 仓储层
from backend.alice.domain.memory.repository.file_repository import FileRepository


__all__ = [
    # 数据模型
    "MemoryEntry",
    "RoundEntry",
    # 存储基类
    "BaseMemoryStore",
    "BaseWorkingMemoryStore",
    # 存储实现
    "WorkingMemoryStore",
    "STMStore",
    "LTMStore",
    # 服务层
    "MemoryManager",
    "Distiller",
    # 仓储层
    "FileRepository",
]
