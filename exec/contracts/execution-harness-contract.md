# Execution Harness Contract Spec

## 1. 三处初始化重复的职责交叉矩阵

> 结论先行：当前主路径同时存在两套“确保可执行环境就绪”的 owner：启动期是 `LifecycleService.initialize()`，执行期是 `DockerExecutor._ensure_docker_environment()`；`ContainerManager.ensure_running()` 具备第三套等价职责，但当前未见主路径接入。证据：`backend/alice/cli/main.py:153-171`、`backend/alice/application/agent/agent.py:104-107`、`backend/alice/application/services/orchestration_service.py:138-151`、`backend/alice/infrastructure/docker/container_manager.py:64-105`。

| 职责 | LifecycleService | DockerExecutor | ContainerManager |
|------|------------------|----------------|------------------|
| 容器创建 | `_create_and_start_container()` 创建并启动新容器，且显式补挂载目录与 `-v` 挂载参数（`backend/alice/application/services/lifecycle_service.py:398-433`） | `_ensure_container_running()` 在容器不存在时直接 `docker run -d --name ...` 创建容器，但未挂载 `DockerConfig.default_mounts`（`backend/alice/domain/execution/executors/docker_executor.py:430-506`） | `_create_and_start()` 委托 `self.client.run_container()` 创建容器（`backend/alice/infrastructure/docker/container_manager.py:118-141`），实际 `docker run` 参数由 `DockerClient.run_container()` + `DockerCommand.container_run()` 生成（`backend/alice/infrastructure/docker/client.py:303-325`、`backend/alice/infrastructure/docker/client.py:106-136`） |
| 镜像构建 | `_ensure_docker_image()` 检查镜像，不存在时进入 `_build_docker_image()` 自动构建（`backend/alice/application/services/lifecycle_service.py:244-270`、`backend/alice/application/services/lifecycle_service.py:272-341`） | `_ensure_docker_image()` 只做 `docker image inspect`；缺镜像时直接抛错，要求手工 `docker build`，不自动构建（`backend/alice/domain/execution/executors/docker_executor.py:387-428`） | `ensure_running()` 在阶段 2 调用 `self.image_builder.ensure_image()`（`backend/alice/infrastructure/docker/container_manager.py:90-94`）；`ImageBuilder.ensure_image()` 负责“存在则跳过，不存在则构建”（`backend/alice/infrastructure/docker/image_builder.py:46-75`） |
| 健康检查 | Docker 引擎检查由 `_check_docker_engine()` 完成；容器状态检查由 `_get_container_status()` 完成（`backend/alice/application/services/lifecycle_service.py:196-243`、`backend/alice/application/services/lifecycle_service.py:369-396`） | Docker 引擎检查由 `_check_docker_engine()` 完成；容器状态检查内嵌在 `_ensure_container_running()`；另有 `is_container_ready()`（`backend/alice/domain/execution/executors/docker_executor.py:334-386`、`backend/alice/domain/execution/executors/docker_executor.py:430-467`、`backend/alice/domain/execution/executors/docker_executor.py:537-548`） | `get_status()` / `is_running()` 负责状态判断（`backend/alice/infrastructure/docker/container_manager.py:47-62`），底层解析由 `DockerClient.get_container_status()` + `ContainerStatus.from_docker_output()` 完成（`backend/alice/infrastructure/docker/client.py:247-259`、`backend/alice/infrastructure/docker/config.py:126-143`） |
| ensure_running | `initialize()` 串行执行 `_check_docker_engine()` → `_ensure_docker_image()` → `_ensure_container_running()`（`backend/alice/application/services/lifecycle_service.py:132-194`） | `_ensure_docker_environment()` 串行执行 `_check_docker_engine()` → `_ensure_docker_image()` → `_ensure_container_running()`（`backend/alice/domain/execution/executors/docker_executor.py:278-332`） | `ensure_running()` 串行执行 `check_engine()` → `ensure_image()` → `get_status()` / `_create_and_start()` / `_start_existing()`（`backend/alice/infrastructure/docker/container_manager.py:64-105`） |
| 容器清理 | `stop_container()`、`remove_container()`、`shutdown()`；但 `shutdown()` 明确“不删除容器，保持容器持久化”（`backend/alice/application/services/lifecycle_service.py:453-523`） | 无显式 stop/remove API；仅维护 `_docker_environment_ready` 本地标志（`backend/alice/domain/execution/executors/docker_executor.py:49`、`backend/alice/domain/execution/executors/docker_executor.py:278-297`） | `stop()`、`restart()`、`remove()` 提供完整容器清理接口（`backend/alice/infrastructure/docker/container_manager.py:179-224`） |
| 命令执行 | 无；该类只做生命周期管理，未暴露容器内 exec（`backend/alice/application/services/lifecycle_service.py:20-27`） | `execute()` → `BaseExecutor.execute()` → `_do_execute()`；实际命令由 `_build_docker_command()` 构造并通过 `subprocess.run()` 执行（`backend/alice/domain/execution/executors/docker_executor.py:110-120`、`backend/alice/domain/execution/executors/docker_executor.py:126-255`、`backend/alice/domain/execution/executors/docker_executor.py:256-276`） | `exec()` / `exec_bash()` / `exec_python()` 通过 `DockerClient.exec_command()` 执行（`backend/alice/infrastructure/docker/container_manager.py:226-275`、`backend/alice/infrastructure/docker/client.py:356-392`） |

