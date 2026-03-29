# Log Validation Report

## 1. 验证目的
- 确保 `.alice/logs` 下的 `system.jsonl`、`tasks.jsonl`、`changes.jsonl` 均被 JSONL 结构化 logger 正常写入。
- 保证每条记录至少含字段 `ts`、`event_type`、`level`、`source`，便于后续 schema 驱动处理。
- 验证典型任务生命周期（创建 → 启动 → 进度 → 完成）可以通过 `task_id` 串联。

## 2. 执行步骤
1. 运行集成测试：
   - `pytest backend/tests/integration/test_logging_e2e.py`
   - 该测试在临时目录中启动 `JSONLCategoryFileHandler`，发送跨 `system/tasks/changes` 事件并注入 `llm_call`/`llm_response` 事件，确认 `tasks.jsonl` 事件顺序、`task_id`/`trace_id` 串联以及 `full payload` 样例（通过 `StreamService` 触发）。
2. 运行性能测试（可选）：
   - `pytest backend/tests/performance/test_log_write_speed.py`
   - 该测试写入 1024 条 `task.progress` 事件并计算吞吐；吞吐验证之后还写入 `full_payload` 模式事件以确认上下文与 metadata 描述被持久化。
3. 使用日志校验脚本：
   - `python scripts/validate_logs.py /path/to/.alice/logs/*.jsonl`
   - 脚本会遍历 `.jsonl` 文件，确保每行是合法 JSON；缺失字段或不可解析记录会被列出，同时会确认 `context`/`data` 为对象、`llm_*` 事件上下文含 `task_id`/`request_id`/`trace_id`，`full_payload` 模式下 `metadata.length` 是整数且至少不小于内容长度。

## 3. 验收标准
- 所有目标 `.jsonl` 文件被创建。
- 每条事件都可正常解析为 JSON，对应必需字段存在。
- `tasks.jsonl` 中的生命周期事件顺序未中断，所有记录都共享 `task_id`。
- `llm_call`/`llm_response` 事件可通过 `context.task_id` 和 `context.request_id`/`trace_id` 串联。
- 性能测试吞吐率可记录以便未来回归，若写入速率显著下降（例如 < 100 条/秒），需调查 handler 线程/磁盘状况。
- `full_payload` 模式事件在 `data.payload.metadata` 中报告的 `length` 是整数，且 `content` 长度不超过该值。

## 4. 风险与假设
- 假设主控会在初始化时创建 `.alice/logs/schema_version.json` 并把 schema 描述放在该目录；如果 schema 文件尚未同步，测试依赖的字段列表可能需要手动同步。
- 集成测试目前仅依赖 `JSONLCategoryFileHandler`，未覆盖整条 Agent 工作流；当主控引入额外格式化规则或 categories map 时，需要在主控完成后复核 `category_mapping` 是否需要同步。
- 性能测试假设写入环境是本地 SSD；在高延迟挂载（如 NFS）上实际吞吐会显著低于本地，需在报告中标明。
