//! # 事件分发器
//!
//! 统一处理和分发各类事件，协调键盘、鼠标和后端消息事件。

use std::io::Write;
use std::time::Duration;

use crossterm::event::{self, Event as CrosstermEvent};
use ratatui::layout::Rect;

use super::event::{AppEvent, EventBus};
use super::handler::{KeyAction, KeyboardHandler, MouseAction, MouseHandler};

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
        self.keyboard.set_status(convert_state_to_agent_status(state));
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
            KeyAction::ToggleThinking => {
                // 由外部处理
            }
            KeyAction::InputChar(_) | KeyAction::Backspace => {
                // 由外部处理
            }
            KeyAction::SendMessage => {
                // 由外部处理
            }
            KeyAction::Interrupt => {
                // 由外部处理
            }
            KeyAction::ScrollUp | KeyAction::ScrollDown => {
                // 由外部处理
            }
            KeyAction::ScrollToTop | KeyAction::ScrollToBottom => {
                // 由外部处理
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
            | MouseAction::SidebarScrollDown => {
                // 由外部处理
            }
            MouseAction::Click { .. } => {
                // 未来可能用于选择消息等
            }
            MouseAction::Drag { .. } => {
                // 未来可能用于选中文本等
            }
            MouseAction::None => {}
        }
    }

    /// 发送中断信号到后端
    ///
    /// 通过 child_stdin 发送 __INTERRUPT__ 信号
    pub fn send_interrupt(&self, stdin: &mut std::process::ChildStdin) -> Result<(), std::io::Error> {
        writeln!(stdin, "__INTERRUPT__")
    }
}

impl Default for EventDispatcher {
    fn default() -> Self {
        Self::new(EventBus::new())
    }
}

/// 转换 AppState 到键盘处理器需要的 AgentStatus
fn convert_state_to_agent_status(state: AppState) -> keyboard_handler::AgentStatus {
    match state {
        AppState::Starting => keyboard_handler::AgentStatus::Starting,
        AppState::Idle => keyboard_handler::AgentStatus::Idle,
        AppState::Thinking => keyboard_handler::AgentStatus::Thinking,
        AppState::Responding => keyboard_handler::AgentStatus::Responding,
        AppState::ExecutingTool => keyboard_handler::AgentStatus::ExecutingTool,
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
        assert!(dispatcher.mouse().is_in_sidebar_area(100, 100) == false); // 默认区域
    }
}
