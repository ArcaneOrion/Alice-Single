import React, { useState, useEffect, useRef, memo } from 'react';
import axios from 'axios';
import { Send, Bot, User, ChevronDown, ChevronUp, ScrollText, Library, Terminal, FileText, Download, ExternalLink, Code2, AlertCircle, CheckCircle2, FolderOpen, Folder } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// 自定义代码块组件
const CodeBlock = memo(({ children, className }) => {
  const [isOpen, setIsOpen] = useState(false);
  const lang = className ? className.replace('language-', '') : 'code';
  
  return (
    <details className="my-2 border border-gray-800 rounded-lg overflow-hidden bg-gray-900/50 shadow-sm transition-all" open={isOpen} onToggle={(e) => setIsOpen(e.target.open)}>
      <summary className="px-3 py-1.5 text-xs text-gray-400 cursor-pointer hover:bg-gray-800 flex items-center justify-between select-none font-mono">
        <div className="flex items-center gap-2">
          <Code2 size={12} className="text-indigo-400" />
          <span>{lang.toUpperCase()} 脚本 / 资源块</span>
        </div>
        <div className="flex items-center gap-2">
            <span className="text-[10px] bg-gray-800 px-1.5 rounded text-gray-400 uppercase">{isOpen ? '收起' : '展开内容'}</span>
            {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </summary>
      <div className="border-t border-gray-800">
        <pre className="p-3 overflow-x-auto bg-black/40 text-white text-xs leading-relaxed">
          <code className={className}>{children}</code>
        </pre>
      </div>
    </details>
  );
});

// 递归文件项组件
const FileTreeItem = memo(({ item, depth = 0 }) => {
  const [isOpen, setIsOpen] = useState(false);
  const isDir = item.type === 'directory';

  return (
    <div className="flex flex-col">
      <div 
        className={cn(
          "flex items-center justify-between p-1.5 hover:bg-gray-800/50 rounded-lg group transition-colors cursor-pointer",
          depth > 0 && "ml-3 border-l border-gray-800 pl-2"
        )}
        onClick={() => isDir && setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2 overflow-hidden flex-1">
          <div className={cn(
            "w-6 h-6 rounded flex items-center justify-center shrink-0",
            isDir ? "text-amber-500" : "text-gray-500"
          )}>
            {isDir ? (isOpen ? <FolderOpen size={14} /> : <Folder size={14} />) : <FileText size={14} />}
          </div>
          <div className="flex flex-col overflow-hidden">
            <span className={cn(
              "text-xs truncate font-medium",
              isDir ? "text-amber-100" : "text-gray-200"
            )} title={item.name}>{item.name}</span>
            {!isDir && (
              <span className="text-[9px] text-gray-500">{(item.size / 1024).toFixed(1)} KB</span>
            )}
            {isDir && item.hasIndex && (
               <span className="text-[9px] text-emerald-500 font-medium">网页报告</span>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-2">
          {isDir && item.hasIndex && (
            <a 
              href={item.indexUrl} 
              target="_blank" 
              rel="noreferrer" 
              className="p-1 text-emerald-500 hover:bg-emerald-500/20 rounded" 
              title="预览报告"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink size={12} />
            </a>
          )}
          {!isDir ? (
            <>
              <a 
                href={item.url} 
                target="_blank" 
                rel="noreferrer" 
                className="p-1 text-indigo-400 hover:bg-indigo-400/20 rounded" 
                title="打开"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink size={12} />
              </a>
              <a 
                href={item.url} 
                download 
                className="p-1 text-gray-400 hover:bg-gray-400/20 rounded" 
                title="下载"
                onClick={(e) => e.stopPropagation()}
              >
                <Download size={12} />
              </a>
            </>
          ) : (
             <div className="text-gray-600">
               {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
             </div>
          )}
        </div>
      </div>
      
      {isDir && isOpen && item.children && (
        <div className="flex flex-col mt-0.5">
          {item.children.length > 0 ? (
            item.children.map((child, idx) => (
              <FileTreeItem key={idx} item={child} depth={depth + 1} />
            ))
          ) : (
            <div className="ml-8 text-[10px] text-gray-600 py-1 italic">空目录</div>
          )}
        </div>
      )}
    </div>
  );
});

// 输入区域组件，用于隔离渲染压力
const ChatInput = memo(({ onSend, isLoading }) => {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSend(input);
    setInput('');
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-4xl mx-auto relative group">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={isLoading ? "Alice 正在全神贯注思考中..." : "问问 Alice，或要求她执行任务..."}
        disabled={isLoading}
        className="w-full pl-5 pr-14 py-4 bg-gray-900 border border-gray-800 rounded-2xl focus:outline-none focus:ring-4 focus:ring-indigo-500/5 focus:border-indigo-500 focus:bg-gray-900 transition-all disabled:bg-gray-950 disabled:text-gray-600 text-gray-100 shadow-inner"
      />
      <button
        type="submit"
        disabled={isLoading || !input.trim()}
        className="absolute right-2.5 top-2.5 bg-indigo-600 text-white p-2.5 rounded-xl hover:bg-indigo-700 transition-all disabled:bg-gray-800 shadow-none active:scale-95"
      >
        <Send size={20} />
      </button>
    </form>
  );
});

function App() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [tasks, setTasks] = useState('');
  const [skills, setSkills] = useState({});
  const [outputs, setOutputs] = useState([]);
  const [isOutputsOpen, setIsOutputsOpen] = useState(true);
  const [isSkillsOpen, setIsSkillsOpen] = useState(true);
  const chatEndRef = useRef(null);

  const scrollToBottom = (instant = false) => {
    chatEndRef.current?.scrollIntoView({ behavior: instant ? 'auto' : 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const handleResize = () => scrollToBottom(true);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    fetchHistory();
    fetchStatus();
    const timer = setInterval(fetchStatus, 5000);
    return () => clearInterval(timer);
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await axios.get('/api/history');
      if (Array.isArray(res.data)) {
        setMessages(res.data);
      }
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  };

  const fetchStatus = async () => {
    try {
      const [taskRes, skillRes, outputRes] = await Promise.all([
        axios.get('/api/tasks'),
        axios.get('/api/skills'),
        axios.get('/api/outputs')
      ]);
      setTasks(taskRes.data.content);
      setSkills(skillRes.data.skills);
      setOutputs(outputRes.data.files);
    } catch (err) {
      console.error('Failed to fetch status:', err);
    }
  };

  const handleSendMessage = async (text) => {
    const userMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    let currentBotMessage = { role: 'bot', steps: [], finalAnswer: '', isComplete: false };
    setMessages((prev) => [...prev, currentBotMessage]);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let currentStep = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            if (data.type === 'start_step') {
                currentStep = { id: data.step, thinking: '', content: '', executionResults: [], systemLogs: [] };
                currentBotMessage.steps.push(currentStep);
            } else if (data.type === 'thinking' && currentStep) {
                currentStep.thinking += data.delta;
            } else if (data.type === 'content' && currentStep) {
                currentStep.content += data.delta;
            } else if (data.type === 'system' && currentStep) {
                currentStep.systemLogs.push(data.content);
            } else if (data.type === 'execution_result' && currentStep) {
                currentStep.executionResults.push(data.content);
            } else if (data.type === 'final_answer') {
                currentBotMessage.finalAnswer = data.content;
                currentBotMessage.isComplete = true;
            }

            setMessages((prev) => {
              const newMessages = [...prev];
              newMessages[newMessages.length - 1] = { ...currentBotMessage };
              return newMessages;
            });
          } catch (e) {
            console.error('Error parsing chunk:', e, line);
          }
        }
      }
    } catch (err) {
      console.error('Chat error:', err);
    } finally {
      setIsLoading(false);
      fetchStatus();
    }
  };

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden font-sans selection:bg-indigo-500/30">
      <div className="w-80 bg-gray-900 border-r border-gray-800 flex flex-col hidden lg:flex shadow-2xl z-10">
        <div className="p-6 border-b border-gray-800 flex items-center gap-3">
          <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-900/20">
            <Bot className="text-white w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-100 leading-none">Alice Agent</h1>
            <span className="text-[10px] text-indigo-400 font-medium uppercase tracking-wider">Experimental Lab</span>
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-6 scrollbar-thin scrollbar-thumb-gray-800">
          <section>
            <div className="flex items-center gap-2 mb-3 text-gray-100 font-bold px-2 text-sm uppercase tracking-wider">
              <ScrollText size={16} className="text-indigo-400" />
              <span>任务清单 (Todo)</span>
            </div>
            <div className="bg-indigo-900/10 rounded-xl p-4 text-sm text-gray-300 whitespace-pre-wrap border border-indigo-900/20 max-h-48 overflow-y-auto font-mono">
              {tasks || '暂无活跃任务'}
            </div>
          </section>

          <section>
            <button 
              onClick={() => setIsOutputsOpen(!isOutputsOpen)}
              className="w-full flex items-center justify-between mb-3 text-gray-100 font-bold px-2 text-sm uppercase tracking-wider hover:bg-gray-800/50 py-1 rounded transition-colors"
            >
              <div className="flex items-center gap-2">
                <FileText size={16} className="text-indigo-400" />
                <span>成果物 (Outputs)</span>
              </div>
              {isOutputsOpen ? <ChevronUp size={14} className="text-gray-500" /> : <ChevronDown size={14} className="text-gray-500" />}
            </button>
            {isOutputsOpen && (
              <div className="space-y-0.5 px-1 animate-in fade-in slide-in-from-top-1 duration-200">
                {outputs.length > 0 ? (
                  outputs.map((item, idx) => (
                    <FileTreeItem key={idx} item={item} />
                  ))
                ) : (
                  <div className="text-xs text-gray-500 text-center py-4 italic bg-gray-800/50 rounded-xl border border-dashed border-gray-700">
                    尚未生成任何文件
                  </div>
                )}
              </div>
            )}
          </section>

          <section>
            <button 
              onClick={() => setIsSkillsOpen(!isSkillsOpen)}
              className="w-full flex items-center justify-between mb-3 text-gray-100 font-bold px-2 text-sm uppercase tracking-wider hover:bg-gray-800/50 py-1 rounded transition-colors"
            >
              <div className="flex items-center gap-2">
                <Library size={16} className="text-indigo-400" />
                <span>技能库 (Skills)</span>
              </div>
              {isSkillsOpen ? <ChevronUp size={14} className="text-gray-500" /> : <ChevronDown size={14} className="text-gray-500" />}
            </button>
            {isSkillsOpen && (
              <div className="grid grid-cols-1 gap-2 px-1 animate-in fade-in slide-in-from-top-1 duration-200">
                {Object.keys(skills).map(name => (
                  <div key={name} className="p-3 bg-gray-800/50 border border-gray-800 rounded-xl shadow-sm hover:shadow-md transition-shadow group">
                    <div className="font-bold text-gray-200 text-xs mb-1 group-hover:text-indigo-400 transition-colors">{name}</div>
                    <div className="text-[10px] text-gray-500 line-clamp-2 leading-relaxed">{skills[name].description}</div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>

      <div className="flex-1 flex flex-col relative z-0">
        <div className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth bg-gray-950">
          {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-gray-600 space-y-4">
                  <Bot size={48} className="text-gray-800" />
                  <p className="text-sm font-medium font-mono">今天有什么我可以帮你的吗？</p>
              </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={cn("flex w-full animate-in fade-in slide-in-from-bottom-2 duration-300", msg.role === 'user' ? "justify-end" : "justify-start")}>
              <div className={cn("max-w-[90%] flex gap-4", msg.role === 'user' ? "flex-row-reverse" : "flex-row")}>
                <div className={cn(
                  "w-9 h-9 rounded-2xl flex items-center justify-center shrink-0 shadow-md",
                  msg.role === 'user' ? "bg-gray-800 text-indigo-400 border border-indigo-900/50" : "bg-indigo-600 text-white"
                )}>
                  {msg.role === 'user' ? <User size={20} /> : <Bot size={20} />}
                </div>
                <div className="space-y-4 flex-1 min-w-0">
                  {msg.role === 'user' ? (
                    <div className="bg-gray-800 text-gray-100 px-5 py-3 rounded-2xl border border-gray-700 shadow-sm leading-relaxed whitespace-pre-wrap break-words overflow-hidden">
                      {msg.content}
                    </div>
                  ) : (
                    <>
                      {msg.steps && msg.steps.length > 0 && (
                        <div className="space-y-2 min-w-0">
                          {msg.steps.map((step, idx) => (
                            <div key={idx} className="group/step min-w-0">
                                <details className="bg-gray-900/40 rounded-xl border border-gray-800/50 overflow-hidden transition-all" open={!msg.isComplete && idx === msg.steps.length - 1}>
                                    <summary className="px-3 py-2 text-[11px] text-gray-500 cursor-pointer hover:bg-gray-800/50 flex items-center justify-between select-none font-mono overflow-hidden">
                                        <div className="flex items-center gap-3">
                                            <div className={cn(
                                                "w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold",
                                                step.executionResults.length > 0 ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30" : "bg-gray-800 text-gray-500"
                                            )}>
                                                {step.id}
                                            </div>
                                            <span className="uppercase tracking-widest font-bold opacity-70">
                                                {step.executionResults.length > 0 ? "执行与观测" : "思考与规划"}
                                            </span>
                                        </div>
                                        <ChevronDown size={14} className="opacity-0 group-hover/step:opacity-100 transition-opacity" />
                                    </summary>
                                    <div className="p-4 bg-black/20 space-y-3 border-t border-gray-800/50 overflow-hidden">
                                        {step.thinking && (
                                            <div className="text-xs text-gray-400 italic font-mono leading-relaxed bg-gray-950/50 p-3 rounded-lg border border-gray-800 break-words overflow-hidden">
                                                <div className="text-[9px] text-indigo-500 mb-1 font-bold"># THOUGHT_PROCESS</div>
                                                {step.thinking}
                                            </div>
                                        )}
                                        {step.content && (
                                            <div className="text-xs text-gray-300 bg-gray-900/50 p-3 rounded-lg border border-gray-800 break-words overflow-hidden text-wrap">
                                                <div className="text-[9px] text-emerald-500 mb-1 font-bold"># INTENT</div>
                                                <ReactMarkdown className="prose prose-invert prose-xs max-w-none break-words">{step.content}</ReactMarkdown>
                                            </div>
                                        )}
                                        {step.executionResults.length > 0 && (
                                            <div className="space-y-2">
                                                {step.executionResults.map((res, ridx) => (
                                                    <div key={ridx} className="bg-black/60 rounded-lg p-3 border border-gray-800 font-mono text-[10px]">
                                                        <div className="flex items-center justify-between mb-2 text-gray-500">
                                                            <div className="flex items-center gap-1.5"><Terminal size={12} /><span>EXEC_RESULT_{ridx + 1}</span></div>
                                                            <span className={res.includes('执行失败') ? "text-red-500" : "text-green-500"}>{res.includes('执行失败') ? "FAIL" : "SUCCESS"}</span>
                                                        </div>
                                                        <pre className="text-green-400/90 overflow-x-auto whitespace-pre-wrap">{res}</pre>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </details>
                            </div>
                          ))}
                        </div>
                      )}
                      {(msg.finalAnswer || (!msg.steps && msg.content)) && (
                        <div className={cn(
                            "rounded-2xl px-5 py-4 shadow-xl leading-relaxed border animate-in fade-in zoom-in-95 duration-500 overflow-hidden min-w-0",
                            "bg-gray-900 text-gray-100 border-gray-800"
                        )}>
                            <ReactMarkdown 
                            className="prose prose-sm max-w-none prose-invert prose-headings:font-bold prose-a:text-indigo-400 prose-pre:p-0 prose-pre:bg-transparent prose-pre:m-0 break-words"
                            components={{
                                code: ({ node, inline, className, children, ...props }) => {
                                return inline ? (
                                    <code className={cn("bg-gray-800 text-pink-400 px-1.5 py-0.5 rounded font-mono text-[0.85em] font-medium", className)} {...props}>{children}</code>
                                ) : (
                                    <CodeBlock className={className}>{children}</CodeBlock>
                                );
                                }
                            }}
                            >
                            {msg.finalAnswer || msg.content}
                            </ReactMarkdown>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>
        <div className="p-6 bg-gray-950/80 backdrop-blur-md border-t border-gray-800">
          <ChatInput onSend={handleSendMessage} isLoading={isLoading} />
        </div>
      </div>
    </div>
  );
}

export default App;