### 交叉点摘要

1. 三者都覆盖了“引擎检查 / 镜像检查 / 容器存在性判断 / 启动或创建”这一初始化骨架，只是实现位置不同（`backend/alice/application/services/lifecycle_service.py:153-161`、`backend/alice/domain/execution/executors/docker_executor.py:289-297`、`backend/alice/infrastructure/docker/container_manager.py:84-105`）。
2. 其中只有 `LifecycleService` 与 `ContainerManager` 会按 `DockerConfig.default_mounts` 创建挂载；`DockerExecutor` 自建容器时没有挂载逻辑，造成 contract 不一致（`backend/alice/infrastructure/docker/config.py:80-100`、`backend/alice/application/services/lifecycle_service.py:400-420`、`backend/alice/infrastructure/docker/client.py:309-324`、`backend/alice/domain/execution/executors/docker_executor.py:472-493`）。
3. 只有 `ContainerManager` 把 Docker CLI 构造下沉到 `DockerClient` / `DockerCommand`；`LifecycleService` 和 `DockerExecutor` 仍直接拼 subprocess 命令，导致 host-side contract 分裂（`backend/alice/infrastructure/docker/client.py:60-172`、`backend/alice/application/services/lifecycle_service.py:198-207`、`backend/alice/domain/execution/executors/docker_executor.py:336-351`）。

---

## 2. 调用链路图

### 2.1 启动期：主路径如何预热 Docker 环境

```text
cli/main.py
  -> LifecycleService(project_root=...)
  -> AliceAgent(..., lifecycle_service=lifecycle)
  -> AliceAgent.__init__()
  -> LifecycleService.initialize()
     -> _check_docker_engine()
     -> _ensure_docker_image()
     -> _ensure_container_running()
```

- CLI 主入口实例化 `LifecycleService` 并注入 `AliceAgent`（`backend/alice/cli/main.py:153-171`）。
- `AliceAgent.__init__()` 构造时立即调用 `self.lifecycle.initialize()`，所以容器预热发生在 agent 启动期，而不是第一次工具执行时（`backend/alice/application/agent/agent.py:104-107`）。

### 2.2 运行期主链：从 workflow / agent 到容器内命令执行

```text
AliceAgent.process(request)
  -> WorkflowChain.process(workflow_context)
     -> ChatWorkflow.execute(workflow_context)
        -> FunctionCallingOrchestrator.execute_tool_calls(tool_calls)
           -> ExecutionService.execute_tool_call(invocation)
              -> ExecutionService.execute(command, is_python_code)
                 -> DockerExecutor.execute(command, is_python_code)
                    -> BaseExecutor.execute(command, is_python_code)
                       -> DockerExecutor._do_execute(Command)
                          -> DockerExecutor._ensure_docker_environment()
                          -> DockerExecutor._build_docker_command()
                          -> subprocess.run(["docker", "exec", ...])
                          -> ExecutionResult.from_subprocess(...)
              -> ToolResultPayload / ToolExecutionResult
        -> ChatMessage.tool(content=tool_message_content()) 回注模型
```

#### 分层接口与进出 contract

