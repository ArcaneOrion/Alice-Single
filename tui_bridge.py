import sys
import json
import io
import os
import logging
import traceback
from agent import AliceAgent

# 配置桥接层日志
logger = logging.getLogger("TuiBridge")

class StreamManager:
    """流式数据管理器，使用缓冲区预判代码块状态，确保 UI 分流精确"""
    def __init__(self, buffer_size=30):
        self.buffer = ""
        self.in_code_block = False
        self.buffer_size = buffer_size

    def process_chunk(self, chunk_text):
        """处理新到达的文本块"""
        self.buffer += chunk_text
        return self._try_dispatch()

    def _try_dispatch(self, is_final=False):
        """尝试分发数据。如果非最后一次，则保留窗口余量以供预判"""
        output_msgs = []
        # 用于追踪是否在当前循环中刚刚进入代码块
        just_entered_code_block = False
        
        while True:
            # 如果缓冲区为空，直接跳出
            if not self.buffer:
                break

            if not self.in_code_block:
                # 寻找代码块起始标记
                start_idx = self.buffer.find("```")
                if start_idx == -1:
                    # 没找到。
                    # 如果不是最终输出，我们要保留末尾可能成为 ``` 的部分（仅限反引号）
                    if not is_final:
                        # 检查末尾反引号 (ASCII 96)
                        # 注意：不要误伤中文感叹号或其他标点
                        backtick_count = 0
                        if self.buffer.endswith("``"): backtick_count = 2
                        elif self.buffer.endswith("`"): backtick_count = 1
                        
                        safe_len = len(self.buffer) - backtick_count
                        
                        if safe_len > 0:
                            content = self.buffer[:safe_len]
                            output_msgs.append({"type": "content", "content": content})
                            self.buffer = self.buffer[safe_len:]
                        
                        # 无论是否分发了 content，只要末尾有反引号，就必须 break 等待下一个 chunk
                        if backtick_count > 0:
                            break
                        # 如果没有反引号且没找到 ```，说明当前 buffer 全是普通文本，
                        # 但因为没有后续数据，在非 final 模式下，我们也已经处理完了
                        break
                    else:
                        # 最终输出，直接全发
                        if self.buffer:
                            output_msgs.append({"type": "content", "content": self.buffer})
                            self.buffer = ""
                        break
                else:
                    # 找到了起始标记！
                    # 在发送 start_idx 之前的内容前，我们要确保 ``` 后面跟着的东西也被预判了
                    # 比如 ```bash\n，如果 buffer 只到 ```b，我们要等待（增加预判深度）
                    if not is_final:
                        remaining_len = len(self.buffer) - start_idx
                        if remaining_len < 10: # 至少给标签留 10 个字符的观察期
                            break

                    if start_idx > 0:
                        output_msgs.append({"type": "content", "content": self.buffer[:start_idx]})
                    
                    self.in_code_block = True
                    just_entered_code_block = True
                    self.buffer = self.buffer[start_idx:]
                    # 继续处理代码块内部
            else:
                # 已经在代码块中，寻找结束标记
                # 仅在同一轮循环中刚刚进入代码块时，才需要跳过当前的起始标记 (offset=3)
                # 如果是跨 chunk 处理，则起始位置应该是 0
                search_offset = 3 if just_entered_code_block else 0
                end_idx = self.buffer.find("```", search_offset)
                just_entered_code_block = False # 重置状态
                
                if end_idx == -1:
                    # 没找到结束标记。同理，保留可能的截断 `
                    if not is_final:
                        backtick_count = 0
                        if self.buffer.endswith("``"): backtick_count = 2
                        elif self.buffer.endswith("`"): backtick_count = 1
                        
                        safe_len = len(self.buffer) - backtick_count
                        if safe_len > 0:
                            thinking = self.buffer[:safe_len]
                            output_msgs.append({"type": "thinking", "content": thinking})
                            self.buffer = self.buffer[safe_len:]
                        break
                    else:
                        if self.buffer:
                            output_msgs.append({"type": "thinking", "content": self.buffer})
                            self.buffer = ""
                        break
                else:
                    # 找到了结束标记！
                    # 将直到结束标记的内容全部发给 thinking
                    thinking_end = end_idx + 3
                    output_msgs.append({"type": "thinking", "content": self.buffer[:thinking_end]})
                    self.buffer = self.buffer[thinking_end:]
                    self.in_code_block = False
                    # 切换回普通模式，继续循环处理 buffer 剩余部分
        
        return output_msgs

    def flush(self):
        """强制冲刷所有剩余数据"""
        return self._try_dispatch(is_final=True)

# 强制切换到脚本所在目录（根目录）
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 强制 stdout 使用 utf-8 编码，并禁用 buffering 以便实时传输 JSON
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

