# 架构决策记录索引

本目录存放本项目所有架构决策记录（ADR）。

## 惯例

- 每条 ADR 编号单调递增,从 000 开始,不复用
- 文件名格式:`adr-NNN.md`(三位数字,零填充)
- 状态变更不删除旧记录,在文件顶部 Status 字段更新
- 每次 commit 在 message 中引用相关 ADR:`[ADR-NNN]` 或 `[ADR-none]`

## 创建新 ADR

```bash
/spec-vc adr-new "<简短的名词短语标题>"
```

## 当前 ADR 列表

<!--
由 /spec-vc adr-list 按需自动维护。手动修改会在下次运行 list 命令时被覆盖。
init 成功后,此区域会被首次 list 调用填充。
-->

_(尚无 ADR。运行 `/spec-vc adr-new "<title>"` 创建第一条,或运行 `/spec-vc adr-list` 刷新本表。)_

| 编号 | 标题 | 状态 | 日期 |
|------|------|------|------|
| ADR-000 | 采用 ADR 方法论 | Accepted | 2026-04-28 |

## 状态图例

- **Proposed** — 提议中,尚未达成一致
- **Accepted** — 已接受,代码可开始实现
- **Deprecated** — 不再使用但未被替代
- **Superseded by ADR-XXX** — 被新决策替代

## 相关资源

- ADR 模板:由 spec-vc skill 的 `templates/adr.md` 提供
- 框架说明:spec-vc skill 的 README.md
