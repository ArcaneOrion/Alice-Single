"""
Logging schema 单元测试

确保 schema_version.json 的结构完整且包含关键的 event_type。
"""

import json
import unittest
from pathlib import Path


class TestLoggingSchema(unittest.TestCase):
    """验证 logging schema 版本文件中的入口与枚举。"""

    def setUp(self) -> None:
        self.schema_path = Path(".alice/logs/schema_version.json")
        self.assertTrue(self.schema_path.exists(), "日志 schema 文件不存在")
        with self.schema_path.open("r", encoding="utf-8") as fp:
            self.schema = json.load(fp)

    def test_required_fields_present(self) -> None:
        """必须字段列表里应包含 ts/event_type/level/source。"""
        required = self.schema.get("required_fields", [])
        for field in ("ts", "event_type", "level", "source"):
            self.assertIn(field, required)

    def test_log_files_coverage(self) -> None:
        """每个日志文件都应列出 event_type 枚举，且枚举包含关键值。"""
        log_files = {
            entry.get("file"): entry.get("event_types", [])
            for entry in self.schema.get("log_files", [])
        }
        expected = {
            "system.jsonl": [
                "system.start",
                "system.shutdown",
                "system.health_check",
                "system.config_reload",
                "system.alert",
            ],
            "tasks.jsonl": [
                "task.created",
                "task.started",
                "task.progress",
                "task.completed",
                "task.failed",
            ],
            "changes.jsonl": [
                "change.file_saved",
                "change.memory_updated",
                "change.skill_loaded",
                "change.config_mutation",
                "change.execution_plan",
            ],
        }

        for log_file, event_types in expected.items():
            self.assertIn(log_file, log_files)
            for event_type in event_types:
                self.assertIn(event_type, log_files[log_file])

    def test_event_type_definitions_exist(self) -> None:
        """event_types 节点应覆盖上层所有枚举值。"""
        definitions = self.schema.get("event_types", {})
        self.assertIsInstance(definitions, dict)
        required = [
            "system.start",
            "system.shutdown",
            "system.health_check",
            "system.config_reload",
            "system.alert",
            "task.created",
            "task.started",
            "task.progress",
            "task.completed",
            "task.failed",
            "change.file_saved",
            "change.memory_updated",
            "change.skill_loaded",
            "change.config_mutation",
            "change.execution_plan",
        ]
        for event_type in required:
            self.assertIn(event_type, definitions)

    def test_example_records_have_required_fields(self) -> None:
        """示例记录必须包含必需字段，保障数据质量。"""
        examples = self.schema.get("example_records", {})
        required = self.schema.get("required_fields", [])
        for records in examples.values():
            for record in records:
                for field in required:
                    self.assertIn(field, record)


if __name__ == "__main__":
    unittest.main()
