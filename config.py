import os
import sys
from dotenv import load_dotenv

# 加载 .env 文件
if not load_dotenv():
    print("警告: 未找到 .env 文件，请确保其存在于项目根目录。")

def get_env_var(name, default=None, required=False):
    value = os.getenv(name, default)
    if required and not value:
        print(f"错误: 环境变量 '{name}' 未设置。请在 .env 文件中进行配置。")
        sys.exit(1)
    return value

# API 配置 (强制要求 API_KEY)
API_KEY = get_env_var("API_KEY", required=True)
BASE_URL = get_env_var("API_BASE_URL", "https://api-inference.modelscope.cn/v1/")

# 模型配置 (强制要求在 .env 中设置模型名称)
MODEL_NAME = get_env_var("MODEL_NAME", required=True)

# 提示词路径
DEFAULT_PROMPT_PATH = "prompts/alice.md"

# 记忆文件路径
MEMORY_FILE_PATH = "memory/alice_memory.md"

# 任务清单路径
TODO_FILE_PATH = "memory/todo.md"

# 短期记忆路径
SHORT_TERM_MEMORY_FILE_PATH = "memory/short_term_memory.md"

# 即时记忆路径 (Working Memory)
WORKING_MEMORY_FILE_PATH = "memory/working_memory.md"
WORKING_MEMORY_MAX_ROUNDS = int(get_env_var("WORKING_MEMORY_MAX_ROUNDS", 5))

# 输出目录
ALICE_OUTPUT_DIR = "alice_output"
