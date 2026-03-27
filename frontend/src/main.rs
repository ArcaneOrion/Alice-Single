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
    event::{self, DisableMouseCapture, EnableMouseCapture, Event},
    execute,
    terminal::{EnterAlternateScreen, LeaveAlternateScreen, disable_raw_mode, enable_raw_mode},
};
use ratatui::{Terminal, backend::CrosstermBackend};

use std::io;
use std::time::{Duration, Instant};

use alice_frontend::app::state::App;
use alice_frontend::bridge::client::BridgeClient;
use alice_frontend::core::dispatcher::{EventDispatcher, drain_bridge_messages};
use alice_frontend::core::event::EventBus;
use alice_frontend::ui::render_app;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 启动 Python 后端
    let bridge_client = BridgeClient::spawn_default()?;

    // 初始化事件总线
    let event_bus = EventBus::new();

    // 初始化应用状态
    let mut app = App::new(bridge_client);

    // 初始化事件分发器
    let mut dispatcher = EventDispatcher::new(event_bus);

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
        if !drain_bridge_messages(&mut app, &mut dispatcher) {
            break;
        }

        // 处理来自后端的错误
        while let Some(err) = app.bridge_client.try_recv_error() {
            dispatcher.handle_bridge_error(&mut app, err);
        }

        // 渲染 UI
        terminal.draw(|f| render_app(f, &mut app))?;
        dispatcher.update_areas(
            app.area_bounds.chat_area,
            app.area_bounds.sidebar_area,
            app.area_bounds.input_area,
        );

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
    execute!(io::stdout(), LeaveAlternateScreen, DisableMouseCapture)?;

    Ok(())
}
