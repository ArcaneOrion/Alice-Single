use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyModifiers, MouseEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph, ListState},
    Frame, Terminal,
};
use serde::{Deserialize, Serialize};
use std::{
    error::Error,
    fs::File,
    io::{self, BufRead, BufReader, Write},
    process::{Command, Stdio},
    sync::mpsc::{self, Receiver, Sender},
    thread,
    time::{Duration, Instant},
};

/// 通信协议消息类型
#[derive(Debug, Deserialize, Serialize)]
#[serde(tag = "type", rename_all = "lowercase")]
enum BridgeMessage {
    Status { content: String },
    Thinking { content: String },
    Content { content: String },
    Tokens { total: usize, prompt: usize, completion: usize },
    Error { content: String },
}

/// 消息作者
#[derive(Clone, PartialEq)]
enum Author {
    User,
    Assistant,
}

/// 单条消息结构
struct Message {
    author: Author,
    thinking: String,
    content: String,
    is_complete: bool,
}

/// Agent 运行状态
#[derive(PartialEq)]
enum AgentStatus {
    Starting,
    Idle,
    Thinking,
    Responding,
    ExecutingTool,
}

/// 应用状态
struct App {
    input: String,
    messages: Vec<Message>,
    status: AgentStatus,
    show_thinking: bool,
    should_quit: bool,
    spinner_index: usize,
    scroll_offset: usize,
    auto_scroll: bool,
    thinking_scroll_offset: usize,
    thinking_auto_scroll: bool,
    total_tokens: usize,
    prompt_tokens: usize,
    completion_tokens: usize,
    list_state: ListState,
    // 区域记录，用于鼠标碰撞检测
    chat_area: Rect,
    sidebar_area: Rect,
    // 子进程标准输入，用于发送用户消息
    child_stdin: Option<ChildStdinWrapper>,
}

struct ChildStdinWrapper(std::process::ChildStdin);

impl App {
    fn new() -> App {
        App {
            input: String::new(),
            messages: vec![Message {
                author: Author::Assistant,
                thinking: String::new(),
                content: "你好！我是你的智能助手 Alice。系统正在初始化...".to_string(),
                is_complete: true,
            }],
            status: AgentStatus::Starting,
            show_thinking: false,
            should_quit: false,
            spinner_index: 0,
            scroll_offset: 0,
            auto_scroll: true,
            thinking_scroll_offset: 0,
            thinking_auto_scroll: true,
            total_tokens: 0,
            prompt_tokens: 0,
            completion_tokens: 0,
            list_state: ListState::default(),
            chat_area: Rect::default(),
            sidebar_area: Rect::default(),
            child_stdin: None,
        }
    }

    fn send_message(&mut self) {
        if self.input.trim().is_empty() || self.status != AgentStatus::Idle {
            return;
        }

        let input = self.input.clone();
        self.messages.push(Message {
            author: Author::User,
            thinking: String::new(),
            content: input.clone(),
            is_complete: true,
        });

        // 发送给 Python 后端
        if let Some(stdin) = &mut self.child_stdin {
            let mut writer = &stdin.0;
            if writeln!(writer, "{}", input).is_err() {
                self.messages.push(Message {
                    author: Author::Assistant,
                    thinking: String::new(),
                    content: "错误: 无法连接到后端引擎。".to_string(),
                    is_complete: true,
                });
            } else {
                self.status = AgentStatus::Thinking;
                // 预先插入 Alice 的占位消息
                self.messages.push(Message {
                    author: Author::Assistant,
                    thinking: String::new(),
                    content: String::new(),
                    is_complete: false,
                });
                self.auto_scroll = true;
            }
        }

        self.input.clear();
    }

    fn on_tick(&mut self) {
        self.spinner_index = (self.spinner_index + 1) % 10;
    }

