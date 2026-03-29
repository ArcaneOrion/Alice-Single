"""
Logging schema 单元测试

确保 schema_version.json 的结构完整且包含关键的 event_type。
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.alice.core.config.settings import LoggingConfig
from backend.alice.core.logging.configure import _ensure_schema_file


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
            "model.stream_started",
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

    def test_field_definitions_include_payload_fields(self) -> None:
        """field_definitions 应包含 payload 相关字段（task_id/span_id/context/data/error）。"""
        definitions = self.schema.get("field_definitions", {})
        expected_types = {
            "task_id": "string",
            "span_id": "string",
            "context": "object",
            "data": "object",
            "error": "object",
        }
        for field, expected_type in expected_types.items():
            self.assertIn(field, definitions, f"{field} should be defined in field_definitions")
            definition = definitions[field]
            self.assertEqual(
                definition.get("type"),
                expected_type,
                f"{field} definition should describe type {expected_type}",
            )

    def test_examples_show_context_and_data_usage(self) -> None:
        """示例记录里应至少出现一次 context 和 data，展示完整载荷模式。"""
        examples = self.schema.get("example_records", {})
        has_context = False
        has_data = False
        for records in examples.values():
            for record in records:
                has_context = has_context or ("context" in record)
                has_data = has_data or ("data" in record)

        self.assertTrue(has_context, "At least one example record should include context")
        self.assertTrue(has_data, "At least one example record should include data")

    def test_existing_legacy_schema_is_refreshed_when_shape_expands(self) -> None:
        """已有旧版 schema 文件时，也应自动升级到当前完整结构。"""
        with TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            schema_path = logs_dir / "schema_version.json"
            schema_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "generated_at": "2026-03-28T00:00:00Z",
                        "required_fields": ["ts", "event_type", "level", "source"],
                        "log_files": [],
                        "recommended_fields": [],
                    }
                ),
                encoding="utf-8",
            )

            config = LoggingConfig(logs_dir=str(logs_dir))
            _ensure_schema_file(config, logs_dir)

            upgraded_schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(upgraded_schema["schema_version"], "2.0.0")
            self.assertIn("event_types", upgraded_schema)
            self.assertIn("field_definitions", upgraded_schema)
            self.assertIn("example_records", upgraded_schema)


if __name__ == "__main__":
    unittest.main()
