# ADR-002 执行方案 001

- **ADR**: ADR-002
- **ADR Title**: 支持双目录 skill 加载：内置 skills 与用户自定义 skills 分离
- **Stage**: validate
- **Created At**: 2026-05-06T21:51:03
- **Summary**: 实现双目录 skill 加载：仓库保留 skill-creator 作为官方 skill，其余迁移至 .alice/skills/ 作为用户自定义技能

## Clarification

- 动机与上下文: 仓库内 skills 过多（18个），且大多带大量 schema/资源文件，导致仓库臃肿、git 历史膨胀。真正需要版本控制的只有 skill-creator（元 skill，用于创建新 skill），其余应为用户按需安装到 .alice/skills/（用户私有目录，不受 git 管理）。当前架构严格单目录，无法同时加载内置 skills 和用户自定义 skills，必须改造。
- 目标与边界: 仓库 backend/alice/skills/ 只保留 skill-creator，其余全部删除。.alice/skills/ 作为用户自定义 skill 目录，系统启动时自动创建。双目录加载：先加载内置目录（backend/alice/skills/），再加载用户目录（.alice/skills/），同名 skill 以用户目录为准（覆盖）。不改动 skill 内部结构、SKILL.md 格式、容器内 /app/skills/ 路径语义。
- 设计与架构: Settings 新增 skills_user_dir: str = '.alice/skills'（与 skills_dir 并列）。DirectorySkillLoader 的 skills_dir 改为 skills_dirs: list[str | Path]，按顺序遍历加载，后加载的覆盖先加载的同名 skill。FileRepository 同理支持多目录解析。DockerConfig 新增用户 skills 挂载：.alice/skills/ → 容器 /app/user_skills/（或直接用 /app/skills/ 合并挂载）。ContainerManager._ensure_mount_directories 自动创建 .alice/skills/。SkillRegistry 在 bootstrap 时传入合并后的 skills_dirs。
- 实现路径: 1. 删除 backend/alice/skills/ 下除 skill-creator 外的所有目录（git rm -r）。2. Settings.py: skills_dir 保持 'backend/alice/skills'，新增 skills_user_dir: str = '.alice/skills'。3. loader.py: config 加载时同步赋值 skills_user_dir。4. DirectorySkillLoader: __init__ 接收 skills_dirs: list[str | Path]，refresh() 按顺序遍历各目录加载，同名覆盖。5. CacheSkillLoader 同步修改。6. FileRepository: 支持多目录解析，read_file 时按 skills_dirs 顺序查找。7. DockerConfig: default_mounts 新增 .alice/skills/ 挂载。8. ContainerManager._ensure_mount_directories 创建 .alice/skills/。9. Core registry: bootstrap 时传入 skills_dirs=[settings.skills_dir, settings.skills_user_dir]。10. 测试：更新单目录测试为多目录测试，验证覆盖行为。11. prompts/04_tools.xml 更新路径描述。
- 验证与测试: pytest backend/tests：295+ passed。验证双目录加载：在内置目录和用户目录各放一个同名 skill，确认用户目录版本生效。验证 .alice/skills/ 自动创建。验证容器挂载：docker inspect 查看 .alice/skills/ 是否挂载。
- 风险与回滚: 回滚：git revert 删除操作 + 恢复单目录配置。风险：删除操作不可逆（git rm 后可用 git checkout HEAD~1 -- skills/ 恢复，但文件多），建议先在 stash/branch 中备份。


## Clarification History

- 动机与上下文: 仓库内 skills 过多（18个），且大多带大量 schema/资源文件，导致仓库臃肿、git 历史膨胀。真正需要版本控制的只有 skill-creator（元 skill，用于创建新 skill），其余应为用户按需安装到 .alice/skills/（用户私有目录，不受 git 管理）。当前架构严格单目录，无法同时加载内置 skills 和用户自定义 skills，必须改造。
- 目标与边界: 仓库 backend/alice/skills/ 只保留 skill-creator，其余全部删除。.alice/skills/ 作为用户自定义 skill 目录，系统启动时自动创建。双目录加载：先加载内置目录（backend/alice/skills/），再加载用户目录（.alice/skills/），同名 skill 以用户目录为准（覆盖）。不改动 skill 内部结构、SKILL.md 格式、容器内 /app/skills/ 路径语义。
- 设计与架构: Settings 新增 skills_user_dir: str = '.alice/skills'（与 skills_dir 并列）。DirectorySkillLoader 的 skills_dir 改为 skills_dirs: list[str | Path]，按顺序遍历加载，后加载的覆盖先加载的同名 skill。FileRepository 同理支持多目录解析。DockerConfig 新增用户 skills 挂载：.alice/skills/ → 容器 /app/user_skills/（或直接用 /app/skills/ 合并挂载）。ContainerManager._ensure_mount_directories 自动创建 .alice/skills/。SkillRegistry 在 bootstrap 时传入合并后的 skills_dirs。
- 实现路径: 1. 删除 backend/alice/skills/ 下除 skill-creator 外的所有目录（git rm -r）。2. Settings.py: skills_dir 保持 'backend/alice/skills'，新增 skills_user_dir: str = '.alice/skills'。3. loader.py: config 加载时同步赋值 skills_user_dir。4. DirectorySkillLoader: __init__ 接收 skills_dirs: list[str | Path]，refresh() 按顺序遍历各目录加载，同名覆盖。5. CacheSkillLoader 同步修改。6. FileRepository: 支持多目录解析，read_file 时按 skills_dirs 顺序查找。7. DockerConfig: default_mounts 新增 .alice/skills/ 挂载。8. ContainerManager._ensure_mount_directories 创建 .alice/skills/。9. Core registry: bootstrap 时传入 skills_dirs=[settings.skills_dir, settings.skills_user_dir]。10. 测试：更新单目录测试为多目录测试，验证覆盖行为。11. prompts/04_tools.xml 更新路径描述。
- 验证与测试: pytest backend/tests：295+ passed。验证双目录加载：在内置目录和用户目录各放一个同名 skill，确认用户目录版本生效。验证 .alice/skills/ 自动创建。验证容器挂载：docker inspect 查看 .alice/skills/ 是否挂载。
- 风险与回滚: 回滚：git revert 删除操作 + 恢复单目录配置。风险：删除操作不可逆（git rm 后可用 git checkout HEAD~1 -- skills/ 恢复，但文件多），建议先在 stash/branch 中备份。


