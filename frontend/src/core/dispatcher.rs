//! # 事件分发器
//!
//! 统一处理和分发各类事件，协调键盘、鼠标和后端消息事件。

use std::io::Write;
use std::time::Duration;

use crossterm::event::{self, Event as CrosstermEvent};
use ratatui::layout::Rect;

use crate::app::state::{AgentStatus as AppAgentStatus, App};
use crate::bridge::protocol::message::{BridgeMessage, StatusContent};
use crate::util::runtime_log::runtime_log;

use super::event::{AppEvent, EventBus};
use super::handler::{KeyAction, KeyboardHandler, MouseAction, MouseHandler};

/// Strip ANSI escape sequences from a string.
fn strip_ansi_codes(s: &str) -> String {
    let mut result = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();
    while let Some(ch) = chars.next() {
        if ch == '\x1b' {
            if chars.peek() == Some(&'[') {
                chars.next(); // consume '['
                // consume parameter bytes (0x30-0x3f)
                while let Some(&c) = chars.peek() {
                    if ('\x30'..='\x3f').contains(&c) {
                        chars.next();
                    } else {
                        break;
                    }
                }
                // consume intermediate bytes (0x20-0x2f)
                while let Some(&c) = chars.peek() {
                    if ('\x20'..='\x2f').contains(&c) {
                        chars.next();
                    } else {
                        break;
                    }
                }
                // consume final byte (0x40-0x7e)
                if let Some(&c) = chars.peek() {
                    if ('\x40'..='\x7e').contains(&c) {
                        chars.next();
                    }
                }
            }
        } else {
            result.push(ch);
        }
    }
    result
}

/// Determine if a stderr line represents an actionable error that should be
/// surfaced to the user in the TUI.
///
/// - Python log-format lines (starting with `YYYY-MM-DD`): only ERROR/CRITICAL/Traceback
/// - Non-Python-log stderr content: treated as actionable
pub fn is_actionable_stderr_error(line: &str) -> bool {
    let stripped = strip_ansi_codes(line);
    let trimmed = stripped.trim();

    if trimmed.is_empty() {
        return false;
    }

    // Check if it looks like a Python log line: starts with YYYY-MM-DD timestamp
    if trimmed.len() >= 10
        && trimmed.as_bytes()[4] == b'-'
        && trimmed.as_bytes()[7] == b'-'
        && trimmed[..4].chars().all(|c| c.is_ascii_digit())
    {
        // It's a Python log line — only actionable if ERROR/CRITICAL/Traceback
        return trimmed.contains("[ERROR]")
            || trimmed.contains("[CRITICAL]")
            || trimmed.contains("Traceback");
    }

    // Non-Python-log stderr content (e.g. direct print to stderr) is always actionable
    true
}

/// 应用状态枚举
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum AppState {
    Starting,
    Idle,
    Thinking,
    Responding,
    ExecutingTool,
}

impl AppState {
    /// 检查是否可以接受用户输入
    pub fn can_accept_input(self) -> bool {
        matches!(self, AppState::Idle)
    }

    /// 检查是否可以中断
    pub fn can_interrupt(self) -> bool {
        !matches!(self, AppState::Idle | AppState::Starting)
    }
}

/// 事件分发器
///
/// 负责从 crossterm 读取原始事件，并通过处理器转换为应用指令。
/// 这是事件循环的核心组件。
pub struct EventDispatcher {
    /// 事件总线
    event_bus: EventBus,
    /// 键盘处理器
    keyboard: KeyboardHandler,
    /// 鼠标处理器
    mouse: MouseHandler,
    /// 当前应用状态
    state: AppState,
    /// 是否应退出
    should_quit: bool,
}

pub fn drain_bridge_messages(app: &mut App, dispatcher: &mut EventDispatcher) -> bool {
    while let Some(msg_result) = app.bridge_client.try_recv_message() {
        match msg_result {
            Ok(msg) => dispatcher.handle_bridge_message(app, msg),
            Err(err) => {
                dispatcher.handle_bridge_error(app, format!("Backend connection lost: {}", err));
                app.should_quit = true;
                dispatcher.should_quit = true;
                return false;
            }
        }
    }

    true
}

