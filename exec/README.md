# Exec 文档索引

本目录现在分为三类文档：**背景**、**当前计划**、**历史材料**。

## 当前计划（先看这里）
- [当前树审查基线](./audit-baseline-current-tree.md)
- [短周期修复计划](./short-cycle-repair-plan.md)
- [文件所有权矩阵](./ownership-matrix.md)
- [短周期 Agent 提示词](./agent-prompts-short-cycle.md)
- [进度记录](./progress.md)

## 背景材料（保留原因，不作为当前执行依据）
- [背景与原因](./harness-decoupling-context.md)
- [合同审查索引](./contracts/README.md)
- `exec/contracts/` 下三份 contract spec

## 历史材料（仅供回溯，不作为当前执行依据）
- [历史长期计划](./harness-decoupling-plan.md)
- [历史并行执行计划](./parallel-execution-plan.md)
- [历史 Agent 提示词](./agent-prompts.md)
- [历史 handoff](./handoff/gamma-to-delta.md)

## 当前工作结论
本轮不继续推进“全面插件化 / gateway 演进”主线，而是先完成一轮**短周期修复**，把代码现实、测试基线、执行边界与文档重新对齐。

当前 active scope 只有四件事：
1. 修复测试基线阻塞
2. 真正收口 execution harness seam
3. 对齐 composition root 与真实入口
4. 收口 workflow / provider 的最小契约漂移

## 使用顺序
1. 先读 `audit-baseline-current-tree.md`
2. 再按 `short-cycle-repair-plan.md` 分 wave 执行
3. 每个 agent 只看 `ownership-matrix.md` 中属于自己的文件
4. 终端 prompt 直接从 `agent-prompts-short-cycle.md` 复制
5. 完成后统一写入 `progress.md`