1. **Agent 层**：`AliceAgent.process()` 创建 `WorkflowContext`，再交给 `WorkflowChain.process()` 分发（`backend/alice/application/agent/agent.py:125-197`、`backend/alice/application/workflow/base_workflow.py:126-141`）。
2. **Workflow 层**：`ChatWorkflow.execute()` 从流式响应中聚合 `tool_calls`，若检测到工具调用则进入 `FunctionCallingOrchestrator.execute_tool_calls()`（`backend/alice/application/workflow/chat_workflow.py:242-243`、`backend/alice/application/workflow/chat_workflow.py:580-677`）。
3. **Tool Orchestrator 层**：`FunctionCallingOrchestrator.execute_tool_calls()` 把 OpenAI 风格 `tool_call` 转为 `ToolInvocation`，逐个调用 `ExecutionService.execute_tool_call()`；失败时降级包装为 `ToolExecutionResult`（`backend/alice/application/workflow/function_calling_orchestrator.py:39-117`）。
4. **Execution Service 层**：
   - `execute_tool_call()` 负责参数校验与 `run_bash` / `run_python` 路由（`backend/alice/domain/execution/services/execution_service.py:465-492`）。
   - `execute()` 负责安全检查、宿主机 builtin 拦截，以及普通命令转发给 executor（`backend/alice/domain/execution/services/execution_service.py:264-455`）。
5. **Executor 层**：`DockerExecutor.execute()` 透传到 `BaseExecutor.execute()`；后者构造 `Command`、做规则校验，再调用 `_do_execute()`（`backend/alice/domain/execution/executors/docker_executor.py:110-120`、`backend/alice/domain/execution/executors/base.py:87-119`）。
6. **Docker Harness 层**：`DockerExecutor._do_execute()` 在真正执行前会再做一次 `_ensure_docker_environment()`，随后调用 `subprocess.run(full_command, shell=False, ...)` 执行 `docker exec`（`backend/alice/domain/execution/executors/docker_executor.py:138-177`）。
7. **结果回注层**：
   - 原始执行结果是 `ExecutionResult`（`backend/alice/domain/execution/models/execution_result.py:22-114`）。
   - 结构化工具结果被包装成 `ToolResultPayload` + `ToolExecutionResult`，再通过 `ChatMessage.tool(content=json)` 写回消息历史（`backend/alice/domain/execution/models/tool_calling.py:188-224`、`backend/alice/application/workflow/function_calling_orchestrator.py:105-111`）。

### 2.3 运行期旁路：直接工具工作流

除结构化 tool calling 主链外，还存在一个直接旁路：

```text
ToolWorkflow.execute(..., command, is_python)
  -> ExecutionService.execute(...)
  -> DockerExecutor.execute(...)
  -> docker exec
```

证据：`backend/alice/application/workflow/tool_workflow.py:53-82`、`backend/alice/domain/execution/services/execution_service.py:264-455`、`backend/alice/domain/execution/executors/docker_executor.py:126-177`。

### 2.4 当前主路径的 owner 分裂

- 启动期 owner：`LifecycleService`（`backend/alice/cli/main.py:153-171`、`backend/alice/application/agent/agent.py:104-107`）。
- 执行期 owner：`DockerExecutor`，由 `OrchestrationService.create_from_config()` 直接实例化后注入 `ExecutionService`（`backend/alice/application/services/orchestration_service.py:134-151`）。
- 第三套 owner：`ContainerManager` 具备同类能力，但当前未见业务侧实例化；代码内仅见类定义及其内部 `ImageBuilder` 注入（`backend/alice/infrastructure/docker/container_manager.py:25-45`）。

---

## 3. Tool Schema / Tool Result 统一出口

### 3.1 `tool_registry` 如何注册和查找 tool

#### 注册

- `ToolRegistry.__init__()` 在 `_tools` 中硬编码注册两个 function-calling tool：
  - `run_bash`
  - `run_python`
  证据：`backend/alice/domain/execution/services/tool_registry.py:19-56`。
- 两个 tool 都以 `ToolSchemaDefinition` 表示，并携带 JSON Schema 参数定义与 `metadata.execution_environment="docker"`（`backend/alice/domain/execution/services/tool_registry.py:22-55`）。

#### 查找 / 暴露