impl EventDispatcher {
    /// 创建新的事件分发器
    pub fn new(event_bus: EventBus) -> Self {
        Self {
            event_bus,
            keyboard: KeyboardHandler::new(),
            mouse: MouseHandler::new(),
            state: AppState::Starting,
            should_quit: false,
        }
    }

    /// 获取事件总线引用
    pub fn event_bus(&self) -> &EventBus {
        &self.event_bus
    }

    /// 获取事件总线发送器
    pub fn sender(&self) -> std::sync::mpsc::Sender<AppEvent> {
        self.event_bus.sender()
    }

    /// 获取键盘处理器引用
    pub fn keyboard(&self) -> &KeyboardHandler {
        &self.keyboard
    }

    /// 获取键盘处理器可变引用
    pub fn keyboard_mut(&mut self) -> &mut KeyboardHandler {
        &mut self.keyboard
    }

    /// 获取鼠标处理器引用
    pub fn mouse(&self) -> &MouseHandler {
        &self.mouse
    }

    /// 获取鼠标处理器可变引用
    pub fn mouse_mut(&mut self) -> &mut MouseHandler {
        &mut self.mouse
    }

    /// 更新应用状态
    pub fn set_state(&mut self, state: AppState) {
        self.state = state;
        self.keyboard
            .set_status(convert_state_to_agent_status(state));
    }

    /// 更新侧边栏显示状态
    pub fn set_show_thinking(&mut self, show: bool) {
        self.keyboard.set_show_thinking(show);
        self.mouse.set_show_thinking(show);
    }

    /// 更新 UI 区域边界
    pub fn update_areas(&mut self, chat_area: Rect, sidebar_area: Rect, input_area: Rect) {
        self.mouse.update_areas(chat_area, sidebar_area, input_area);
    }

    /// 获取当前状态
    pub fn state(&self) -> AppState {
        self.state
    }

    /// 检查是否应该退出
    pub fn should_quit(&self) -> bool {
        self.should_quit
    }

    /// 设置退出标志
    pub fn set_should_quit(&mut self, value: bool) {
        self.should_quit = value;
    }

    /// 处理 crossterm 事件（带超时）
    ///
    /// 这是主事件循环的核心方法。它：
    /// 1. 等待 crossterm 事件（带超时）
    /// 2. 将事件分发给对应的处理器
    /// 3. 返回是否发生了事件
    pub fn dispatch_crossterm(&mut self, timeout: Duration) -> Result<bool, std::io::Error> {
        if !event::poll(timeout)? {
            return Ok(false);
        }

        match event::read()? {
            CrosstermEvent::Key(key) => {
                let action = self.keyboard.handle_crossterm_event(key);
                self.handle_key_action(action);
                Ok(true)
            }
            CrosstermEvent::Mouse(mouse) => {
                let action = self.mouse.handle_crossterm_event(mouse);
                self.handle_mouse_action(action);
                Ok(true)
            }
            _ => Ok(false),
        }
    }

    /// 处理内部应用事件
    pub fn dispatch_app_event(&mut self, event: &AppEvent) {
        match event {
            AppEvent::Quit => {
                self.should_quit = true;
            }
            AppEvent::Tick => {
                // 刻度事件由外部处理
            }
            _ => {}
        }
    }

    /// 处理键盘动作
    fn handle_key_action(&mut self, action: KeyAction) {
        match action {
            KeyAction::Quit => {
                self.should_quit = true;
            }
            KeyAction::ToggleThinking
            | KeyAction::InputChar(_)
            | KeyAction::Backspace
            | KeyAction::SendMessage
            | KeyAction::Interrupt
            | KeyAction::ScrollUp
            | KeyAction::ScrollDown
            | KeyAction::ScrollToTop
            | KeyAction::ScrollToBottom
            | KeyAction::Copy
            | KeyAction::Paste => {
                // 由 apply_key_action 处理
            }
            KeyAction::None => {}
        }
    }

