# ADR-001 执行方案 001

- **ADR**: ADR-001
- **ADR Title**: 目录结构重组：skills 归入后端包、Dockerfile 建 docker/ 目录收容
- **Stage**: close
- **Created At**: 2026-05-06T21:38:09
- **Summary**: 目录结构重组：skills/ 迁移至 backend/alice/skills/，Dockerfile.sandbox 迁移至 docker/

## Clarification

- 动机与上下文: 根目录散落 skills/、Dockerfile.sandbox、prompts/，前后端模块边界模糊。skills 是后端 Python agent 的运行时能力模块（SKILL.md + 可选脚本），应归入后端包内。.alice/ 是用户私有运行时配置目录（被 .gitignore 忽略），不适合存放需要版本控制的 skills。
- 目标与边界: 将 skills/ 迁移至 backend/alice/skills/；Dockerfile.sandbox 迁移至 docker/Dockerfile.sandbox；prompts/ 保持不动（模板源需版本控制，不可放入 .alice/）。不改动容器内 /app/skills/ 路径，只调整宿主机挂载路径；不强制迁移用户本地 .alice/config.json 中自定义的 skills_dir。
- 设计与架构: 后端包 self-contained：backend/alice/ 同时包含业务代码与技能库，减少根目录噪音。docker/ 目录收容所有运行时镜像定义。通过 DockerConfig.default_mounts 将宿主机 backend/alice/skills/ 映射到容器 /app/skills/，保持容器内路径语义不变。配置默认值从 skills_dir="skills" 改为 "backend/alice/skills"，由 get_absolute_path() 解析。
- 实现路径: 1. git mv skills/ backend/alice/skills/（保持历史）。2. git mv Dockerfile.sandbox docker/。3. 更新硬编码路径：settings.py 默认值、docker/config.py 挂载路径与 dockerfile_path、skills loaders/repository/cache 默认参数、execution_service cat 缓存日志、tool_registry 与 toolkit_command 描述文本、prompts/04_tools.xml 路径提示、README.md 目录结构。4. 更新测试断言。5. pyproject.toml mypy exclude 添加 backend/alice/skills/ 避免无 __init__.py 的路径冲突。
- 验证与测试: pytest backend/tests：295 passed, 4 warnings。ruff 检查（1024 个已有错误非本次引入）。mypy 排除 skills/ 后通过。验证容器挂载路径：宿主机 backend/alice/skills/ → 容器 /app/skills/，skills 文件在容器内可访问。
- 风险与回滚: 风险：用户本地 .alice/config.json 中自定义 skills_dir 可能指向旧路径，需手动更新。回滚方案：git mv 恢复目录位置 + 恢复 settings.py/docker/config.py 默认值 + 移除 pyproject.toml exclude。


## Clarification History

- 动机与上下文: 根目录散落 skills/、Dockerfile.sandbox、prompts/，前后端模块边界模糊。skills 是后端 Python agent 的运行时能力模块（SKILL.md + 可选脚本），应归入后端包内。.alice/ 是用户私有运行时配置目录（被 .gitignore 忽略），不适合存放需要版本控制的 skills。
- 目标与边界: 将 skills/ 迁移至 backend/alice/skills/；Dockerfile.sandbox 迁移至 docker/Dockerfile.sandbox；prompts/ 保持不动（模板源需版本控制，不可放入 .alice/）。不改动容器内 /app/skills/ 路径，只调整宿主机挂载路径；不强制迁移用户本地 .alice/config.json 中自定义的 skills_dir。
- 设计与架构: 后端包 self-contained：backend/alice/ 同时包含业务代码与技能库，减少根目录噪音。docker/ 目录收容所有运行时镜像定义。通过 DockerConfig.default_mounts 将宿主机 backend/alice/skills/ 映射到容器 /app/skills/，保持容器内路径语义不变。配置默认值从 skills_dir="skills" 改为 "backend/alice/skills"，由 get_absolute_path() 解析。
- 实现路径: 1. git mv skills/ backend/alice/skills/（保持历史）。2. git mv Dockerfile.sandbox docker/。3. 更新硬编码路径：settings.py 默认值、docker/config.py 挂载路径与 dockerfile_path、skills loaders/repository/cache 默认参数、execution_service cat 缓存日志、tool_registry 与 toolkit_command 描述文本、prompts/04_tools.xml 路径提示、README.md 目录结构。4. 更新测试断言。5. pyproject.toml mypy exclude 添加 backend/alice/skills/ 避免无 __init__.py 的路径冲突。
- 验证与测试: pytest backend/tests：295 passed, 4 warnings。ruff 检查（1024 个已有错误非本次引入）。mypy 排除 skills/ 后通过。验证容器挂载路径：宿主机 backend/alice/skills/ → 容器 /app/skills/，skills 文件在容器内可访问。
- 风险与回滚: 风险：用户本地 .alice/config.json 中自定义 skills_dir 可能指向旧路径，需手动更新。回滚方案：git mv 恢复目录位置 + 恢复 settings.py/docker/config.py 默认值 + 移除 pyproject.toml exclude。