- `list_tools()` 返回内部 `ToolSchemaDefinition` 列表（`backend/alice/domain/execution/services/tool_registry.py:61-62`）。
- `list_openai_tools()` 将其转成 OpenAI function calling 所需的 `{"type": "function", "function": ...}` 结构（`backend/alice/domain/execution/services/tool_registry.py:64-65`，转换实现见 `backend/alice/domain/execution/models/tool_calling.py:108-117`）。
- `get_tool()` / `require_tool()` 负责按名称查找；不存在时抛 `UnknownToolError`（`backend/alice/domain/execution/services/tool_registry.py:67-74`）。
- `validate_tool_arguments()` 统一调用 `ToolSchemaDefinition.parse_and_validate_arguments()` 做 JSON 解析、required 检查和 `additionalProperties` 校验（`backend/alice/domain/execution/services/tool_registry.py:76-81`、`backend/alice/domain/execution/models/tool_calling.py:118-152`）。
- `snapshot()` 额外把 builtin 命令、skills、terminal、code execution 四类工具打平为 `ToolRegistrySnapshot`，供 runtime context / docs / UI 侧读取（`backend/alice/domain/execution/services/tool_registry.py:86-123`）。

### 3.2 `tool_calling.py` 中的 schema 定义

`backend/alice/domain/execution/models/tool_calling.py` 实际承载了四类 contract：

1. **工具描述 contract**：`ToolDescriptor`、`ToolRegistrySnapshot`（`backend/alice/domain/execution/models/tool_calling.py:40-86`）。
2. **模型暴露 schema**：`ToolSchemaDefinition`，可转 `ToolDescriptor`、可转 OpenAI tool、可做参数校验（`backend/alice/domain/execution/models/tool_calling.py:88-152`）。
3. **模型发起调用 contract**：`ToolInvocation`，从 provider 返回的 `tool_call` 反序列化而来（`backend/alice/domain/execution/models/tool_calling.py:155-186`）。
4. **结果回注 contract**：`ToolResultPayload` + `ToolExecutionResult`，前者是回给模型的 payload，后者把 `ToolInvocation`、`ToolResultPayload` 与底层 `ExecutionResult` 绑定在一起（`backend/alice/domain/execution/models/tool_calling.py:188-224`）。

### 3.3 `execution_result.py` 中的结果定义

- `ExecutionStatus` 统一了 `success/failure/timeout/interrupted/blocked` 五种状态（`backend/alice/domain/execution/models/execution_result.py:13-20`）。
- `ExecutionResult` 是底层执行结果主模型，字段包括：
  - `success`
  - `output`
  - `status`
  - `error`
  - `exit_code`
  - `execution_time`
  - `timestamp`
  - `metadata`
  证据：`backend/alice/domain/execution/models/execution_result.py:22-36`。
- `from_subprocess()`、`blocked_result()`、`timeout_result()` 等工厂方法，用于把 subprocess / security / timeout 场景折叠成统一返回值（`backend/alice/domain/execution/models/execution_result.py:38-101`）。

### 3.4 是否有统一 envelope：结论是“只有局部统一，没有全链统一”

#### 已统一的部分

- **底层命令执行结果**：`ExecutionResult` 是 docker exec 的统一底层结果（`backend/alice/domain/execution/models/execution_result.py:22-114`）。
- **结构化工具结果**：`ExecutionService._coerce_tool_result()` 会把 `ExecutionResult | str` 折叠成 `ToolExecutionResult`（`backend/alice/domain/execution/services/execution_service.py:112-142`）。

#### 未统一的部分

1. **执行入口仍有双返回制**：`ExecutionService.execute()` 返回 `ExecutionResult | str`，为了兼容旧接口，在成功场景常直接返回 `result.output` 字符串（`backend/alice/domain/execution/services/execution_service.py:264-279`、`backend/alice/domain/execution/services/execution_service.py:406-455`）。
2. **tool result 回注给模型时又变成 JSON string**：`ToolExecutionResult.tool_message_content()` 会把 `ToolResultPayload` 再 `json.dumps()` 成字符串（`backend/alice/domain/execution/models/tool_calling.py:220-223`）。
3. **接口层还有重复 `ExecutionResult` 定义**：`backend/alice/core/interfaces/command_executor.py:12-19` 重新定义了一份简化版 `ExecutionResult`，与 domain 层 `ExecutionResult` 不是同一个类型（`backend/alice/domain/execution/models/execution_result.py:22-36`）。
4. **Executor 协议重复**：`backend/alice/core/interfaces/command_executor.py:31-52` 与 `backend/alice/domain/execution/executors/base.py:15-62` 各自维护一份 `CommandExecutor` 协议。

