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
    event::{
        self, DisableBracketedPaste, DisableMouseCapture, EnableBracketedPaste, EnableMouseCapture,
        Event,
    },
    execute,
    terminal::{EnterAlternateScreen, LeaveAlternateScreen, disable_raw_mode, enable_raw_mode},
};
use ratatui::{Terminal, backend::CrosstermBackend};

use std::io;
use std::time::{Duration, Instant};

use alice_frontend::app::state::App;
use alice_frontend::bridge::client::BridgeClient;
use alice_frontend::core::dispatcher::{
    EventDispatcher, drain_bridge_messages, is_actionable_stderr_error,
};
use alice_frontend::core::event::EventBus;
use alice_frontend::ui::render_app;

use alice_frontend::util::runtime_log::runtime_log;

/// 终端恢复守卫，确保即使 panic 或信号中断也能还原终端状态。
struct TerminalGuard;

impl Drop for TerminalGuard {
    fn drop(&mut self) {
        disable_raw_mode().ok();
        execute!(
            io::stdout(),
            LeaveAlternateScreen,
            DisableMouseCapture,
            DisableBracketedPaste
        )
        .ok();
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    runtime_log("main", "system.start", "phase=frontend.main.start");

    // 启动 Python 后端
    runtime_log("main", "system.start", "phase=backend.spawn.request");
    let bridge_client = match BridgeClient::spawn_default() {
        Ok(client) => {
            runtime_log("main", "system.start", "phase=backend.spawn.connected");
            client
        }
        Err(err) => {
            runtime_log(
                "main",
                "bridge.error",
                &format!("phase=backend.spawn error={}", err),
            );
            return Err(err.into());
        }
    };

    // 初始化事件总线
    let event_bus = EventBus::new();

    // 初始化应用状态
    let mut app = App::new(bridge_client);

    // 初始化事件分发器
    let mut dispatcher = EventDispatcher::new(event_bus);

    // 初始化终端（guard 在作用域结束时自动恢复终端）
    let _guard = TerminalGuard;
    runtime_log("main", "system.start", "phase=raw_mode.init.start");
    enable_raw_mode().map_err(|err| {
        runtime_log(
            "main",
            "bridge.error",
            &format!("phase=raw_mode.init error={}", err),
        );
        err
    })?;
    let mut stdout = io::stdout();
    execute!(
        stdout,
        EnterAlternateScreen,
        EnableMouseCapture,
        EnableBracketedPaste
    )
    .map_err(|err| {
        runtime_log(
            "main",
            "bridge.error",
            &format!("phase=terminal.enter_alternate_screen error={}", err),
        );
        err
    })?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend).map_err(|err| {
        runtime_log(
            "main",
            "bridge.error",
            &format!("phase=terminal.new error={}", err),
        );
        err
    })?;
    runtime_log("main", "system.start", "phase=raw_mode.init.ready");

    let tick_rate = Duration::from_millis(100);
    let min_poll = Duration::from_millis(5);
    let mut last_tick = Instant::now();
    let exit_reason: &str;

    // 主事件循环
    loop {
        // 处理来自后端的消息
        if !drain_bridge_messages(&mut app, &mut dispatcher) {
            exit_reason = "bridge_message_channel_closed";
            runtime_log(
                "main",
                "bridge.eof",
                "phase=event_loop.bridge_messages reason=channel_closed",
            );
            break;
        }

        // 处理来自后端的错误
        while let Some(err) = app.bridge_client.try_recv_error() {
            if is_actionable_stderr_error(&err) {
                runtime_log(
                    "main",
                    "bridge.error",
                    &format!("phase=event_loop.backend_error summary={}", err),
                );
                dispatcher.handle_bridge_error(&mut app, err);
            } else {
                runtime_log(
                    "main",
                    "bridge.stderr",
                    &format!("phase=event_loop.backend_stderr summary={}", err),
                );
            }
        }

        // 渲染 UI
        terminal.draw(|f| render_app(f, &mut app)).map_err(|err| {
            runtime_log(
                "main",
                "bridge.error",
                &format!("phase=terminal.draw error={}", err),
            );
            err
        })?;
        dispatcher.update_areas(
            app.area_bounds.chat_area,
            app.area_bounds.sidebar_area,
            app.area_bounds.input_area,
        );

        // 处理终端事件（保底 5ms 阻塞避免空转漏事件）
        let timeout = tick_rate
            .checked_sub(last_tick.elapsed())
            .unwrap_or(min_poll)
            .max(min_poll);

        if event::poll(timeout).map_err(|err| {
            runtime_log(
                "main",
                "bridge.error",
                &format!("phase=event.poll error={}", err),
            );
            err
        })? {
            match event::read().map_err(|err| {
                runtime_log(
                    "main",
                    "bridge.error",
                    &format!("phase=event.read error={}", err),
                );
                err
            })? {
                Event::Key(key) => {
                    dispatcher.handle_key_event(&mut app, key);
                }
                Event::Mouse(mouse) => {
                    dispatcher.handle_mouse_event(&mut app, mouse);
                }
                Event::Paste(text) => {
                    if app.status.can_accept_input() {
                        app.input.push_str(&text);
                    }
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
            exit_reason = "app_should_quit";
            break;
        }
    }

    runtime_log(
        "main",
        "system.shutdown",
        &format!("phase=frontend.main.exit reason={}", exit_reason),
    );

    // terminal 恢复由 _guard 的 Drop 完成
    drop(terminal);

    runtime_log("main", "system.shutdown", "phase=frontend.main.done");

    Ok(())
}