## Motivation and Context

根目录散落 skills/、Dockerfile.sandbox、prompts/，前后端模块边界模糊。skills 是后端 Python agent 的运行时能力模块（SKILL.md + 可选脚本），应归入后端包内。.alice/ 是用户私有运行时配置目录（被 .gitignore 忽略），不适合存放需要版本控制的 skills。


## Goals and Boundaries

将 skills/ 迁移至 backend/alice/skills/；Dockerfile.sandbox 迁移至 docker/Dockerfile.sandbox；prompts/ 保持不动（模板源需版本控制，不可放入 .alice/）。不改动容器内 /app/skills/ 路径，只调整宿主机挂载路径；不强制迁移用户本地 .alice/config.json 中自定义的 skills_dir。


## Design and Architecture

后端包 self-contained：backend/alice/ 同时包含业务代码与技能库，减少根目录噪音。docker/ 目录收容所有运行时镜像定义。通过 DockerConfig.default_mounts 将宿主机 backend/alice/skills/ 映射到容器 /app/skills/，保持容器内路径语义不变。配置默认值从 skills_dir="skills" 改为 "backend/alice/skills"，由 get_absolute_path() 解析。


## Implementation Path

1. git mv skills/ backend/alice/skills/（保持历史）。2. git mv Dockerfile.sandbox docker/。3. 更新硬编码路径：settings.py 默认值、docker/config.py 挂载路径与 dockerfile_path、skills loaders/repository/cache 默认参数、execution_service cat 缓存日志、tool_registry 与 toolkit_command 描述文本、prompts/04_tools.xml 路径提示、README.md 目录结构。4. 更新测试断言。5. pyproject.toml mypy exclude 添加 backend/alice/skills/ 避免无 __init__.py 的路径冲突。


## Verification and Testing

pytest backend/tests：295 passed, 4 warnings。ruff 检查（1024 个已有错误非本次引入）。mypy 排除 skills/ 后通过。验证容器挂载路径：宿主机 backend/alice/skills/ → 容器 /app/skills/，skills 文件在容器内可访问。


## Risks and Rollback

风险：用户本地 .alice/config.json 中自定义 skills_dir 可能指向旧路径，需手动更新。回滚方案：git mv 恢复目录位置 + 恢复 settings.py/docker/config.py 默认值 + 移除 pyproject.toml exclude。


## Affected Areas

待补充

## Pre-Change Validation

运行 pytest backend/tests：295 passed, 4 warnings（实施前基线）。ruff check：1024 个已有错误（非本次引入）。mypy 排除 skills/ 后通过。目录结构：skills/ 存在于根目录，Dockerfile.sandbox 存在于根目录。


## Post-Change Validation

运行 pytest backend/tests：295 passed, 4 warnings。ruff check：1024 个已有错误（非本次引入）。mypy：排除 backend/alice/skills/ 后通过。目录已验证：skills/ 已迁移至 backend/alice/skills/（209 个文件），Dockerfile.sandbox 已迁移至 docker/。宿主机挂载路径：backend/alice/skills/ → 容器 /app/skills/。


## Closure Summary

目录结构重组完成：skills/ 迁移至 backend/alice/skills/（209 文件），Dockerfile.sandbox 迁移至 docker/。同步更新了所有硬编码路径引用和测试断言。295 测试通过。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-001-plan-001.md


## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