#### 判断

因此当前不是“一个统一 envelope 贯穿 agent → workflow → execution → tool result”，而是多层分散表示：

- provider/tool schema：`ToolSchemaDefinition`（`backend/alice/domain/execution/models/tool_calling.py:88-152`）
- invocation：`ToolInvocation`（`backend/alice/domain/execution/models/tool_calling.py:155-186`）
- execution：`ExecutionResult`（`backend/alice/domain/execution/models/execution_result.py:22-114`）
- model 回注：`ToolResultPayload` / `ToolExecutionResult` / JSON string（`backend/alice/domain/execution/models/tool_calling.py:188-224`）
- legacy compatibility：`str`（`backend/alice/domain/execution/services/execution_service.py:269-279`）

---

## 4. Sandbox Provider Seam 最小接口设计建议

> 目标不是再加第四套实现，而是让 `LifecycleService` 与 `ExecutionService/DockerExecutor` 共享同一个 backend seam。职责依据：当前三处实现都重复了 `check engine -> ensure image -> ensure container -> exec` 主流程（`backend/alice/application/services/lifecycle_service.py:153-161`、`backend/alice/domain/execution/executors/docker_executor.py:289-297`、`backend/alice/infrastructure/docker/container_manager.py:84-105`）。

### 4.1 最小方法集

建议统一成一个 `SandboxProvider` / `ExecutionBackend` 协议，最小只暴露 5 个方法：

1. `ensure_ready(...) -> SandboxStatus`
2. `exec(command: Command, *, log_context: dict | None = None) -> ExecutionResult`
3. `status() -> SandboxStatus`
4. `interrupt() -> bool`
5. `cleanup(*, remove: bool = False, force: bool = False) -> bool`

### 4.2 每个方法的输入 / 输出类型建议

#### 1) `ensure_ready`

```python
ensure_ready(
    *,
    force_rebuild: bool = False,
    on_build_progress: Callable[[str], None] | None = None,
) -> SandboxStatus
```

- **输入**：
  - `force_rebuild`：是否强制重建镜像
  - `on_build_progress`：可选构建日志回调
- **输出**：`SandboxStatus`
  - 可沿用 `ContainerStatus` 语义并补足 `image_ready` / `engine_ready`（现有基础可参考 `backend/alice/infrastructure/docker/config.py:112-143`）
- **理由**：当前 `LifecycleService.initialize()`、`DockerExecutor._ensure_docker_environment()`、`ContainerManager.ensure_running()` 都在做这个动作，应收口成唯一入口（`backend/alice/application/services/lifecycle_service.py:132-194`、`backend/alice/domain/execution/executors/docker_executor.py:278-332`、`backend/alice/infrastructure/docker/container_manager.py:64-105`）。

#### 2) `exec`

```python
exec(
    command: Command,
    *,
    log_context: dict[str, Any] | None = None,
) -> ExecutionResult
```

- **输入**：直接复用现有 `Command` 模型（`backend/alice/domain/execution/models/command.py:27-35`）
- **输出**：统一返回 domain 层 `ExecutionResult`，不再返回裸字符串（`backend/alice/domain/execution/models/execution_result.py:22-36`）
- **理由**：当前 `ExecutionService.execute()` 还保留 `ExecutionResult | str` 双态，导致 tool result、workflow、legacy 调用方 contract 分裂（`backend/alice/domain/execution/services/execution_service.py:264-279`）。

#### 3) `status`

```python
status() -> SandboxStatus
```

- **输入**：无
- **输出**：统一环境状态对象
- **理由**：当前 `LifecycleService._get_container_status()`、`DockerExecutor.is_container_ready()`、`ContainerManager.get_status()/is_running()` 分散存在（`backend/alice/application/services/lifecycle_service.py:369-396`、`backend/alice/domain/execution/executors/docker_executor.py:537-548`、`backend/alice/infrastructure/docker/container_manager.py:47-62`）。

#### 4) `interrupt`

```python
interrupt() -> bool
```

- **输入**：无
- **输出**：是否成功发起中断
- **理由**：agent 侧已经把中断一路传播到 `execution_service.interrupt()`（`backend/alice/application/agent/agent.py:350-353`），backend seam 应承接这一 contract。

