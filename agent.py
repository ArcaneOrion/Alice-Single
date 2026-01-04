import re
import subprocess
import os
import sys
import logging
from datetime import datetime, timedelta
from openai import OpenAI
import config
from snapshot_manager import SnapshotManager

# 配置运行时日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileClipHandler('alice_runtime.log', mode='a', encoding='utf-8') if hasattr(logging, 'FileClipHandler') else logging.FileHandler('alice_runtime.log', mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger("AliceAgent")

class AliceAgent:
    def __init__(self, model_name=None, prompt_path=None):
        logger.info(f"正在初始化 AliceAgent (模型: {model_name or config.MODEL_NAME})")
        self.model_name = model_name or config.MODEL_NAME
        self.prompt_path = prompt_path or config.DEFAULT_PROMPT_PATH
        self.memory_path = config.MEMORY_FILE_PATH
        self.todo_path = config.TODO_FILE_PATH
        self.stm_path = config.SHORT_TERM_MEMORY_FILE_PATH
        self.working_memory_path = config.WORKING_MEMORY_FILE_PATH
        self.client = OpenAI(
            base_url=config.BASE_URL,
            api_key=config.API_KEY
        )
        self.messages = []
        
        # 权限与路径安全
        self.project_root = os.getcwd() 
        
        # 容器执行引擎配置 (常驻容器模式)
        self.docker_image = "alice-sandbox:latest"
        self.container_name = "alice-sandbox-instance"
        self._ensure_docker_environment()
        
        # 内存快照管理器
        self.snapshot_mgr = SnapshotManager()
        self.interrupted = False
        
        # 确保输出目录存在
        os.makedirs(config.ALICE_OUTPUT_DIR, exist_ok=True)
        
        # 启动时管理记忆（滚动与提炼）
        self.manage_memory()
        
        self._refresh_context()

    def _ensure_docker_environment(self):
        """确保 Docker 环境就绪，实现核心隔离与自动化唤醒"""
        try:
            # 1. 检查 Docker 引擎
            res = subprocess.run("docker --version", shell=True, capture_output=True)
            if res.returncode != 0:
                print("错误: 系统未检测到 Docker。Alice 需要 Docker 环境来确保执行安全与持久化。")
                sys.exit(1)
            
            # 2. 检查并自动构建镜像
            res = subprocess.run(f"docker image inspect {self.docker_image}", shell=True, capture_output=True)
            if res.returncode != 0:
                print(f"[系统]: 未找到 Docker 镜像 {self.docker_image}，正在启动全自动构建流程...")
                print(f"[系统]: 这可能需要几分钟，请稍候...")
                build_cmd = f"docker build -t {self.docker_image} -f Dockerfile.sandbox ."
                # 实时输出构建进度
                process = subprocess.Popen(build_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in process.stdout:
                    print(f"  [Docker Build]: {line.strip()}")
                process.wait()
                
                if process.returncode != 0:
                    print(f"错误: Docker 镜像构建失败。请检查 Dockerfile.sandbox 或网络连接。")
                    sys.exit(1)
                print(f"[系统]: 镜像 {self.docker_image} 构建成功。")

            # 3. 检查/启动常驻容器 (最小化权限挂载模式)
            res = subprocess.run(f"docker ps -a --filter name={self.container_name} --format '{{{{.Status}}}}'", shell=True, capture_output=True, text=True)
            status = res.stdout.lower()

            if not status:
                # 确保关键目录存在 (用于物理隔离挂载)
                os.makedirs(os.path.join(self.project_root, "skills"), exist_ok=True)
                os.makedirs(config.ALICE_OUTPUT_DIR, exist_ok=True)

                print(f"[系统]: 正在初始化 Alice 常驻实验室容器 (最小权限隔离模式)...")
                start_cmd = [
                    "docker", "run", "-d",
                    "--name", self.container_name,
                    "--restart", "always",
                    # 仅同步技能库和输出目录，隔离记忆、人设及源代码
                    "-v", f"{os.path.join(self.project_root, 'skills')}:/app/skills",
                    "-v", f"{os.path.abspath(config.ALICE_OUTPUT_DIR)}:/app/alice_output",
                    "-w", "/app",
                    self.docker_image,
                    "tail", "-f", "/dev/null"
                ]
                subprocess.run(" ".join(start_cmd), shell=True, check=True)
                print(f"[系统]: 容器已成功初始化。记忆与人设文件已实现物理隔离保护。")
            elif "up" not in status:
                # 容器存在但没运行，启动它
                print(f"[系统]: 正在唤醒 Alice 常驻实验室容器...")
                subprocess.run(f"docker start {self.container_name}", shell=True, check=True)
            
        except Exception as e:
            print(f"初始化 Docker 环境时出错: {e}")
            sys.exit(1)

    def _refresh_context(self):
        """刷新上下文，分离人格设定 (System) 与记忆背景 (User)"""
        logger.info("正在刷新上下文索引...")
        self.system_prompt = self._load_prompt()
        self.memory_content = self._load_file_content(self.memory_path, "暂无长期记忆。")
        self.stm_content = self._load_file_content(self.stm_path, "暂无近期记忆。")
        self.working_memory_content = self._load_file_content(self.working_memory_path, "暂无即时对话背景。")
        self.todo_content = self._load_file_content(self.todo_path, "暂无活跃任务。")
        self.snapshot_mgr.refresh() # 刷新快照
        self.index_text = self.snapshot_mgr.get_index_text()
        
        # 1. 构造 System Message (仅放人格设定和环境信息)
        env_context = (
            f"### 当前运行环境信息\n"
            f"- **宿主机工作目录**: `{self.project_root}`\n"
            f"- **容器工作目录**: `/app` (所有 bash/python 代码均在此执行)\n"
            f"- **挂载映射**: `skills/` -> `/app/skills`, `alice_output/` -> `/app/alice_output`\n"
            f"- **重要规则**: 请始终使用相对路径 (如 `skills/xxx`)，这在宿主机和容器中均通用。\n"
        )

        system_content = (
            f"{self.system_prompt}\n\n"
            f"{env_context}"
        )

        # 2. 构造 Memory Context (作为 User Message 提示模型)
        loaded_files = [
            self.memory_path,
            self.stm_path,
            self.todo_path
        ]
        files_list_str = "\n".join([f"- {f}" for f in loaded_files])

        memory_context_content = (
            f"【记忆与背景信息注入】\n"
            f"以下是你当前存储的记忆和任务状态，请作为后续对话的参考：\n\n"
            f"### 长期记忆 (来自 {self.memory_path})\n{self.memory_content}\n\n"
            f"### 短期记忆 (最近 7 天，来自 {self.stm_path})\n{self.stm_content}\n\n"
            f"### 即时对话背景 (来自 {self.working_memory_path})\n{self.working_memory_content}\n\n"
            f"### 当前任务清单 (来自 {self.todo_path})\n{self.todo_content}\n\n"
            f"### 核心资产索引快照\n{self.index_text}\n\n"
            f"--- 记忆注入结束，请开始/继续你的助理工作 ---"
        )

        # 3. 更新消息序列
        # 保持 messages[0] 为 system, messages[1] 为 memory context
        system_msg = {"role": "system", "content": system_content}
        memory_msg = {"role": "user", "content": memory_context_content}

        if not self.messages:
            self.messages = [system_msg, memory_msg]
        else:
            # 确保前两条是系统和记忆
            self.messages[0] = system_msg
            if len(self.messages) > 1 and self.messages[1].get("role") == "user" and "【记忆与背景信息注入】" in self.messages[1].get("content", ""):
                self.messages[1] = memory_msg
            else:
                # 插入记忆消息
                self.messages.insert(1, memory_msg)

    def _load_prompt(self):
        try:
            if os.path.exists(self.prompt_path):
                with open(self.prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return "你是一个 AI 助手。"
        except Exception as e:
            print(f"加载提示词失败: {e}")
            return "你是一个 AI 助手。"

    def manage_memory(self):
        """管理短期记忆滚动和长期记忆提炼"""
        if not os.path.exists(self.stm_path):
            return

        try:
            with open(self.stm_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            sections = {}
            current_date = None
            
            # 解析日期小节
            for line in lines:
                match = re.match(r'^## (\d{4}-\d{2}-\d{2})', line)
                if match:
                    current_date = match.group(1)
                    sections[current_date] = [line]
                elif current_date:
                    sections[current_date].append(line)

            if not sections:
                return

            # 计算过期日期（7天前）
            sorted_dates = sorted(sections.keys())
            today = datetime.now().date()
            expiry_limit = today - timedelta(days=7)
            
            to_prune = [d for d in sorted_dates if datetime.strptime(d, '%Y-%m-%d').date() < expiry_limit]
            
            if to_prune:
                print(f"[系统]: 发现过期短期记忆 ({len(to_prune)} 天)，正在启动提炼流程...")
                
                # 提取过期内容进行总结
                pruned_content = ""
                for d in to_prune:
                    pruned_content += "\n".join(sections[d]) + "\n"
                
                # 调用 LLM 进行提炼
                distill_prompt = (
                    f"你是一个记忆提炼专家。以下是用户最近 7 天的短期记忆记录：\n\n{content}\n\n"
                    f"请重点分析即将被删除的旧记忆：\n{pruned_content}\n\n"
                    "请根据这 7 天的整体背景，结合旧记忆，提炼出具有长期价值的：\n"
                    "1. 用户的新习惯或偏好变更。\n"
                    "2. 重要的项目决策或里程碑进展。\n"
                    "3. 用户提到的重要个人事实。\n\n"
                    "请以 Markdown 列表格式输出提炼结果，保持简洁。如果没有值得记录的长期价值，请回复“无重要更新”。"
                )
                
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": distill_prompt}]
                )
                summary = response.choices[0].message.content.strip()
                
                if summary and "无重要更新" not in summary:
                    # 写入长期记忆
                    with open(self.memory_path, 'a', encoding='utf-8') as f:
                        f.write(f"\n\n### 自动提炼记忆 ({datetime.now().strftime('%Y-%m-%d')})\n{summary}\n")
                    print("[系统]: 长期记忆已更新。")
                
                # 更新短期记忆 file（移除过期日期）
                remaining_content = lines[0:2] # 保持标题和描述
                for d in sorted_dates:
                    if d not in to_prune:
                        remaining_content.extend(sections[d])
                
                with open(self.stm_path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(remaining_content))
                print(f"[系统]: 已清理过期短期记忆。")

        except Exception as e:
            print(f"记忆管理过程中出错: {e}")

    def _load_file_content(self, path, default_msg):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return content if content.strip() else default_msg
            return default_msg
        except Exception as e:
            print(f"加载文件 {path} 失败: {e}")
            return default_msg

    def handle_update_prompt(self, content):
        """处理内置 update_prompt 指令，在宿主机更新人设文件"""
        try:
            with open(self.prompt_path, "w", encoding="utf-8") as f:
                f.write(content.strip())
            return "已成功更新宿主机人设文件 (prompts/alice.md)。新指令将在下一轮对话生效。"
        except Exception as e:
            return f"更新人设文件失败: {str(e)}"

    def handle_toolkit(self, args):
        """处理内置 toolkit 指令（基于注册机制）"""
        if not args or args[0] == "list":
            skills = self.snapshot_mgr.skills
            if not skills:
                return "当前未注册任何技能。请确保 `skills/` 目录下有正确的 `SKILL.md` 文件。"
            
            skill_list = []
            for name, data in sorted(skills.items()):
                skill_list.append(f"- **{name}**: {data['description']}")
            return "### 可用技能列表 (内存注册表)\n" + "\n".join(skill_list)

        elif args[0] == "info" and len(args) > 1:
            skill_name = args[1]
            skill = self.snapshot_mgr.skills.get(skill_name)
            if not skill:
                return f"技能 '{skill_name}' 未在注册表中。请尝试执行 `toolkit refresh`。"
            
            yaml_content = skill.get("yaml", "").strip()
            if yaml_content:
                return f"### 技能 '{skill_name}' 配置信息 (内存注册表)\n```yaml\n---\n{yaml_content}\n---\n```\n*(提示: 如需完整用法，请直接查看 {skill['path']})*"
            return f"技能 '{skill_name}' 注册信息不完整，缺少元数据。"
        
        elif args[0] == "refresh":
            self.snapshot_mgr.refresh()
            count = len(self.snapshot_mgr.skills)
            return f"技能注册表已刷新，共发现并注册 {count} 个技能。"
            
        return "未知 toolkit 指令。用法: `toolkit list`, `toolkit info <skill_name>`, `toolkit refresh`"

    def handle_todo(self, content):
        """处理内置 todo 指令，在宿主机更新任务清单文件"""
        try:
            with open(self.todo_path, "w", encoding="utf-8") as f:
                f.write(content.strip())
            return "已成功更新宿主机任务清单 (memory/todo.md)。"
        except Exception as e:
            return f"更新任务清单失败: {str(e)}"

    def _update_working_memory(self, user_text, assistant_thinking, assistant_content):
        """更新即时记忆 (Working Memory)，过滤掉代码块，保持最近 N 轮"""
        def filter_code(text):
            if not text: return ""
            # 移除所有代码块
            return re.sub(r'```[\s\S]*?```', '', text).strip()

        clean_user = filter_code(user_text)
        clean_thinking = filter_code(assistant_thinking)
        clean_content = filter_code(assistant_content)

        if not clean_user and not clean_content and not clean_thinking:
            return

        new_entry = f"--- ROUND ---\n"
        if clean_user:
            new_entry += f"USER: {clean_user}\n"
        if clean_thinking:
            new_entry += f"ALICE_THINKING: {clean_thinking}\n"
        if clean_content:
            new_entry += f"ALICE_RESPONSE: {clean_content}\n"
        
        try:
            os.makedirs(os.path.dirname(self.working_memory_path), exist_ok=True)
            content = ""
            if os.path.exists(self.working_memory_path):
                with open(self.working_memory_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            # 分割现有的轮次
            rounds = re.split(r'^--- ROUND ---\n', content, flags=re.MULTILINE)
            rounds = [r.strip() for r in rounds if r.strip()]
            
            rounds.append(new_entry.replace("--- ROUND ---\n", "").strip())
            
            # 保持轮数限制
            max_rounds = config.WORKING_MEMORY_MAX_ROUNDS
            if len(rounds) > max_rounds:
                rounds = rounds[-max_rounds:]
            
            final_content = "# Alice 的即时对话背景 (Working Memory)\n\n"
            for r in rounds:
                final_content += f"--- ROUND ---\n{r}\n\n"
            
            with open(self.working_memory_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
        except Exception as e:
            print(f"更新即时记忆失败: {e}")

    def handle_memory(self, content, target="stm"):
        """处理内置 memory 指令，确保写入宿主机 memory/ 目录"""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        
        target_path = self.stm_path if target == "stm" else self.memory_path
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        # 清洗内容，避免重复的日期前缀
        clean_content = content.strip()
        # 匹配 [2025-12-29] 或 2025-12-29 这种格式
        if re.match(r'^\[?\d{4}-\d{2}-\d{2}\]?', clean_content):
            entry_prefix = "" 
        else:
            entry_prefix = f"[{date_str}] "

        try:
            if target == "stm":
                if not os.path.exists(target_path):
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write("# Alice 的短期记忆 (最近 7 天)\n\n")
                
                with open(target_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                has_date_header = any(line.strip() == f"## {date_str}" for line in lines)
                
                with open(target_path, "a", encoding="utf-8") as f:
                    if not has_date_header:
                        f.write(f"\n## {date_str}\n")
                    f.write(f"- [{time_str}] {clean_content}\n")
                return f"已成功更新短期记忆。"
            else:
                # LTM 经验教训追加逻辑
                if not os.path.exists(target_path):
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write("# Alice 的长期记忆\n")

                with open(target_path, "r", encoding="utf-8") as f:
                    full_text = f.read()

                lessons_header = "## 经验教训"
                entry = f"- {entry_prefix}{clean_content}\n"

                if lessons_header in full_text:
                    parts = full_text.split(lessons_header)
                    # 插入到标题下方
                    new_content = parts[0] + lessons_header + "\n" + entry + parts[1].lstrip()
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                else:
                    with open(target_path, "a", encoding="utf-8") as f:
                        f.write(f"\n{lessons_header}\n{entry}")
                return f"已成功更新长期记忆经验教训。"
        except Exception as e:
            return f"更新记忆失败: {str(e)}"

    def interrupt(self):
        """发送中断信号"""
        self.interrupted = True

    def is_safe_command(self, command):
        """安全审查：仅拦截危险的 rm 指令"""
        cmd_strip = command.strip().lower()
        if cmd_strip.startswith("rm ") or " rm " in cmd_strip:
            return False, "为了系统安全，禁止在容器内使用 rm 指令。如需删除文件，请通过其他方式操作。"
        return True, ""

    def execute_command(self, command, is_python_code=False):
        logger.info(f"执行指令 ({'Python' if is_python_code else 'Bash'}): {command[:200]}...")
        # 0. 安全审查 (容器指令审查)
        is_safe, warning = self.is_safe_command(command)
        if not is_safe:
            logger.warning(f"指令被安全审查拦截: {command}")
            return warning

        # 1. 拦截内置指令 (在宿主机本体执行)
        if not is_python_code:
            cmd_strip = command.strip()
            if cmd_strip.startswith("toolkit"):
                return self.handle_toolkit(cmd_strip.split()[1:])
            
            if cmd_strip.startswith("update_prompt"):
                # 提取 update_prompt 之后的所有内容
                parts = cmd_strip.split(None, 1)
                if len(parts) > 1:
                    content = parts[1].strip().strip('"\'')
                    return self.handle_update_prompt(content)
                return "错误: update_prompt 需要提供新的提示词内容。"

            if cmd_strip.startswith("todo"):
                content_match = re.search(r'["\'](.*?)["\']', cmd_strip, re.DOTALL)
                if content_match:
                    return self.handle_todo(content_match.group(1))
                else:
                    parts = cmd_strip.split(None, 1)
                    if len(parts) > 1:
                        content = parts[1].strip().strip('"\'')
                        return self.handle_todo(content)
                return "错误: todo 指令需要提供任务清单内容。"

            if cmd_strip.startswith("memory"):
                # 极简解析: memory "content" [--ltm]
                ltm_mode = "--ltm" in cmd_strip
                content_match = re.search(r'["\'](.*?)["\']', cmd_strip, re.DOTALL)
                if content_match:
                    return self.handle_memory(content_match.group(1), target="ltm" if ltm_mode else "stm")
                else:
                    parts = cmd_strip.split(None, 1)
                    if len(parts) > 1:
                        content = parts[1].replace("--ltm", "").strip().strip('"\'')
                        return self.handle_memory(content, target="ltm" if ltm_mode else "stm")

        # 2. 准备 Docker 执行指令 (采用 List 模式避免 Shell 转义陷阱)
        display_name = "Docker 常驻容器"
        full_command = [
            "docker", "exec",
            "-w", "/app",
            self.container_name
        ]
        
        if is_python_code:
            full_command += ["python3", "-c", command]
        else:
            full_command += ["bash", "-c", command]

        print(f"\n[Alice 正在执行 ({display_name})]: {command[:100]}{'...' if len(command) > 100 else ''}")
        
        try:
            result = subprocess.run(
                full_command,
                shell=False, # 核心修复：禁用宿主机 Shell 解析
                capture_output=True,
                text=True,
                timeout=120,
                env=os.environ
            )
            
            output = result.stdout
            if result.stderr:
                logger.error(f"指令执行产生标准错误: {result.stderr}")
                output += f"\n[标准错误输出]:\n{result.stderr}"
            if result.returncode != 0:
                logger.error(f"指令执行失败，返回码: {result.returncode}")
                output += f"\n[执行失败，退出状态码: {result.returncode}]"
            
            logger.debug(f"指令执行结果回显长度: {len(output)}")
            return output if output else "[命令执行成功，无回显内容]"
        except subprocess.TimeoutExpired:
            return "错误: 执行超时。"
        except Exception as e:
            return f"执行过程中出错: {str(e)}"

    def chat(self, user_input):
        logger.info(f"收到用户输入: {user_input[:100]}...")
        self.messages.append({"role": "user", "content": user_input})
        
        while True:
            extra_body = {"enable_thinking": True}
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=self.messages,
                stream=True,
                stream_options={"include_usage": True},
                extra_body=extra_body
            )

            full_content = ""
            thinking_content = ""
            done_thinking = False
            
            print(f"\n{'='*20} Alice 正在思考 ({self.model_name}) {'='*20}")
            
            for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    # 容错处理：确保字段存在且不为 None，防止拼接异常或截断
                    t_chunk = getattr(delta, 'reasoning_content', '') or ""
                    c_chunk = getattr(delta, 'content', '') or ""
                    
                    if t_chunk:
                        logger.debug(f"Thinking Chunk: {t_chunk}")
                        print(t_chunk, end='', flush=True)
                        thinking_content += t_chunk
                    
                    if c_chunk: # 移除 elif，防止同一 chunk 中包含两种内容时丢失正文首字
                        logger.debug(f"Content Chunk: {c_chunk}")
                        if not done_thinking:
                            print('\n\n' + "="*20 + " Alice 的回答 " + "="*20 + '\n')
                            done_thinking = True
                        print(c_chunk, end='', flush=True)
                        full_content += c_chunk

            # 提取代码块
            python_codes = re.findall(r'```python\s*\n?(.*?)\s*```', full_content, re.DOTALL)
            bash_commands = re.findall(r'```bash\s*\n?(.*?)\s*```', full_content, re.DOTALL)
            
            if not python_codes and not bash_commands:
                self.messages.append({"role": "assistant", "content": full_content})
                break
                
            self.messages.append({"role": "assistant", "content": full_content})
            results = []
            
            for code in python_codes:
                res = self.execute_command(code.strip(), is_python_code=True)
                results.append(f"Python 代码执行结果:\n{res}")
            
            for cmd in bash_commands:
                res = self.execute_command(cmd.strip(), is_python_code=False)
                results.append(f"Shell 命令 `{cmd.strip()}` 的结果:\n{res}")
            
            feedback = "\n\n".join(results)
            self.messages.append({"role": "user", "content": f"容器执行反馈：\n{feedback}"})
            
            # 刷新上下文
            self._refresh_context()
                
            logger.info("系统快照已更新，反馈给 Alice。")
            print(f"\n{'-'*40}\n系统快照已更新，结果已反馈给 Alice，继续生成中...")