    /// 处理鼠标动作
    fn handle_mouse_action(&mut self, action: MouseAction) {
        match action {
            MouseAction::ChatScrollUp
            | MouseAction::ChatScrollDown
            | MouseAction::SidebarScrollUp
            | MouseAction::SidebarScrollDown
            | MouseAction::Click { .. }
            | MouseAction::Drag { .. }
            | MouseAction::Move { .. }
            | MouseAction::Release { .. } => {
                // 由 apply_mouse_action 处理
            }
            MouseAction::None => {}
        }
    }

    /// 处理来自后端桥接的消息
    pub fn handle_bridge_message(&mut self, app: &mut App, msg: BridgeMessage) {
        match msg {
            BridgeMessage::Status { content } => {
                app.bridge_client.handle_status_message(&content);
                match content {
                    StatusContent::Ready => {
                        app.handle_ready();
                        self.set_state(AppState::Idle);
                    }
                    StatusContent::Thinking => {
                        app.set_thinking();
                        self.set_state(AppState::Thinking);
                    }
                    StatusContent::ExecutingTool => {
                        app.set_executing_tool();
                        self.set_state(AppState::ExecutingTool);
                    }
                    StatusContent::Done => {
                        app.mark_current_complete();
                        app.set_idle();
                        self.set_state(AppState::Idle);
                    }
                }
            }
            BridgeMessage::Thinking { content } => {
                app.append_thinking(&content);
                app.set_thinking();
                self.set_state(AppState::Thinking);
            }
            BridgeMessage::Content { content } => {
                app.append_content(&content);
                app.set_responding();
                self.set_state(AppState::Responding);
            }
            BridgeMessage::Tokens {
                total,
                prompt,
                completion,
            } => {
                app.tokens.update(total, prompt, completion);
            }
            BridgeMessage::Error { content } => {
                self.handle_bridge_error(app, content);
            }
            BridgeMessage::Interrupt => {}
        }

        self.set_show_thinking(app.show_thinking);
    }

    /// 处理来自后端桥接的错误
    pub fn handle_bridge_error(&mut self, app: &mut App, err: String) {
        app.mark_current_complete();
        app.add_error(err.clone());
        app.set_idle();
        self.set_state(AppState::Idle);
        runtime_log("dispatcher", "bridge.error", &format!("summary={}", err));
    }

    /// 处理键盘事件
    pub fn handle_key_event(&mut self, app: &mut App, key: crossterm::event::KeyEvent) {
        let action = self.keyboard.handle_crossterm_event(key);
        self.apply_key_action(app, action);
    }

    /// 处理鼠标事件
    pub fn handle_mouse_event(&mut self, app: &mut App, mouse: crossterm::event::MouseEvent) {
        let action = self.mouse.handle_crossterm_event(mouse);
        self.apply_mouse_action(app, action);
    }

    /// 发送中断信号到后端
    ///
    /// 通过 child_stdin 发送 __INTERRUPT__ 信号
    pub fn send_interrupt(
        &self,
        stdin: &mut std::process::ChildStdin,
    ) -> Result<(), std::io::Error> {
        writeln!(stdin, "__INTERRUPT__")
    }