#### 5) `cleanup`

```python
cleanup(*, remove: bool = False, force: bool = False) -> bool
```

- **输入**：
  - `remove=False`：默认只停，不删
  - `force=False`：必要时强制删除
- **输出**：布尔成功标记
- **理由**：当前清理语义被拆在 `LifecycleService.stop_container/remove_container/shutdown()` 与 `ContainerManager.stop/remove()` 两套接口里（`backend/alice/application/services/lifecycle_service.py:453-523`、`backend/alice/infrastructure/docker/container_manager.py:179-224`）。

### 4.3 哪些职责应该内聚到 backend 内部

以下职责不应继续散落在 `LifecycleService`、`DockerExecutor`、`ContainerManager` 三处，而应只保留在 backend 内部：

1. **Docker 引擎检查**（当前重复于三处）（`backend/alice/application/services/lifecycle_service.py:196-243`、`backend/alice/domain/execution/executors/docker_executor.py:334-386`、`backend/alice/infrastructure/docker/client.py:221-236`）。
2. **镜像存在性检查与构建策略**（当前一处自动构建、一处委托构建、一处只报错）（`backend/alice/application/services/lifecycle_service.py:244-341`、`backend/alice/infrastructure/docker/image_builder.py:46-132`、`backend/alice/domain/execution/executors/docker_executor.py:387-428`）。
3. **挂载目录准备与 `docker run` 参数构造**（当前只有 `LifecycleService` / `ContainerManager` 会带 `default_mounts`，`DockerExecutor` 不会）（`backend/alice/infrastructure/docker/config.py:80-100`、`backend/alice/application/services/lifecycle_service.py:400-420`、`backend/alice/infrastructure/docker/client.py:309-324`、`backend/alice/domain/execution/executors/docker_executor.py:472-493`）。
4. **容器状态探测、创建、启动、停止、删除**（当前三套 owner 重复）（`backend/alice/application/services/lifecycle_service.py:342-500`、`backend/alice/domain/execution/executors/docker_executor.py:430-548`、`backend/alice/infrastructure/docker/container_manager.py:97-224`）。
5. **Docker CLI 命令构建与 subprocess 错误折叠**（当前 `DockerClient/DockerCommand` 有一套，但 `LifecycleService` / `DockerExecutor` 又绕过它）（`backend/alice/infrastructure/docker/client.py:60-172`、`backend/alice/application/services/lifecycle_service.py:198-207`、`backend/alice/domain/execution/executors/docker_executor.py:336-351`）。

### 4.4 上层该保留什么

- `LifecycleService` 应退化为“应用生命周期编排者”，只调用 `backend.ensure_ready()` / `backend.cleanup()`，不再自行拼 Docker CLI（现状相反，见 `backend/alice/application/services/lifecycle_service.py:132-194`）。
- `ExecutionService` 应只负责：
  - 安全审查
  - builtin 路由
  - tool schema 参数校验
  - 调 backend `exec()`
  不应再持有一份自初始化的 Docker owner（现状为 `self.executor = executor or DockerExecutor()`，见 `backend/alice/domain/execution/services/execution_service.py:39-45`）。

---

## 5. 发现的问题与建议

### 5.1 职责交叉的具体风险

#### 问题 1：主路径有两个有效 owner，第三个 owner 处于旁路状态

- 启动期由 `LifecycleService` 初始化环境（`backend/alice/cli/main.py:153-171`、`backend/alice/application/agent/agent.py:104-107`）。
- 执行期 `DockerExecutor` 仍会在第一次执行时再次 `_ensure_docker_environment()`（`backend/alice/domain/execution/executors/docker_executor.py:138-140`、`backend/alice/domain/execution/executors/docker_executor.py:278-297`）。
- `ContainerManager.ensure_running()` 具备第三套同类 contract，但当前未接到主路径（`backend/alice/infrastructure/docker/container_manager.py:64-105`）。

**风险**：同一容器初始化职责被多个对象持有，本地状态位 `_initialized`、`_container_running`、`_docker_environment_ready` 可能彼此漂移（`backend/alice/application/services/lifecycle_service.py:42-43`、`backend/alice/domain/execution/executors/docker_executor.py:49`）。