    fn get_spinner(&self) -> &'static str {
        const SPINNER: &[&str] = &["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
        SPINNER[self.spinner_index]
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    // 0. 准备日志文件
    let mut log_file = File::create("alice_debug.log")?;
    writeln!(log_file, "--- Alice Debug Log Start ---")?;

    // 1. 启动 Python 桥接层
    let mut child = Command::new("python3")
        .arg("./tui_bridge.py")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;

    let stdin = child.stdin.take().ok_or("Failed to open stdin")?;
    let stdout = child.stdout.take().ok_or("Failed to open stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to open stderr")?;

    // 2. 设置线程间通信
    let (tx, rx): (Sender<BridgeMessage>, Receiver<BridgeMessage>) = mpsc::channel();
    let tx_err = tx.clone();

    // 启动线程读取 stdout
    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            if let Ok(l) = line {
                if let Ok(msg) = serde_json::from_str::<BridgeMessage>(&l) {
                    let _ = tx.send(msg);
                }
            }
        }
    });

    // 启动线程读取 stderr 并写入日志文件
    thread::spawn(move || {
        let reader = BufReader::new(stderr);
        let mut log_file_app = File::options().append(true).open("alice_debug.log").unwrap();
        for line in reader.lines() {
            if let Ok(l) = line {
                if !l.trim().is_empty() {
                    let _ = writeln!(log_file_app, "[STDERR] {}", l);
                    let _ = tx_err.send(BridgeMessage::Error { content: format!("Backend Error: Check alice_debug.log") });
                }
            }
        }
    });

    // 3. 初始化终端
    enable_raw_mode()?;
    let mut stdout_term = io::stdout();
    execute!(stdout_term, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout_term);
    let mut terminal = Terminal::new(backend)?;

    let mut app = App {
        child_stdin: Some(ChildStdinWrapper(stdin)),
        ..App::new()
    };

    let tick_rate = Duration::from_millis(100);
    let mut last_tick = Instant::now();

    loop {
        // 处理来自后端的通信消息
        while let Ok(msg) = rx.try_recv() {
            match msg {
                BridgeMessage::Status { content } => match content.as_str() {
                    "ready" => {
                        app.status = AgentStatus::Idle;
                        if let Some(msg) = app.messages.last_mut() {
                            if msg.author == Author::Assistant && msg.content.contains("系统正在初始化") {
                                msg.content = "你好！我是你的智能助手 Alice。我已经准备好了！".to_string();
                            }
                        }
                    }
                    "thinking" => app.status = AgentStatus::Thinking,
                    "executing_tool" => app.status = AgentStatus::ExecutingTool,
                    "done" => {
                        app.status = AgentStatus::Idle;
                        if let Some(msg) = app.messages.last_mut() {
                            msg.is_complete = true;
                        }
                    }
                    _ => {}
                },
                BridgeMessage::Thinking { content } => {
                    app.status = AgentStatus::Thinking;
                    if let Some(msg) = app.messages.last_mut() {
                        if msg.author == Author::Assistant {
                            msg.thinking.push_str(&content);
                        }
                    }
                }
                BridgeMessage::Content { content } => {
                    app.status = AgentStatus::Responding;
                    if let Some(msg) = app.messages.last_mut() {
                        if msg.author == Author::Assistant {
                            msg.content.push_str(&content);
                        }
                    }
                }
                BridgeMessage::Tokens { total, prompt, completion } => {
                    app.total_tokens = total;
                    app.prompt_tokens = prompt;
                    app.completion_tokens = completion;
                }
                BridgeMessage::Error { content } => {
                    if content.contains("Backend Error") {
                        app.messages.push(Message {
                            author: Author::Assistant,
                            thinking: String::new(),
                            content: format!("⚠️ {}", content),
                            is_complete: true,
                        });
                    }
                }
            }
        }

        terminal.draw(|f| ui(f, &mut app))?;

        let timeout = tick_rate
            .checked_sub(last_tick.elapsed())
            .unwrap_or_else(|| Duration::from_secs(0));

        if event::poll(timeout)? {
            match event::read()? {
                Event::Key(key) => {
                    if key.kind == event::KeyEventKind::Release {
                        continue;
                    }

                    match key.code {
                        KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                            app.should_quit = true;
                        }
                        KeyCode::Char('o') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                            app.show_thinking = !app.show_thinking;
                        }
                        KeyCode::Char(c) => {
                            if app.status == AgentStatus::Idle {
                                app.input.push(c);
                            }
                        }
                        KeyCode::Backspace => {
                            app.input.pop();
                        }
                        KeyCode::Enter => {
                            app.send_message();
                        }
                        KeyCode::Esc => {
                            app.should_quit = true;
                        }
                        KeyCode::Up => {
                            // 键盘 Up 逻辑：如果有侧边栏，优先滚动侧边栏，除非用户正在输入
                            if app.show_thinking {
                                app.thinking_auto_scroll = false;
                                if app.thinking_scroll_offset > 0 { app.thinking_scroll_offset -= 1; }
                            } else {
                                app.auto_scroll = false;
                                if app.scroll_offset > 0 { app.scroll_offset -= 1; }
                            }
                        }
                        KeyCode::Down => {
                            if app.show_thinking {
                                if app.thinking_scroll_offset < 9999 { app.thinking_scroll_offset += 1; }
                            } else {
                                app.scroll_offset += 1;
                            }
                        }
                        _ => {}
                    }
                }
                Event::Mouse(mouse) => {
                    let (x, y) = (mouse.column, mouse.row);
                    let is_in_sidebar = app.show_thinking && 
                        x >= app.sidebar_area.x && x < app.sidebar_area.x + app.sidebar_area.width &&
                        y >= app.sidebar_area.y && y < app.sidebar_area.y + app.sidebar_area.height;
                    
                    let is_in_chat = 
                        x >= app.chat_area.x && x < app.chat_area.x + app.chat_area.width &&
                        y >= app.chat_area.y && y < app.chat_area.y + app.chat_area.height;

                    match mouse.kind {
                        MouseEventKind::ScrollUp => {
                            if is_in_sidebar {
                                app.thinking_auto_scroll = false;
                                if app.thinking_scroll_offset > 0 { app.thinking_scroll_offset -= 1; }
                            } else if is_in_chat {
                                app.auto_scroll = false;
                                if app.scroll_offset > 0 { app.scroll_offset -= 1; }
                            }
                        }
                        MouseEventKind::ScrollDown => {
                            if is_in_sidebar {
                                if app.thinking_scroll_offset < 9999 { app.thinking_scroll_offset += 1; }
                            } else if is_in_chat {
                                app.scroll_offset += 1;
                            }
                        }
                        _ => {}
                    }
                }
                _ => {}
            }
        }

        if last_tick.elapsed() >= tick_rate {
            app.on_tick();
            last_tick = Instant::now();
        }

        if app.should_quit {
            break;
        }
    }

    // 优雅退出子进程
    let _ = child.kill();

    // 恢复终端
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    Ok(())
}

