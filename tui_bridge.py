import sys
import json
import io
import os
import logging
import traceback
import threading
import queue
import re
from agent import AliceAgent

# 配置桥接层日志
logger = logging.getLogger("TuiBridge")

class StreamManager:
    """流式数据管理器，使用缓冲区预判代码块状态，确保 UI 分流精确"""
    def __init__(self, max_buffer_size=10*1024*1024, window_size=20):  # 10MB 默认限制
        self.buffer = ""
        self.in_code_block = False
        self.current_end_tag = "```"
        self.current_start_tag_len = 3
        self.max_buffer_size = max_buffer_size
        self.window_size = window_size # 滑动预判窗口大小

    def process_chunk(self, chunk_text):
        """处理新到达的文本块"""
        self.buffer += chunk_text

        # P0 修复: 防止缓冲区无限增长导致 OOM
        if len(self.buffer) > self.max_buffer_size:
            logger.warning(f"StreamManager 缓冲区超限 ({len(self.buffer)} > {self.max_buffer_size})，强制冲刷")
            output = self._try_dispatch(is_final=True)
            self.buffer = ""  # 清空缓冲区
            self.in_code_block = False  # 重置状态
            return output

        return self._try_dispatch()

    def _try_dispatch(self, is_final=False):
        """尝试分发数据。如果非最后一次，则保留窗口余量以供预判"""
        output_msgs = []
        just_entered_code_block = False
        
        while True:
            if not self.buffer:
                break

            if not self.in_code_block:
                # 兼容多种标记形式，增加 tool_call, python, cat 等识别判断
                markers = [
                    ("```python", "```"),
                    ("```bash", "```"),
                    ("```", "```"),
                    ("<thought>", "</thought>"),
                    ("<reasoning>", "</reasoning>"),
                    ("<thinking>", "</thinking>"),
                    ("<tool_call>", "</tool_call>"),
                    ("<python>", "</python>"),
                ]
                
                # 裸关键词识别 (通常出现在行首或空白后)
                naked_keywords = ["python ", "cat ", "ls ", "grep ", "mkdir "]
                
                found_marker = None
                start_idx = -1
                
                # 1. 优先匹配显式标记
                for start_tag, end_tag in markers:
                    idx = self.buffer.find(start_tag)
                    if idx != -1 and (start_idx == -1 or idx < start_idx):
                        start_idx = idx
                        found_marker = (start_tag, end_tag)
                
                # 2. 匹配裸关键词 (防止代码直接出现在正文)
                for kw in naked_keywords:
                    # 使用正则检测行首或特定位置的关键词
                    kw_match = re.search(r'(?:^|\n)' + re.escape(kw), self.buffer)
                    if kw_match:
                        idx = kw_match.start()
                        if start_idx == -1 or idx < start_idx:
                            start_idx = idx
                            # 对于裸关键词，我们假设它会持续到下一个双换行或 buffer 结束，或者被包裹在虚拟思考区
                            found_marker = (kw_match.group(), "\n\n") 

                if start_idx == -1:
                    if not is_final:
                        # 智能前缀保留 (滑动延迟检测)
                        # 保留 window_size 长度，或者保留标记的前缀
                        hold_back = self.window_size
                        for start_tag, _ in markers:
                            for i in range(len(start_tag)-1, 0, -1):
                                if self.buffer.endswith(start_tag[:i]):
                                    hold_back = max(hold_back, i)
                                    break
                        
                        # 额外检查 naked_keywords 的前缀
                        for kw in naked_keywords:
                            for i in range(len(kw)-1, 0, -1):
                                if self.buffer.endswith(kw[:i]):
                                    hold_back = max(hold_back, i)
                                    break

                        safe_len = len(self.buffer) - hold_back
                        if safe_len > 0:
                            output_msgs.append({"type": "content", "content": self.buffer[:safe_len]})
                            self.buffer = self.buffer[safe_len:]
                        break
                    else:
                        output_msgs.append({"type": "content", "content": self.buffer})
                        self.buffer = ""
                        break
                else:
                    # 发现起始标记，处理之前的正文
                    if start_idx > 0:
                        output_msgs.append({"type": "content", "content": self.buffer[:start_idx]})
                    
                    self.in_code_block = True
                    self.current_end_tag = found_marker[1]
                    self.current_start_tag_len = len(found_marker[0])
                    just_entered_code_block = True
                    self.buffer = self.buffer[start_idx:]
            else:
                # 已经在隔离块中，寻找结束标记
                search_offset = self.current_start_tag_len if just_entered_code_block else 0
                end_idx = self.buffer.find(self.current_end_tag, search_offset)

                # P0 修复: 仅在找到结束标签或输出内容后才重置标志
                if end_idx == -1:
                    if not is_final:
                        # 同样需要保留结束标签的前缀
                        hold_back = 0
                        for i in range(len(self.current_end_tag)-1, 0, -1):
                            if self.buffer.endswith(self.current_end_tag[:i]):
                                hold_back = i
                                break
                        
                        safe_len = len(self.buffer) - hold_back
                        if safe_len > 0:
                            output_msgs.append({"type": "thinking", "content": self.buffer[:safe_len]})
                            self.buffer = self.buffer[safe_len:]
                        break
                    else:
                        output_msgs.append({"type": "thinking", "content": self.buffer})
                        self.buffer = ""
                        break
                else:
                    # 发现结束标记，闭合思考块
                    thinking_end = end_idx + len(self.current_end_tag)
                    output_msgs.append({"type": "thinking", "content": self.buffer[:thinking_end]})
                    self.buffer = self.buffer[thinking_end:]
                    self.in_code_block = False
                    just_entered_code_block = False  # 找到结束标签后重置
        
        return output_msgs

    def flush(self):
        """强制冲刷所有剩余数据"""
        return self._try_dispatch(is_final=True)