## Motivation and Context

仓库内 skills 过多（18个），且大多带大量 schema/资源文件，导致仓库臃肿、git 历史膨胀。真正需要版本控制的只有 skill-creator（元 skill，用于创建新 skill），其余应为用户按需安装到 .alice/skills/（用户私有目录，不受 git 管理）。当前架构严格单目录，无法同时加载内置 skills 和用户自定义 skills，必须改造。


## Goals and Boundaries

仓库 backend/alice/skills/ 只保留 skill-creator，其余全部删除。.alice/skills/ 作为用户自定义 skill 目录，系统启动时自动创建。双目录加载：先加载内置目录（backend/alice/skills/），再加载用户目录（.alice/skills/），同名 skill 以用户目录为准（覆盖）。不改动 skill 内部结构、SKILL.md 格式、容器内 /app/skills/ 路径语义。


## Design and Architecture

Settings 新增 skills_user_dir: str = '.alice/skills'（与 skills_dir 并列）。DirectorySkillLoader 的 skills_dir 改为 skills_dirs: list[str | Path]，按顺序遍历加载，后加载的覆盖先加载的同名 skill。FileRepository 同理支持多目录解析。DockerConfig 新增用户 skills 挂载：.alice/skills/ → 容器 /app/user_skills/（或直接用 /app/skills/ 合并挂载）。ContainerManager._ensure_mount_directories 自动创建 .alice/skills/。SkillRegistry 在 bootstrap 时传入合并后的 skills_dirs。


## Implementation Path

1. 删除 backend/alice/skills/ 下除 skill-creator 外的所有目录（git rm -r）。2. Settings.py: skills_dir 保持 'backend/alice/skills'，新增 skills_user_dir: str = '.alice/skills'。3. loader.py: config 加载时同步赋值 skills_user_dir。4. DirectorySkillLoader: __init__ 接收 skills_dirs: list[str | Path]，refresh() 按顺序遍历各目录加载，同名覆盖。5. CacheSkillLoader 同步修改。6. FileRepository: 支持多目录解析，read_file 时按 skills_dirs 顺序查找。7. DockerConfig: default_mounts 新增 .alice/skills/ 挂载。8. ContainerManager._ensure_mount_directories 创建 .alice/skills/。9. Core registry: bootstrap 时传入 skills_dirs=[settings.skills_dir, settings.skills_user_dir]。10. 测试：更新单目录测试为多目录测试，验证覆盖行为。11. prompts/04_tools.xml 更新路径描述。


## Verification and Testing

pytest backend/tests：295+ passed。验证双目录加载：在内置目录和用户目录各放一个同名 skill，确认用户目录版本生效。验证 .alice/skills/ 自动创建。验证容器挂载：docker inspect 查看 .alice/skills/ 是否挂载。


## Risks and Rollback

回滚：git revert 删除操作 + 恢复单目录配置。风险：删除操作不可逆（git rm 后可用 git checkout HEAD~1 -- skills/ 恢复，但文件多），建议先在 stash/branch 中备份。


## Affected Areas

待补充

## Pre-Change Validation

pytest backend/tests: 295 passed, 4 warnings（基线）。ruff check: 修改前已有 lint 噪音 1024 条。mypy 排除 skills/ 后通过。当前 skills_dir 单目录架构，skills_user_dir 字段不存在。


## Post-Change Validation

pytest backend/tests: 295 passed, 4 warnings。双目录加载验证通过：DirectorySkillLoader 加载 19 技能（1 内置 + 18 用户）。ruff check 修改文件通过。mypy 无新增错误。调用路径验证：orchestration_service → create_runtime_registry → skills_dirs → CacheSkillLoader 链路完整。


## Closure Summary

待补充

## References

- **Commits**: 待补充
- **Plan**: 待补充

## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