    fn apply_key_action(&mut self, app: &mut App, action: KeyAction) {
        match action {
            KeyAction::Quit => {
                self.should_quit = true;
                app.should_quit = true;
            }
            KeyAction::ToggleThinking => {
                app.toggle_thinking();
                self.set_show_thinking(app.show_thinking);
            }
            KeyAction::InputChar(ch) => {
                if app.status.can_accept_input() {
                    app.input.push(ch);
                }
            }
            KeyAction::Backspace => {
                app.input.pop();
            }
            KeyAction::SendMessage => {
                app.send_message();
                self.sync_from_app(app);
            }
            KeyAction::Interrupt => {
                app.interrupt();
                self.sync_from_app(app);
            }
            KeyAction::ScrollUp => {
                self.active_scroll_state(app).scroll_up();
            }
            KeyAction::ScrollDown => {
                self.active_scroll_state(app).scroll_down();
            }
            KeyAction::ScrollToTop => {
                let scroll_state = self.active_scroll_state(app);
                scroll_state.offset = 0;
                scroll_state.auto_scroll = false;
            }
            KeyAction::ScrollToBottom => {
                self.active_scroll_state(app).reset();
            }
            KeyAction::None => {}
            KeyAction::Copy => {
                if !app.selection.has_selection() {
                    return;
                }
                let line_texts = match app.selection.area {
                    crate::core::event::types::UiArea::Chat
                    | crate::core::event::types::UiArea::Input => app.chat_content_lines.clone(),
                    crate::core::event::types::UiArea::Sidebar => app.sidebar_content_lines.clone(),
                    crate::core::event::types::UiArea::None => Vec::new(),
                };
                app.selection.extract_text(&line_texts);
                if let Err(e) = app.selection.copy_to_clipboard() {
                    runtime_log("dispatcher", "clipboard.error", &format!("copy: {}", e));
                }
            }
            KeyAction::Paste => {
                match crate::app::selection::SelectionState::paste_from_clipboard() {
                    Ok(text) => {
                        runtime_log(
                            "dispatcher",
                            "clipboard.paste",
                            &format!("len={}", text.len()),
                        );
                        app.input.push_str(&text);
                    }
                    Err(e) => {
                        runtime_log("dispatcher", "clipboard.error", &format!("paste: {}", e));
                    }
                }
            }
        }
    }

    fn apply_mouse_action(&mut self, app: &mut App, action: MouseAction) {
        match action {
            MouseAction::ChatScrollUp => {
                app.chat_scroll.scroll_up();
            }
            MouseAction::ChatScrollDown => {
                app.chat_scroll.scroll_down();
            }
            MouseAction::SidebarScrollUp => {
                app.thinking_scroll.scroll_up();
            }
            MouseAction::SidebarScrollDown => {
                app.thinking_scroll.scroll_down();
            }
            MouseAction::Click { area, x, y } => {
                if area != crate::core::event::types::UiArea::None {
                    let (rect, scroll) = match area {
                        crate::core::event::types::UiArea::Chat => {
                            (app.area_bounds.chat_area, app.chat_scroll.offset)
                        }
                        crate::core::event::types::UiArea::Sidebar => {
                            (app.area_bounds.sidebar_area, app.thinking_scroll.offset)
                        }
                        crate::core::event::types::UiArea::Input => {
                            (app.area_bounds.input_area, 0usize)
                        }
                        crate::core::event::types::UiArea::None => {
                            (ratatui::layout::Rect::default(), 0)
                        }
                    };
                    let (line, col) = crate::app::selection::screen_to_content(x, y, rect, scroll);
                    app.selection.start(area, line, col);
                } else {
                    app.selection.clear();
                }
            }
            MouseAction::Drag {
                area, to_x, to_y, ..
            }
            | MouseAction::Move {
                area,
                x: to_x,
                y: to_y,
            } => {
                if app.selection.active && app.selection.area == area {
                    let (rect, scroll) = match area {
                        crate::core::event::types::UiArea::Chat => {
                            (app.area_bounds.chat_area, app.chat_scroll.offset)
                        }
                        crate::core::event::types::UiArea::Sidebar => {
                            (app.area_bounds.sidebar_area, app.thinking_scroll.offset)
                        }
                        crate::core::event::types::UiArea::Input => {
                            (app.area_bounds.input_area, 0usize)
                        }
                        crate::core::event::types::UiArea::None => {
                            (ratatui::layout::Rect::default(), 0)
                        }
                    };
                    let (line, col) =
                        crate::app::selection::screen_to_content(to_x, to_y, rect, scroll);
                    app.selection.update(line, col);
                }
            }
            MouseAction::Release { .. } => {
                if app.selection.active {
                    app.selection.end();
                }
            }
            MouseAction::None => {}
        }
    }

