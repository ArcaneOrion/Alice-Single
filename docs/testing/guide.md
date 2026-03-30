# 测试指南

本页是贡献者视角的测试入口，聚焦“去哪里找测试、先跑什么、什么改动需要补哪类测试”。

更完整的历史说明仍可参考 `backend/tests/README.md`。

## 测试目录
- `backend/tests/unit/`: 单元测试
- `backend/tests/integration/`: 集成测试
- `backend/tests/performance/`: 性能测试
- `backend/tests/fixtures/`: 共享 fixtures

## 常用命令

### 跑后端全量测试
```bash
python -m pytest backend/tests
```

### 常用筛选
```bash
pytest -m unit
pytest -m integration
pytest -m "not slow"
```

### 常用静态检查
```bash
python -m ruff check backend/alice backend/tests
python -m mypy backend/alice
```

### 前端验证
```bash
cd frontend && cargo test
cd frontend && cargo clippy
cd frontend && cargo fmt --check
```

## 什么时候补什么测试
- 纯后端逻辑改动：优先补 unit tests。
- 影响 workflow orchestration、bridge communication、Docker execution、跨模块边界：补 integration tests。
- 影响吞吐、日志写入、重执行路径：检查是否需要 performance tests。
- 改协议或状态流：前后端验证一起跑，不要只跑单侧。

## 当前值得注意的测试覆盖点
- `backend/tests/integration/test_bridge.py`: Bridge 通信
- `backend/tests/integration/test_agent.py`: Agent 集成路径
- `backend/tests/integration/test_logging_e2e.py`: Logging 端到端
- `backend/tests/performance/test_log_write_speed.py`: Logging 性能

## 标记
当前常用 pytest markers：
- `unit`
- `integration`
- `slow`

## 文档维护提醒
如果你新增了重要测试类别、夹具模式或验证命令，请同步更新本页和 `backend/tests/README.md`。