**建议**：收口成单一 backend owner，其他层只调 seam，不再各自维护 ready flag。

#### 问题 2：镜像策略不一致

- `LifecycleService`：缺镜像自动构建（`backend/alice/application/services/lifecycle_service.py:244-341`）。
- `ContainerManager`：缺镜像自动构建（`backend/alice/infrastructure/docker/container_manager.py:90-94`、`backend/alice/infrastructure/docker/image_builder.py:46-75`）。
- `DockerExecutor`：缺镜像直接抛错，要求用户手工 build（`backend/alice/domain/execution/executors/docker_executor.py:424-428`）。

**风险**：同一“ensure ready”语义，在不同入口会得到不同结果；启动能成功不代表运行期自恢复也能成功。

**建议**：把镜像策略统一下沉到 backend `ensure_ready()` 内部。

#### 问题 3：容器创建参数不一致，尤其是挂载 contract 不一致

- `DockerConfig.default_mounts` 明确定义应挂载 `skills/` 与宿主机 `.alice/workspace/`（容器内仍映射到 `/app/alice_output`）（`backend/alice/infrastructure/docker/config.py:80-100`）。
- `LifecycleService._create_and_start_container()` 会遍历 `default_mounts` 添加 `-v`（`backend/alice/application/services/lifecycle_service.py:400-420`）。
- `ContainerManager` 最终通过 `DockerClient.run_container()` 也会带上这些挂载（`backend/alice/infrastructure/docker/client.py:309-324`）。
- `DockerExecutor._ensure_container_running()` 自建容器时完全没有挂载逻辑（`backend/alice/domain/execution/executors/docker_executor.py:472-493`）。

**风险**：同名容器在不同入口下可能拥有不同挂载视图，导致技能文件、输出目录、后续 tool contract 出现隐式差异。

**建议**：只保留一套 `docker run` 参数构造路径，禁止 executor 自己裸拼创建命令。

### 5.2 不一致的错误处理

#### 问题 4：异常与结果模型混用

- `LifecycleService` 主要抛 `RuntimeError`（`backend/alice/application/services/lifecycle_service.py:228-242`、`backend/alice/application/services/lifecycle_service.py:287`、`backend/alice/application/services/lifecycle_service.py:332`）。
- `ContainerManager` / `ImageBuilder` / `DockerClient` 使用各自异常类型：`ContainerManagerError`、`ImageBuildError`、`DockerClientError`（`backend/alice/infrastructure/docker/container_manager.py:19-22`、`backend/alice/infrastructure/docker/image_builder.py:18-21`、`backend/alice/infrastructure/docker/client.py:48-57`）。
- `DockerExecutor` 在命令执行阶段更多返回 `ExecutionResult`，但初始化阶段仍抛异常（`backend/alice/domain/execution/executors/docker_executor.py:201-254`、`backend/alice/domain/execution/executors/docker_executor.py:311-332`）。
- `ExecutionService.execute()` 还会直接返回字符串，尤其是安全阻断与 legacy compatibility 场景（`backend/alice/domain/execution/services/execution_service.py:299-323`、`backend/alice/domain/execution/services/execution_service.py:406-455`）。

**风险**：调用方很难仅靠类型判断区分“初始化失败 / 命令失败 / 安全阻断 / tool 参数错误”。

**建议**：上层只消费 `ExecutionResult` / `ToolExecutionResult`；backend 内部异常统一折叠为单一错误族，再由上层包装成 response。

#### 问题 5：接口层重复定义 `ExecutionResult` 与 `CommandExecutor`

- `backend/alice/core/interfaces/command_executor.py:12-19` 定义了简化版 `ExecutionResult`。
- `backend/alice/domain/execution/models/execution_result.py:22-36` 定义了真正运行时使用的 `ExecutionResult`。
- `backend/alice/core/interfaces/command_executor.py:31-52` 与 `backend/alice/domain/execution/executors/base.py:15-62` 各维护一份 `CommandExecutor` 协议。

**风险**：静态接口与运行时模型分叉，未来替换 backend 时容易出现“类型兼容但语义不兼容”的假统一。

**建议**：删掉重复协议或让 core 直接依赖 domain 合法 contract。

### 5.3 资源泄漏与运行时占用风险

#### 问题 6：中断语义不能终止正在运行的 subprocess

