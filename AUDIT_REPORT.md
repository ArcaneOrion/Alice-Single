# Alice-Single 架构重构审计报告

**日期**: 2026-03-26
**审计员**: Agent-Cleanup
**状态**: 不能安全删除旧代码

---

## 1. 审计发现

### 1.1 新架构实现状态

| 模块 | 状态 | 文件数 | 说明 |
|------|------|--------|------|
| Backend Domain 层 | ✅ 完成 | 62+ 文件 | LLM, Memory, Execution, Skills 模块完整 |
| Backend Application 层 | ✅ 完成 | 13+ 文件 | Agent, Workflows, Services, DTOs |
| Backend Infrastructure 层 | ✅ 完成 | 18+ 文件 | Bridge, Docker, Cache, Logging |
| Frontend (Rust) | ⚠️ 部分 | 33+ 文件 | 只有 lib.rs，缺少 main.rs 入口 |

### 1.2 旧代码依赖分析

**当前运行入口**: `src/main.rs` (第 165 行)
```rust
let mut child = Command::new("python3")
    .arg("./tui_bridge.py")  // ← 调用旧的桥接层
    .spawn()?;
```

**旧代码调用链**:
```
src/main.rs (Rust)
    ↓
tui_bridge.py
    ↓
agent.py (旧单体 Agent)
    ↓
config.py, snapshot_manager.py
```

### 1.3 新架构未集成原因

1. **`frontend/` 没有 `main.rs` 入口点**
   - 只有 `lib.rs` 库文件
   - 缺少 TUI 运行时代码

2. **新的 CLI 入口未被调用**
   - `backend/alice/cli/main.py` 存在
   - 但没有 Rust 前端调用它

3. **根目录 Cargo.toml 仍指向旧代码**
   - 没有 workspace 配置
   - `frontend/Cargo.toml` 是独立的

---

## 2. 文件对比分析

### 2.1 可以删除的文件 (暂缓)

| 文件 | 新替代 | 状态 |
|------|--------|------|
| `agent.py` | `backend/alice/application/agent/agent.py` | 新实现完成 |
| `tui_bridge.py` | `backend/alice/cli/main.py` | 新实现完成 |
| `config.py` | `backend/alice/core/config/` | 新实现完成 |
| `snapshot_manager.py` | `backend/alice/domain/skills/` | 新实现完成 |
| `src/main.rs` | `frontend/src/main.rs` | **不存在** |

### 2.2 不能删除的原因

```
当前状态: 旧代码仍在运行
                    ↓
删除旧代码 → 系统无法启动
                    ↓
需要: 完成 frontend 入口点集成
```

---

## 3. 关键缺失组件

### 3.1 Frontend Main Entry

缺失文件: `frontend/src/main.rs`

应包含:
- TUI 初始化
- 调用 `backend/alice/cli/main.py`
- 事件处理循环
- UI 渲染

### 3.2 Workspace 配置

缺失文件: 根目录 `Cargo.toml` workspace 配置

应包含:
```toml
[workspace]
members = ["frontend"]

[workspace.dependencies]
ratatui = "0.29"
# ... 共享依赖
```

---

## 4. 下一步行动

### 方案 A: 完成新架构集成 (推荐)

1. 创建 `frontend/src/main.rs`
2. 创建 `frontend/src/bin/alice.rs`
3. 更新根目录 `Cargo.toml` 为 workspace
4. 测试新入口点
5. **然后**删除旧代码

### 方案 B: 保持双系统 (保守)

- 保留旧代码作为备用
- 新架构作为独立开发分支
- 待新架构稳定后再切换

---

## 5. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 新架构未测试 | 高 | 编写集成测试 |
| 缺少前端入口 | 高 | 实现 main.rs |
| 旧代码删除后无法恢复 | 中 | Git 保留历史 |

---

## 6. 结论

**不能安全删除旧代码**。新架构后端已完成，但前端入口点缺失。

**建议**: 先完成 `frontend/src/main.rs` 实现，验证新架构可运行后，再删除旧代码。

---

审计完成。