fn ui(f: &mut Frame, app: &mut App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // Header
            Constraint::Min(10),   // Main Area
            Constraint::Length(3), // Input
        ])
        .split(f.size());

    // 1. Header
    let status_style = match app.status {
        AgentStatus::Starting => Style::default().fg(Color::Blue),
        AgentStatus::Idle => Style::default().fg(Color::Green),
        AgentStatus::Thinking => Style::default().fg(Color::Yellow).add_modifier(Modifier::ITALIC),
        AgentStatus::Responding => Style::default().fg(Color::Magenta),
        AgentStatus::ExecutingTool => Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD),
    };

    let status_text = match app.status {
        AgentStatus::Starting => format!(" {} 正在启动后端...", app.get_spinner()),
        AgentStatus::Idle => " ⚡ 就绪 ".to_string(),
        AgentStatus::Thinking => format!(" {} Alice 正在思考...", app.get_spinner()),
        AgentStatus::Responding => format!(" {} Alice 正在回复...", app.get_spinner()),
        AgentStatus::ExecutingTool => format!(" {} 正在执行工具任务...", app.get_spinner()),
    };

    let thinking_hint = if app.show_thinking { "显示思考过程 (Ctrl+O 隐藏)" } else { "隐藏思考过程 (Ctrl+O 显示)" };
    
    let token_info = if app.total_tokens > 0 {
        format!(" | Context: {} (P: {} / C: {})", app.total_tokens, app.prompt_tokens, app.completion_tokens)
    } else {
        "".to_string()
    };

    let header_line = Line::from(vec![
        Span::styled(" ALICE ASSISTANT ", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        Span::raw(" | 状态:"),
        Span::styled(status_text, status_style),
        Span::raw(" | "),
        Span::raw(thinking_hint),
        Span::styled(token_info, Style::default().fg(Color::DarkGray)),
    ]);

    let header = Paragraph::new(header_line)
        .block(Block::default().borders(Borders::ALL));
    f.render_widget(header, chunks[0]);

    // 2. Main Area (Split Chat and Sidebar)
    let main_chunks = if app.show_thinking {
        Layout::default()
            .direction(Direction::Horizontal)
            .constraints([
                Constraint::Percentage(75),
                Constraint::Percentage(25),
            ])
            .split(chunks[1])
    } else {
        Layout::default()
            .direction(Direction::Horizontal)
            .constraints([
                Constraint::Percentage(100),
                Constraint::Percentage(0),
            ])
            .split(chunks[1])
    };

    app.chat_area = main_chunks[0];
    app.sidebar_area = main_chunks[1];

    render_messages(f, app, main_chunks[0]);

    if app.show_thinking {
        render_sidebar(f, app, main_chunks[1]);
    }

    // 3. Input Box
    let input_title = if app.status == AgentStatus::Idle {
        " 输入消息 (Enter 发送, Ctrl+C 退出) "
    } else {
        " 请等待 Alice 回复... "
    };
    
    let input = Paragraph::new(app.input.as_str())
        .style(Style::default().fg(if app.status == AgentStatus::Idle { Color::Yellow } else { Color::DarkGray }))
        .block(Block::default().borders(Borders::ALL).title(input_title));
    f.render_widget(input, chunks[2]);

    if app.status == AgentStatus::Idle {
        let input_width = unicode_width::UnicodeWidthStr::width(app.input.as_str());
        f.set_cursor(
            chunks[2].x + input_width as u16 + 1,
            chunks[2].y + 1,
        );
    }
}