- `BaseExecutor.interrupt()` 只是把 `_interrupted` 设为 `True`（`backend/alice/domain/execution/executors/base.py:147-154`）。
- `DockerExecutor` 真正执行命令时调用的是同步 `subprocess.run(...)`，没有保存 process handle，也没有 kill 逻辑（`backend/alice/domain/execution/executors/docker_executor.py:162-169`）。
- Agent 的中断最终只会传播到 `execution_service.interrupt()` / `executor.interrupt()`（`backend/alice/application/agent/agent.py:350-353`、`backend/alice/domain/execution/services/execution_service.py:623-625`）。

**风险**：长命令一旦开始，用户中断只能阻止下一次执行，不能取消当前 `docker exec`；资源会继续被容器和宿主机进程占用，直到命令自然结束或超时。

**建议**：backend seam 需要把“运行中命令句柄”纳入 contract，至少能对当前 exec 发出 kill / cancel。

#### 问题 7：shutdown 不回收容器，状态位也未统一复位

- `LifecycleService.shutdown()` 明确不删除容器，只重置 `_initialized=False`（`backend/alice/application/services/lifecycle_service.py:502-523`）。
- `LifecycleService._container_running` 不在 `shutdown()` 中重置（`backend/alice/application/services/lifecycle_service.py:520`）。
- 另一侧 `DockerExecutor` 只维护 `_docker_environment_ready`，与 lifecycle 状态互不关联（`backend/alice/domain/execution/executors/docker_executor.py:49`、`backend/alice/domain/execution/executors/docker_executor.py:297`）。

**风险**：容器持久化本身不是问题，但“容器真实状态”与“多个 owner 的本地标志位”可能脱节，表现为假 ready / 假 running。

**建议**：将本地 ready flag 最小化，统一以 backend.status() 的实时探测为准。

### 5.4 其它 contract 漂移

#### 问题 8：`Command.to_docker_command()` 疑似陈旧实现

- `Command.to_docker_command()` 构造的 `docker exec` 命令缺少容器名参数（`backend/alice/domain/execution/models/command.py:59-71`）。
- 当前真正被使用的是 `DockerExecutor._build_docker_command()`（`backend/alice/domain/execution/executors/docker_executor.py:256-276`）与 `DockerCommand.container_exec()`（`backend/alice/infrastructure/docker/client.py:158-172`）。

**风险**：如果未来有人误用 `Command.to_docker_command()`，会得到无效命令；这说明 command model 与 backend command builder 已经漂移。

**建议**：删除陈旧 helper，或让 `Command` 只保留数据，不再负责拼接 backend-specific CLI。

#### 问题 9：host-side Docker 调用安全风格不一致

- `DockerClient._run()` 使用 `shell=False` + list argv（`backend/alice/infrastructure/docker/client.py:189-220`）。
- `DockerExecutor` 的若干 host-side probe 仍使用 `shell=True` + 字符串命令（`backend/alice/domain/execution/executors/docker_executor.py:347-351`、`backend/alice/domain/execution/executors/docker_executor.py:401-405`、`backend/alice/domain/execution/executors/docker_executor.py:446-450`、`backend/alice/domain/execution/executors/docker_executor.py:540-545`）。

**风险**：同一 execution harness 的 host 命令风格不一致，增加维护和审计成本。

**建议**：全部通过统一 command builder + `shell=False` 执行。

---

## 总结

当前 execution harness 的真实格局是：

1. **主路径已接入的只有两套 owner**：`LifecycleService`（启动期）和 `DockerExecutor`（执行期）（`backend/alice/cli/main.py:153-171`、`backend/alice/application/services/orchestration_service.py:138-151`）。
2. **`ContainerManager` / `ImageBuilder` 更像未接主路径的基础设施旁路**，但它们反而承载了更完整、更一致的 Docker client contract（`backend/alice/infrastructure/docker/container_manager.py:64-105`、`backend/alice/infrastructure/docker/client.py:60-172`）。
3. **最值得优先统一的不是 exec 本身，而是 `ensure_ready()`**：因为目前三处重复最严重、差异也最大，尤其体现在镜像构建策略、挂载 contract 和错误处理上（`backend/alice/application/services/lifecycle_service.py:153-161`、`backend/alice/domain/execution/executors/docker_executor.py:289-297`、`backend/alice/infrastructure/docker/container_manager.py:84-105`）。
