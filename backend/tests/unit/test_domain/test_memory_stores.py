"""
Memory store 单元测试

验证基础存储类型能够正常实例化。
"""

from pathlib import Path
import tempfile
import unittest

from backend.alice.domain.memory.stores.working_store import WorkingMemoryStore


class TestMemoryStores(unittest.TestCase):
    """Memory store 测试"""

    def test_working_memory_store_initializes_with_file_path(self) -> None:
        """WorkingMemoryStore 应能用 file_path 正常初始化"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "working.md"
            store = WorkingMemoryStore(str(file_path), max_rounds=5)

        self.assertEqual(store.file_path, str(file_path))
        self.assertEqual(store.max_rounds, 5)


if __name__ == "__main__":
    unittest.main()