    fn active_scroll_state<'a>(
        &self,
        app: &'a mut App,
    ) -> &'a mut crate::core::event::types::ScrollState {
        if self.keyboard.should_scroll_sidebar() {
            &mut app.thinking_scroll
        } else {
            &mut app.chat_scroll
        }
    }

    fn sync_from_app(&mut self, app: &App) {
        self.set_state(convert_agent_status_to_app_state(app.status));
        self.set_show_thinking(app.show_thinking);
    }
}

impl Default for EventDispatcher {
    fn default() -> Self {
        Self::new(EventBus::new())
    }
}

/// 转换 AppState 到键盘处理器需要的 AgentStatus
fn convert_state_to_agent_status(
    state: AppState,
) -> crate::core::handler::keyboard_handler::AgentStatus {
    match state {
        AppState::Starting => crate::core::handler::keyboard_handler::AgentStatus::Starting,
        AppState::Idle => crate::core::handler::keyboard_handler::AgentStatus::Idle,
        AppState::Thinking => crate::core::handler::keyboard_handler::AgentStatus::Thinking,
        AppState::Responding => crate::core::handler::keyboard_handler::AgentStatus::Responding,
        AppState::ExecutingTool => {
            crate::core::handler::keyboard_handler::AgentStatus::ExecutingTool
        }
    }
}

fn convert_agent_status_to_app_state(status: AppAgentStatus) -> AppState {
    match status {
        AppAgentStatus::Starting => AppState::Starting,
        AppAgentStatus::Idle => AppState::Idle,
        AppAgentStatus::Thinking => AppState::Thinking,
        AppAgentStatus::Responding => AppState::Responding,
        AppAgentStatus::ExecutingTool => AppState::ExecutingTool,
    }
}

/// 事件循环辅助函数
///
/// 提供事件循环的通用模式
pub struct EventLoop {
    /// 事件分发器
    dispatcher: EventDispatcher,
    /// 刻度速率
    tick_rate: Duration,
    /// 上次刻度时间
    last_tick: std::time::Instant,
}

impl EventLoop {
    /// 创建新的事件循环
    pub fn new(dispatcher: EventDispatcher, tick_rate: Duration) -> Self {
        Self {
            dispatcher,
            tick_rate,
            last_tick: std::time::Instant::now(),
        }
    }

    /// 获取分发器引用
    pub fn dispatcher(&self) -> &EventDispatcher {
        &self.dispatcher
    }

    /// 获取分发器可变引用
    pub fn dispatcher_mut(&mut self) -> &mut EventDispatcher {
        &mut self.dispatcher
    }

