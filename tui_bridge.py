import sys
import json
import io
import os
from agent import AliceAgent

# 强制切换到脚本所在目录（根目录）
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 强制 stdout 使用 utf-8 编码，并禁用 buffering 以便实时传输 JSON
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

def main():
    try:
        alice = AliceAgent()
    except Exception as e:
        print(json.dumps({"type": "error", "content": f"Initialization failed: {str(e)}"}), flush=True)
        return
    
    # 向 Rust 发送就绪信号
    print(json.dumps({"type": "status", "content": "ready"}), flush=True)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            user_input = line.strip()
            if not user_input:
                continue
            
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
                print(json.dumps({"type": "status", "content": "thinking"}), flush=True)

                # 状态机，用于识别代码块并实现重定向
                in_code_block = False
                pending_buffer = "" # 用于处理可能跨 chunk 的 ``` 标记
                
                for chunk in response:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        t_chunk = getattr(delta, 'reasoning_content', '')
                        c_chunk = getattr(delta, 'content', '')
                        
                        if t_chunk:
                            thinking_content += t_chunk
                            print(json.dumps({"type": "thinking", "content": t_chunk}), flush=True)
                        elif c_chunk:
                            full_content += c_chunk
                            
                            # 将新内容追加到待处理缓冲区
                            pending_buffer += c_chunk
                            
                            while pending_buffer:
                                if not in_code_block:
                                    # 查找代码块开始标记
                                    start_idx = pending_buffer.find("```")
                                    if start_idx == -1:
                                        # 如果没有发现 ```，但末尾可能存在截断的 ` 或 ``
                                        # 逻辑：保留最后两个字符以防跨 chunk
                                        safe_len = max(0, len(pending_buffer) - 2)
                                        if safe_len > 0:
                                            to_send = pending_buffer[:safe_len]
                                            print(json.dumps({"type": "content", "content": to_send}), flush=True)
                                            pending_buffer = pending_buffer[safe_len:]
                                        break
                                    else:
                                        # 发送开始之前的普通文本
                                        if start_idx > 0:
                                            print(json.dumps({"type": "content", "content": pending_buffer[:start_idx]}), flush=True)
                                        
                                        in_code_block = True
                                        # 我们需要等待看到完整的 ```xxx 来确定如何处理，
                                        # 但为了即时性，直接进入代码块模式
                                        pending_buffer = pending_buffer[start_idx:]
                                        # 注意：这里不打印 ```，因为它属于代码块，将被发送到 thinking
                                else:
                                    # 已经在代码块中，查找结束标记
                                    # 注意：跳过起始的 ```
                                    end_idx = pending_buffer.find("```", 3)
                                    if end_idx == -1:
                                        # 全部作为思考发送
                                        # 同样保留末尾以防跨 chunk
                                        safe_len = max(0, len(pending_buffer) - 2)
                                        if safe_len > 0:
                                            to_send = pending_buffer[:safe_len]
                                            print(json.dumps({"type": "thinking", "content": to_send}), flush=True)
                                            pending_buffer = pending_buffer[safe_len:]
                                        break
                                    else:
                                        # 找到闭合，发送代码块内容并切换状态
                                        code_block_full = pending_buffer[:end_idx + 3]
                                        print(json.dumps({"type": "thinking", "content": code_block_full}), flush=True)
                                        pending_buffer = pending_buffer[end_idx + 3:]
                                        in_code_block = False

                # 处理最后剩余的缓冲区
                if pending_buffer:
                    msg_type = "thinking" if in_code_block else "content"
                    print(json.dumps({"type": msg_type, "content": pending_buffer}), flush=True)

                # 检查工具调用
                import re
                python_codes = re.findall(r'```python\s*\n?(.*?)\s*```', full_content, re.DOTALL)
                bash_commands = re.findall(r'```bash\s*\n?(.*?)\s*```', full_content, re.DOTALL)
                
                # 更新即时记忆 (过滤代码块)
                alice._update_working_memory(user_input, thinking_content, full_content)

                if not python_codes and not bash_commands:
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
                alice._refresh_system_message()
                
        except EOFError:
            break
        except Exception as e:
            # 捕获所有运行时错误并通过 JSON 传回，而不是直接打印
            print(json.dumps({"type": "error", "content": str(e)}), flush=True)
            break

if __name__ == "__main__":
    main()
