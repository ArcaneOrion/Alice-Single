//! # Alice Assistant - Rust TUI Frontend
//!
//! 基于 ratatui 的终端用户界面，与 Python 后端通过 stdin/stdout 通信。
//!
//! ## 架构
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────┐
//! │                    Frontend (Rust)                          │
//! │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
//! │  │  UI Layer   │  │ Event Bus   │  │  Protocol Layer     │  │
//! │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
//! └─────────┼─────────────────┼─────────────────────┼─────────────┘
//!           │                 │                     │
//!           └─────────────────┼─────────────────────┘
//!                            │ stdin/stdout (JSON)
//!          ┌─────────────────┼─────────────────────┐
//!          │                 │                     │
//! ┌────────▼────────┐ ┌──────▼──────┐ ┌───────────▼───────────┐    │
//! │ Backend (Python)│             │                        │
//! │ ┌──────────────┐ │ ┌───────────▼─▼──────────────────┐    │
//! │ │Domain Layer   │ │ │      Application Layer           │    │
//! └───────────────────┘ │──────────────────────────────────┘ │
//! └───────────────────────────────────────────────────────────┘
//! ```

use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyModifiers, MouseEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::CrosstermBackend,
    layout::Constraint,
    style::{Color, Style},
    text::Line,
    widgets::{Block, Borders, Paragraph},
    Frame, Terminal,
};

use std::io::{self, Stdout};
use std::time::{Duration, Instant};

use app::state::{AgentStatus, App};
use core::dispatcher::EventDispatcher;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 启动 Python 后端
    let bridge_client = bridge::client::BridgeClient::spawn_default()?;

    // 初始化应用状态
    let mut app = App::new(bridge_client);

    // 初始化事件分发器
    let mut dispatcher = EventDispatcher::new();

    // 初始化终端
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let tick_rate = Duration::from_millis(100);
    let mut last_tick = Instant::now();

    // 主事件循环
    loop {
        // 处理来自后端的消息
        while let Ok(msg) = app.bridge_client.try_recv_message() {
            dispatcher.handle_bridge_message(&mut app, msg);
        }

        // 处理来自后端的错误
        while let Ok(err) = app.bridge_client.try_recv_error() {
            dispatcher.handle_bridge_error(&mut app, err);
        }

        // 渲染 UI
        terminal.draw(|f| ui(f, &mut app))?;

        // 处理终端事件
        let timeout = tick_rate
            .checked_sub(last_tick.elapsed())
            .unwrap_or_else(|| Duration::from_secs(0));

        if event::poll(timeout)? {
            match event::read()? {
                Event::Key(key) => {
                    dispatcher.handle_key_event(&mut app, key);
                }
                Event::Mouse(mouse) => {
                    dispatcher.handle_mouse_event(&mut app, mouse);
                }
                _ => {}
            }
        }

        // 定时器更新
        if last_tick.elapsed() >= tick_rate {
            app.on_tick();
            last_tick = Instant::now();
        }

        // 检查退出条件
        if app.should_quit {
            break;
        }
    }

    // 优雅退出
    drop(terminal);
    disable_raw_mode()?;
    execute!(
        io::stdout(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;

    Ok(())
}

fn ui(f: &mut Frame, app: &mut App) {
    // TODO: 实现UI渲染
    // 当前为简化版本，完整UI组件将逐步从 ui/component 模块迁移
    let chunks = ratatui::layout::Layout::default()
        .direction(ratatui::layout::Direction::Vertical)
        .constraints([
            ratatui::layout::Constraint::Length(3),
            ratatui::layout::Constraint::Min(10),
            ratatui::layout::Constraint::Length(3),
        ])
        .split(f.size());

    // Header
    let status_text = match app.status {
        AgentStatus::Idle => "⚡ 就绪",
        AgentStatus::Thinking => "💭 思考中...",
        AgentStatus::Responding => "✍️ 回复中...",
        AgentStatus::ExecutingTool => "🔧 执行工具...",
        AgentStatus::Starting => "⏳ 启动中...",
    };

    let header = Paragraph::new(Line::from(vec![
        " ALICE ASSISTANT ",
        status_text,
    ]))
    .block(Block::default().borders(Borders::ALL));
    f.render_widget(header, chunks[0]);

    // Main area (placeholder)
    let main = Paragraph::new("Alice 重构版本 - UI 组件正在迁移中...")
        .block(Block::default().borders(Borders::ALL).title(" 对话历史 "));
    f.render_widget(main, chunks[1]);

    // Input
    let input = Paragraph::new(app.input.as_str())
        .block(Block::default().borders(Borders::ALL).title(" 输入 "));
    f.render_widget(input, chunks[2]);
}