    /// 运行一步事件循环
    ///
    /// 返回是否需要继续运行
    pub fn step(&mut self) -> Result<bool, std::io::Error> {
        // 计算超时时间
        let timeout = self
            .tick_rate
            .checked_sub(self.last_tick.elapsed())
            .unwrap_or_else(|| Duration::from_secs(0));

        // 处理 crossterm 事件
        self.dispatcher.dispatch_crossterm(timeout)?;

        // 检查是否需要刻度
        if self.last_tick.elapsed() >= self.tick_rate {
            self.dispatcher.sender().send(AppEvent::Tick).ok();
            self.last_tick = std::time::Instant::now();
        }

        Ok(!self.dispatcher.should_quit())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc;

    use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

    use crate::app::state::{Author, Message};
    use crate::bridge::client::BridgeClient;

    fn create_app_and_dispatcher() -> (
        App,
        EventDispatcher,
        mpsc::Sender<BridgeMessage>,
        mpsc::Sender<String>,
    ) {
        let (msg_tx, msg_rx) = mpsc::channel();
        let (err_tx, err_rx) = mpsc::channel();
        let bridge_client = BridgeClient::with_test_channels(msg_rx, err_rx).unwrap();

        (
            App::new(bridge_client),
            EventDispatcher::new(EventBus::new()),
            msg_tx,
            err_tx,
        )
    }

    #[test]
    fn test_app_state_can_accept_input() {
        assert!(AppState::Idle.can_accept_input());
        assert!(!AppState::Thinking.can_accept_input());
        assert!(!AppState::Responding.can_accept_input());
        assert!(!AppState::ExecutingTool.can_accept_input());
        assert!(!AppState::Starting.can_accept_input());
    }

    #[test]
    fn test_app_state_can_interrupt() {
        assert!(!AppState::Idle.can_interrupt());
        assert!(AppState::Thinking.can_interrupt());
        assert!(AppState::Responding.can_interrupt());
        assert!(AppState::ExecutingTool.can_interrupt());
        assert!(!AppState::Starting.can_interrupt());
    }

    #[test]
    fn test_dispatcher_creation() {
        let bus = EventBus::new();
        let dispatcher = EventDispatcher::new(bus);

        assert_eq!(dispatcher.state(), AppState::Starting);
        assert!(!dispatcher.should_quit());
    }

    #[test]
    fn test_dispatcher_set_state() {
        let bus = EventBus::new();
        let mut dispatcher = EventDispatcher::new(bus);

        dispatcher.set_state(AppState::Thinking);
        assert_eq!(dispatcher.state(), AppState::Thinking);
    }

    #[test]
    fn test_dispatcher_quit() {
        let bus = EventBus::new();
        let mut dispatcher = EventDispatcher::new(bus);

        dispatcher.dispatch_app_event(&AppEvent::Quit);
        assert!(dispatcher.should_quit());
    }

    #[test]
    fn test_set_show_thinking() {
        let bus = EventBus::new();
        let mut dispatcher = EventDispatcher::new(bus);

        dispatcher.set_show_thinking(true);
        // 测试是否正确设置（通过检查鼠标处理器）
        assert!(!dispatcher.mouse().is_in_sidebar_area(100, 100)); // 默认区域
    }

    #[test]
    fn test_handle_bridge_ready_updates_app() {
        let (mut app, mut dispatcher, _msg_tx, _err_tx) = create_app_and_dispatcher();

        dispatcher.handle_bridge_message(
            &mut app,
            BridgeMessage::Status {
                content: StatusContent::Ready,
            },
        );

        assert_eq!(app.status, AppAgentStatus::Idle);
        assert_eq!(dispatcher.state(), AppState::Idle);
        assert!(app.messages[0].content.contains("准备好了"));
    }

    #[test]
    fn test_handle_bridge_stream_updates_message_and_completion() {
        let (mut app, mut dispatcher, _msg_tx, _err_tx) = create_app_and_dispatcher();
        app.handle_ready();
        dispatcher.set_state(AppState::Idle);
        app.messages.push(Message::assistant_pending());

        dispatcher.handle_bridge_message(
            &mut app,
            BridgeMessage::Thinking {
                content: "分析中".into(),
            },
        );
        dispatcher.handle_bridge_message(
            &mut app,
            BridgeMessage::Content {
                content: "你好".into(),
            },
        );

        assert_eq!(app.status, AppAgentStatus::Responding);
        assert_eq!(dispatcher.state(), AppState::Responding);
        assert_eq!(app.messages.last().unwrap().thinking, "分析中");
        assert_eq!(app.messages.last().unwrap().content, "你好");

        dispatcher.handle_bridge_message(
            &mut app,
            BridgeMessage::Status {
                content: StatusContent::Done,
            },
        );

        assert_eq!(app.status, AppAgentStatus::Idle);
        assert_eq!(dispatcher.state(), AppState::Idle);
        assert!(app.messages.last().unwrap().is_complete);
    }

    #[test]
    fn test_handle_bridge_error_updates_app() {
        let (mut app, mut dispatcher, _msg_tx, _err_tx) = create_app_and_dispatcher();
        app.handle_ready();
        dispatcher.set_state(AppState::Idle);
        app.messages.push(Message::assistant_pending());
        app.set_responding();
        dispatcher.set_state(AppState::Responding);

        dispatcher.handle_bridge_message(
            &mut app,
            BridgeMessage::Error {
                content: "boom".into(),
            },
        );

        assert_eq!(app.status, AppAgentStatus::Idle);
        assert_eq!(dispatcher.state(), AppState::Idle);
        assert!(app.messages[1].is_complete);
        assert!(app.messages.last().unwrap().content.contains("boom"));
    }

    #[test]
    fn test_handle_bridge_tokens_updates_app() {
        let (mut app, mut dispatcher, _msg_tx, _err_tx) = create_app_and_dispatcher();

        dispatcher.handle_bridge_message(
            &mut app,
            BridgeMessage::Tokens {
                total: 12,
                prompt: 5,
                completion: 7,
            },
        );

        assert_eq!(app.tokens.total, 12);
        assert_eq!(app.tokens.prompt, 5);
        assert_eq!(app.tokens.completion, 7);
    }

    #[test]
    fn test_handle_key_event_updates_input_and_sends_message() {
        let (mut app, mut dispatcher, _msg_tx, _err_tx) = create_app_and_dispatcher();
        app.handle_ready();
        dispatcher.set_state(AppState::Idle);

        dispatcher.handle_key_event(
            &mut app,
            KeyEvent::new(KeyCode::Char('h'), KeyModifiers::empty()),
        );
        dispatcher.handle_key_event(
            &mut app,
            KeyEvent::new(KeyCode::Char('i'), KeyModifiers::empty()),
        );
        dispatcher.handle_key_event(
            &mut app,
            KeyEvent::new(KeyCode::Backspace, KeyModifiers::empty()),
        );
        dispatcher.handle_key_event(
            &mut app,
            KeyEvent::new(KeyCode::Char('!'), KeyModifiers::empty()),
        );

        assert_eq!(app.input, "h!");

        dispatcher.handle_key_event(
            &mut app,
            KeyEvent::new(KeyCode::Enter, KeyModifiers::empty()),
        );

        assert!(app.input.is_empty());
        assert_eq!(app.status, AppAgentStatus::Thinking);
        assert_eq!(dispatcher.state(), AppState::Thinking);
        assert_eq!(app.messages[1].author, Author::User);
        assert_eq!(app.messages[1].content, "h!");
        assert_eq!(app.messages.last().unwrap().author, Author::Assistant);
        assert!(!app.messages.last().unwrap().is_complete);
    }

    #[test]
    fn test_handle_key_event_toggle_scroll_and_quit() {
        let (mut app, mut dispatcher, _msg_tx, _err_tx) = create_app_and_dispatcher();
        app.handle_ready();
        dispatcher.set_state(AppState::Idle);

        dispatcher.handle_key_event(
            &mut app,
            KeyEvent::new(KeyCode::Char('o'), KeyModifiers::CONTROL),
        );
        dispatcher.handle_key_event(
            &mut app,
            KeyEvent::new(KeyCode::Down, KeyModifiers::empty()),
        );

        assert!(app.show_thinking);
        assert_eq!(app.thinking_scroll.offset, 1);
        assert_eq!(app.chat_scroll.offset, 0);

        dispatcher.handle_key_event(
            &mut app,
            KeyEvent::new(KeyCode::Char('d'), KeyModifiers::CONTROL),
        );

        assert!(app.should_quit);
        assert!(dispatcher.should_quit());
    }

    #[test]
    fn test_drain_bridge_messages_stops_on_disconnect() {
        let (msg_tx, msg_rx) = mpsc::channel::<BridgeMessage>();
        let (_err_tx, err_rx) = mpsc::channel::<String>();
        drop(msg_tx);
        let bridge_client = BridgeClient::with_test_channels(msg_rx, err_rx).unwrap();
        let mut app = App::new(bridge_client);
        let mut dispatcher = EventDispatcher::new(EventBus::new());

        assert!(!drain_bridge_messages(&mut app, &mut dispatcher));
        assert!(app.should_quit);
        assert!(dispatcher.should_quit());
        assert!(
            app.messages
                .last()
                .unwrap()
                .content
                .contains("Backend connection lost")
        );
    }
}