fn render_messages(f: &mut Frame, app: &mut App, area: Rect) {
    let mut message_items = Vec::new();
    let width = area.width.saturating_sub(4) as usize;

    for m in &app.messages {
        let (name, color) = match m.author {
            Author::User => (" 你: ", Color::Blue),
            Author::Assistant => (" Alice: ", Color::Magenta),
        };

        // 1. 作者行
        message_items.push(ListItem::new(Line::from(vec![
            Span::styled(name, Style::default().fg(color).add_modifier(Modifier::BOLD)),
        ])));

        // 2. 正文 (由于思考过程移到了侧边栏，这里不再渲染它)
        let content_text = if m.content.is_empty() && !m.is_complete && m.author == Author::Assistant {
            format!("{} 正在处理中...", app.get_spinner())
        } else {
            m.content.clone()
        };

        let content_lines = format_text_to_lines(&content_text, width);
        for line in content_lines {
            message_items.push(ListItem::new(Line::from(line)));
        }

        // 3. 分隔空行
        message_items.push(ListItem::new(""));
    }

    let total_lines = message_items.len();
    let list_height = area.height.saturating_sub(2) as usize;

    // 自动置底逻辑
    if app.auto_scroll {
        if total_lines > list_height {
            app.scroll_offset = total_lines - list_height;
        } else {
            app.scroll_offset = 0;
        }
    } else {
        if total_lines > list_height {
            let max_scroll = total_lines - list_height;
            if app.scroll_offset > max_scroll {
                app.scroll_offset = max_scroll;
                app.auto_scroll = true; 
            }
        } else {
            app.scroll_offset = 0;
            app.auto_scroll = true;
        }
    }

    let history = List::new(message_items)
        .block(Block::default().title(" 对话历史 ").borders(Borders::ALL));
    
    *app.list_state.offset_mut() = app.scroll_offset;
    f.render_stateful_widget(history, area, &mut app.list_state);
}

fn render_sidebar(f: &mut Frame, app: &mut App, area: Rect) {
    let width = area.width.saturating_sub(2) as usize;
    
    // 获取最新的思考过程
    let current_thinking = app.messages.iter().rev()
        .find(|m| !m.thinking.is_empty())
        .map(|m| m.thinking.as_str())
        .unwrap_or("暂无思考过程...");

    let sidebar_title = if app.status == AgentStatus::Thinking {
        format!(" 💭 {} ", app.get_spinner())
    } else {
        " 💭 ".to_string()
    };

    let style = Style::default().fg(Color::Gray).add_modifier(Modifier::ITALIC);

    // 计算内容行数以实现自动滚动
    let lines = format_text_to_lines(current_thinking, width);
    let total_lines = lines.len();
    let height = area.height.saturating_sub(2) as usize;

    if app.thinking_auto_scroll {
        if total_lines > height {
            app.thinking_scroll_offset = total_lines - height;
        } else {
            app.thinking_scroll_offset = 0;
        }
    } else {
        // 限制手动滚动范围
        if total_lines > height {
            let max_scroll = total_lines - height;
            if app.thinking_scroll_offset > max_scroll {
                app.thinking_scroll_offset = max_scroll;
                app.thinking_auto_scroll = true;
            }
        } else {
            app.thinking_scroll_offset = 0;
            app.thinking_auto_scroll = true;
        }
    }

    let thinking_paragraph = Paragraph::new(current_thinking)
        .style(style)
        .wrap(ratatui::widgets::Wrap { trim: true })
        .scroll((app.thinking_scroll_offset as u16, 0))
        .block(Block::default()
            .title(sidebar_title)
            .borders(Borders::ALL));

    f.render_widget(thinking_paragraph, area);
}

/// 简易手动文本换行辅助函数
fn format_text_to_lines(text: &str, width: usize) -> Vec<String> {
    if width == 0 { return vec![text.to_string()]; }
    let mut lines = Vec::new();
    for paragraph in text.split('\n') {
        if paragraph.is_empty() {
            lines.push(String::new());
            continue;
        }
        let mut current_line = String::new();
        let mut current_width = 0;

        for ch in paragraph.chars() {
            let ch_width = unicode_width::UnicodeWidthChar::width(ch).unwrap_or(1);
            if current_width + ch_width > width {
                lines.push(current_line);
                current_line = String::new();
                current_width = 0;
            }
            current_line.push(ch);
            current_width += ch_width;
        }
        if !current_line.is_empty() {
            lines.push(current_line);
        }
    }
    lines
}