def main():
    logger.info("TUI Bridge 进程启动。")
    try:
        alice = AliceAgent()
    except Exception as e:
        error_msg = f"初始化失败: {traceback.format_exc()}"
        logger.error(error_msg)
        print(json.dumps({"type": "error", "content": f"Initialization failed: {str(e)}"}), flush=True)
        return
    
    # 向 Rust 发送就绪信号
    print(json.dumps({"type": "status", "content": "ready"}), flush=True)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                logger.info("接收到 EOF，退出主循环。")
                break
            
            user_input = line.strip()
            if not user_input:
                continue
            
            logger.info(f"收到 TUI 输入: {user_input}")
            
            alice.messages.append({"role": "user", "content": user_input})
            
            while True:
                extra_body = {"enable_thinking": True}
                response = alice.client.chat.completions.create(
                    model=alice.model_name,
                    messages=alice.messages,
                    stream=True,
                    extra_body=extra_body
                )

                full_content = ""
                thinking_content = ""
                
                # 发送开始思考信号
                logger.info("开始流式请求 (chat.completions.create)...")
                print(json.dumps({"type": "status", "content": "thinking"}), flush=True)

                # 初始化流管理器 (滑动窗口预判)
                stream_mgr = StreamManager(buffer_size=30)
                usage = None
                
                for chunk in response:
                    # 获取 Token 使用情况
                    if hasattr(chunk, 'usage') and chunk.usage:
                        usage = chunk.usage
                        print(json.dumps({
                            "type": "tokens",
                            "total": usage.total_tokens,
                            "prompt": usage.prompt_tokens,
                            "completion": usage.completion_tokens
                        }), flush=True)

                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        # 容错处理：确保字段存在且不为 None，防止拼接异常或截断
                        t_chunk = getattr(delta, 'reasoning_content', '') or ""
                        c_chunk = getattr(delta, 'content', '') or ""
                        
                        if t_chunk:
                            thinking_content += t_chunk
                            print(json.dumps({"type": "thinking", "content": t_chunk}), flush=True)
                        
                        if c_chunk: # 移除 elif，防止同一 chunk 中包含两种内容时丢失正文首字
                            full_content += c_chunk
                            # 通过流管理器处理内容块 (保留延迟机制，确保 UI 不出现代码块碎屑)
                            msgs = stream_mgr.process_chunk(c_chunk)
                            for msg in msgs:
                                print(json.dumps(msg), flush=True)

                # 强制冲刷管理器缓冲区
                final_msgs = stream_mgr.flush()
                if final_msgs:
                    logger.info(f"强制冲刷 StreamManager 缓冲区: {final_msgs}")
                    for msg in final_msgs:
                        print(json.dumps(msg), flush=True)

                # 检查工具调用
                import re
                python_codes = re.findall(r'```python\s*\n?(.*?)\s*```', full_content, re.DOTALL)
                bash_commands = re.findall(r'```bash\s*\n?(.*?)\s*```', full_content, re.DOTALL)
                
                # 更新即时记忆 (过滤代码块)
                alice._update_working_memory(user_input, thinking_content, full_content)

                if not python_codes and not bash_commands:
                    logger.info("回复完成，未检测到工具调用。")
                    # 过滤掉 full_content 中的代码块再存入 messages，防止 UI 重复渲染（或者保持完整，UI 渲染时再处理）
                    # 这里保持消息完整性，但 UI 由于我们上面分流发送，已经实现了“代码块在侧边栏”的效果
                    alice.messages.append({"role": "assistant", "content": full_content})
                    print(json.dumps({"type": "status", "content": "done"}), flush=True)
                    break
                
                # 有工具调用
                alice.messages.append({"role": "assistant", "content": full_content})
                results = []
                
                print(json.dumps({"type": "status", "content": "executing_tool"}), flush=True)

                # 捕获工具执行过程中的 print，防止污染 stdout
                for code in python_codes:
                    res = alice.execute_command(code.strip(), is_python_code=True)
                    results.append(f"Python 代码执行结果:\n{res}")
                
                for cmd in bash_commands:
                    res = alice.execute_command(cmd.strip(), is_python_code=False)
                    results.append(f"Shell 命令 `{cmd.strip()}` 的结果:\n{res}")
                
                feedback = "\n\n".join(results)
                alice.messages.append({"role": "user", "content": f"容器执行反馈：\n{feedback}"})
                alice._refresh_context()
                
        except EOFError:
            logger.info("接收到 EOFError。")
            break
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"TUI Bridge 运行时异常:\n{error_trace}")
            # 捕获所有运行时错误并通过 JSON 传回，而不是直接打印
            print(json.dumps({"type": "error", "content": f"Runtime Error: {str(e)}. 请查看 alice_runtime.log"}), flush=True)
            break

if __name__ == "__main__":
    main()