# 强制切换到脚本所在目录（根目录）
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 强制 stdout 使用 utf-8 编码，并禁用 buffering 以便实时传输 JSON
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

# 异步输入队列与监听线程
input_queue = queue.Queue()

def stdin_reader():
    """专门负责监听宿主机输入的线程，防止阻塞主逻辑"""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                input_queue.put(None) # EOF 信号
                break
            input_queue.put(line.strip())
        except Exception:
            break

def main():
    logger.info("TUI Bridge 进程启动。")
    # 启动监听线程
    threading.Thread(target=stdin_reader, daemon=True).start()

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
            # 从异步队列获取输入
            user_input = input_queue.get()
            if user_input is None:
                logger.info("接收到 EOF，退出主循环。")
                break
            
            if not user_input or user_input == "__INTERRUPT__":
                continue
            
            logger.info(f"收到 TUI 输入: {user_input}")
            
            alice.messages.append({"role": "user", "content": user_input})
            
            while True:
                extra_body = {"enable_thinking": True}
                response = alice._create_chat_completion(
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
                stream_mgr = StreamManager(max_buffer_size=10*1024*1024)  # 10MB 限制
                usage = None
                
                for chunk in response:
                    # 实时检查中断信号
                    while not input_queue.empty():
                        msg = input_queue.get_nowait()
                        if msg == "__INTERRUPT__":
                            logger.info("检测到中断信号，正在停止输出...")
                            alice.interrupted = True
                    
                    if alice.interrupted:
                        break

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
                        choice = chunk.choices[0]
                        delta = getattr(choice, 'delta', None) or choice
                        
                        # 极度兼容的读取函数
                        def get_val(obj, names):
                            for name in names:
                                # 1. 直接属性访问
                                res = getattr(obj, name, None)
                                if res: return res
                                # 2. 字典访问
                                if isinstance(obj, dict):
                                    res = obj.get(name)
                                    if res: return res
                                # 3. Pydantic 额外字段访问
                                if hasattr(obj, 'model_extra') and obj.model_extra:
                                    res = obj.model_extra.get(name)
                                    if res: return res
                            return ""

                        # 诊断日志：仅在每一轮对话的第一个 chunk 记录结构
                        if not full_content and not thinking_content:
                            try:
                                d_keys = list(delta.keys()) if isinstance(delta, dict) else list(getattr(delta, '__dict__', {}).keys())
                                if hasattr(delta, 'model_extra') and delta.model_extra:
                                    d_keys += [f"extra:{k}" for k in delta.model_extra.keys()]
                                logger.info(f"探测到响应结构: Delta_Keys={d_keys}")
                            except: pass

                        # 扩充字段名变体
                        think_names = ['reasoning_content', 'reasoningContent', 'reasoning', 'thought', 'thought_content', 'thoughtContent']
                        t_chunk = get_val(delta, think_names)
                        # 如果 delta 里没找到，尝试在 choice 级找 (某些非标代理)
                        if not t_chunk: t_chunk = get_val(choice, think_names)
                        
                        c_chunk = get_val(delta, ['content'])
                        
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
                python_codes = re.findall(r'```python\s*\n?(.*?)\s*```', full_content, re.DOTALL)
                bash_commands = re.findall(r'```bash\s*\n?(.*?)\s*```', full_content, re.DOTALL)
                
                # 更新即时记忆 (过滤代码块)
                alice._update_working_memory(user_input, thinking_content, full_content)

                if alice.interrupted:
                    logger.info("由于用户中断，跳过后续步骤。")
                    alice.interrupted = False # 重置状态
                    print(json.dumps({"type": "status", "content": "done"}), flush=True)
                    break

                if not python_codes and not bash_commands:
                    logger.info("回复完成，未检测到工具调用。")
                    alice.messages.append({"role": "assistant", "content": full_content})
                    print(json.dumps({"type": "status", "content": "done"}), flush=True)
                    break
                
                # 有工具调用
                alice.messages.append({"role": "assistant", "content": full_content})
                results = []
                
                print(json.dumps({"type": "status", "content": "executing_tool"}), flush=True)

                # 捕获工具执行过程中的 print，防止污染 stdout
                for code in python_codes:
                    if alice.interrupted: break
                    res = alice.execute_command(code.strip(), is_python_code=True)
                    results.append(f"Python 代码执行结果:\n{res}")
                
                for cmd in bash_commands:
                    if alice.interrupted: break
                    res = alice.execute_command(cmd.strip(), is_python_code=False)
                    results.append(f"Shell 命令 `{cmd.strip()}` 的结果:\n{res}")
                
                if alice.interrupted:
                    logger.info("工具执行阶段被中断。")
                    alice.interrupted = False
                    print(json.dumps({"type": "status", "content": "done"}), flush=True)
                    break

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
