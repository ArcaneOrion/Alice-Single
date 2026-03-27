//! # 键盘事件处理器
//!
//! 处理键盘输入事件，转换为应用命令或状态变更。

use crossterm::event::{KeyCode as CrosstermKeyCode, KeyEvent, KeyEventKind, KeyModifiers};

use crate::core::event::types::{KeyCode, KeyModifiers as OurKeyModifiers, KeyboardEvent, UiArea};

/// 键盘事件处理结果
#[derive(Debug, Clone, PartialEq)]
pub enum KeyAction {
    /// 无操作
    None,
    /// 退出应用
    Quit,
    /// 切换思考侧边栏显示
    ToggleThinking,
    /// 输入字符
    InputChar(char),
    /// 删除字符
    Backspace,
    /// 发送消息
    SendMessage,
    /// 中断当前操作
    Interrupt,
    /// 向上滚动
    ScrollUp,
    /// 向下滚动
    ScrollDown,
    /// 滚动到顶部
    ScrollToTop,
    /// 滚动到底部
    ScrollToBottom,
}

/// 键盘事件处理器
///
/// 负责将原始键盘事件转换为应用级别的操作指令。
/// 保持与原 main.rs 中键盘处理逻辑的一致性。
pub struct KeyboardHandler {
    /// 当前 Agent 状态
    status: AgentStatus,
    /// 是否显示思考侧边栏
    show_thinking: bool,
    /// 当前焦点区域
    focus_area: UiArea,
}

impl KeyboardHandler {
    /// 创建新的键盘处理器
    pub fn new() -> Self {
        Self {
            status: AgentStatus::Idle,
            show_thinking: false,
            focus_area: UiArea::Input,
        }
    }

    /// 更新 Agent 状态
    pub fn set_status(&mut self, status: AgentStatus) {
        self.status = status;
    }

    /// 更新侧边栏显示状态
    pub fn set_show_thinking(&mut self, show: bool) {
        self.show_thinking = show;
    }

    /// 更新焦点区域
    pub fn set_focus_area(&mut self, area: UiArea) {
        self.focus_area = area;
    }

    /// 处理 crossterm 键盘事件
    pub fn handle_crossterm_event(&self, event: KeyEvent) -> KeyAction {
        // 忽略释放事件
        if event.kind == KeyEventKind::Release {
            return KeyAction::None;
        }

        self.handle_key_code(event.code, event.modifiers)
    }

    /// 处理键盘事件
    pub fn handle(&self, event: &KeyboardEvent) -> KeyAction {
        if event.is_release {
            return KeyAction::None;
        }
        self.handle_key_code_inner(event.code, event.modifiers)
    }

    /// 处理按键代码（crossterm 版本）
    fn handle_key_code(&self, code: CrosstermKeyCode, modifiers: KeyModifiers) -> KeyAction {
        // Ctrl+C: 退出
        if code == CrosstermKeyCode::Char('c') && modifiers.contains(KeyModifiers::CONTROL) {
            return KeyAction::Quit;
        }

        // Ctrl+O: 切换思考侧边栏
        if code == CrosstermKeyCode::Char('o') && modifiers.contains(KeyModifiers::CONTROL) {
            return KeyAction::ToggleThinking;
        }

        // 根据按键代码处理
        match code {
            // 字符输入：仅在 Idle 状态下允许
            CrosstermKeyCode::Char(c) => {
                if self.status == AgentStatus::Idle {
                    KeyAction::InputChar(c)
                } else {
                    KeyAction::None
                }
            }

            // Backspace: 删除字符
            CrosstermKeyCode::Backspace => KeyAction::Backspace,

            // Enter: 发送消息
            CrosstermKeyCode::Enter => KeyAction::SendMessage,

            // Esc: 中断当前操作
            CrosstermKeyCode::Esc => {
                if self.status != AgentStatus::Idle {
                    KeyAction::Interrupt
                } else {
                    KeyAction::None
                }
            }

            // Up: 向上滚动
            CrosstermKeyCode::Up => KeyAction::ScrollUp,

            // Down: 向下滚动
            CrosstermKeyCode::Down => KeyAction::ScrollDown,

            // Page Up/Page Down
            CrosstermKeyCode::PageUp => KeyAction::ScrollToTop,
            CrosstermKeyCode::PageDown => KeyAction::ScrollToBottom,

            _ => KeyAction::None,
        }
    }

    /// 处理按键代码（内部版本）
    fn handle_key_code_inner(&self, code: KeyCode, modifiers: OurKeyModifiers) -> KeyAction {
        // Ctrl+C: 退出
        if matches!(code, KeyCode::Char('c')) && modifiers.contains_control() {
            return KeyAction::Quit;
        }

        // Ctrl+O: 切换思考侧边栏
        if matches!(code, KeyCode::Char('o')) && modifiers.contains_control() {
            return KeyAction::ToggleThinking;
        }

        // 根据按键代码处理
        match code {
            // 字符输入：仅在 Idle 状态下允许
            KeyCode::Char(c) => {
                if self.status == AgentStatus::Idle {
                    KeyAction::InputChar(c)
                } else {
                    KeyAction::None
                }
            }

            // Backspace: 删除字符
            KeyCode::Backspace => KeyAction::Backspace,

            // Enter: 发送消息
            KeyCode::Enter => KeyAction::SendMessage,

            // Esc: 中断当前操作
            KeyCode::Esc => {
                if self.status != AgentStatus::Idle {
                    KeyAction::Interrupt
                } else {
                    KeyAction::None
                }
            }

            // Up: 向上滚动
            KeyCode::Up => KeyAction::ScrollUp,

            // Down: 向下滚动
            KeyCode::Down => KeyAction::ScrollDown,

            // Page Up/Page Down
            KeyCode::PageUp => KeyAction::ScrollToTop,
            KeyCode::PageDown => KeyAction::ScrollToBottom,

            _ => KeyAction::None,
        }
    }

    /// 判断是否应滚动侧边栏
    ///
    /// 规则：如果有侧边栏，优先滚动侧边栏
    pub fn should_scroll_sidebar(&self) -> bool {
        self.show_thinking
    }
}

impl Default for KeyboardHandler {
    fn default() -> Self {
        Self::new()
    }
}

/// Agent 运行状态（复制自 types.rs，避免循环依赖）
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum AgentStatus {
    Starting,
    Idle,
    Thinking,
    Responding,
    ExecutingTool,
}

/// 从 crossterm KeyCode 转换为内部 KeyCode
pub fn convert_key_code(code: CrosstermKeyCode) -> KeyCode {
    match code {
        CrosstermKeyCode::Backspace => KeyCode::Backspace,
        CrosstermKeyCode::Enter => KeyCode::Enter,
        CrosstermKeyCode::Left => KeyCode::Left,
        CrosstermKeyCode::Right => KeyCode::Right,
        CrosstermKeyCode::Up => KeyCode::Up,
        CrosstermKeyCode::Down => KeyCode::Down,
        CrosstermKeyCode::Home => KeyCode::Home,
        CrosstermKeyCode::End => KeyCode::End,
        CrosstermKeyCode::PageUp => KeyCode::PageUp,
        CrosstermKeyCode::PageDown => KeyCode::PageDown,
        CrosstermKeyCode::Tab => KeyCode::Tab,
        CrosstermKeyCode::Delete => KeyCode::Delete,
        CrosstermKeyCode::Insert => KeyCode::Insert,
        CrosstermKeyCode::F(n) => KeyCode::F(n),
        CrosstermKeyCode::Char(c) => KeyCode::Char(c),
        CrosstermKeyCode::Null => KeyCode::Null,
        CrosstermKeyCode::Esc => KeyCode::Esc,
        _ => KeyCode::Null,
    }
}

/// 从 crossterm KeyModifiers 转换为内部 KeyModifiers
pub fn convert_key_modifiers(modifiers: KeyModifiers) -> OurKeyModifiers {
    OurKeyModifiers {
        shift: modifiers.contains(KeyModifiers::SHIFT),
        control: modifiers.contains(KeyModifiers::CONTROL),
        alt: modifiers.contains(KeyModifiers::ALT),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_handler() -> KeyboardHandler {
        let mut handler = KeyboardHandler::new();
        handler.set_status(AgentStatus::Idle);
        handler.set_show_thinking(false);
        handler
    }

    #[test]
    fn test_ctrl_c_quit() {
        let handler = create_handler();
        let event = KeyEvent::new(CrosstermKeyCode::Char('c'), KeyModifiers::CONTROL);
        assert_eq!(handler.handle_crossterm_event(event), KeyAction::Quit);
    }

    #[test]
    fn test_ctrl_o_toggle_thinking() {
        let handler = create_handler();
        let event = KeyEvent::new(CrosstermKeyCode::Char('o'), KeyModifiers::CONTROL);
        assert_eq!(
            handler.handle_crossterm_event(event),
            KeyAction::ToggleThinking
        );
    }

    #[test]
    fn test_char_input_when_idle() {
        let handler = create_handler();
        let event = KeyEvent::new(CrosstermKeyCode::Char('a'), KeyModifiers::empty());
        assert_eq!(
            handler.handle_crossterm_event(event),
            KeyAction::InputChar('a')
        );
    }

    #[test]
    fn test_char_input_when_busy() {
        let mut handler = create_handler();
        handler.set_status(AgentStatus::Thinking);
        let event = KeyEvent::new(CrosstermKeyCode::Char('a'), KeyModifiers::empty());
        assert_eq!(handler.handle_crossterm_event(event), KeyAction::None);
    }

    #[test]
    fn test_backspace() {
        let handler = create_handler();
        let event = KeyEvent::new(CrosstermKeyCode::Backspace, KeyModifiers::empty());
        assert_eq!(handler.handle_crossterm_event(event), KeyAction::Backspace);
    }

    #[test]
    fn test_enter_send_message() {
        let handler = create_handler();
        let event = KeyEvent::new(CrosstermKeyCode::Enter, KeyModifiers::empty());
        assert_eq!(
            handler.handle_crossterm_event(event),
            KeyAction::SendMessage
        );
    }

    #[test]
    fn test_esc_interrupt_when_busy() {
        let mut handler = create_handler();
        handler.set_status(AgentStatus::Thinking);
        let event = KeyEvent::new(CrosstermKeyCode::Esc, KeyModifiers::empty());
        assert_eq!(handler.handle_crossterm_event(event), KeyAction::Interrupt);
    }

    #[test]
    fn test_esc_no_interrupt_when_idle() {
        let handler = create_handler();
        let event = KeyEvent::new(CrosstermKeyCode::Esc, KeyModifiers::empty());
        assert_eq!(handler.handle_crossterm_event(event), KeyAction::None);
    }

    #[test]
    fn test_arrow_keys() {
        let handler = create_handler();
        assert_eq!(
            handler
                .handle_crossterm_event(KeyEvent::new(CrosstermKeyCode::Up, KeyModifiers::empty())),
            KeyAction::ScrollUp
        );
        assert_eq!(
            handler.handle_crossterm_event(KeyEvent::new(
                CrosstermKeyCode::Down,
                KeyModifiers::empty()
            )),
            KeyAction::ScrollDown
        );
    }

    #[test]
    fn test_convert_key_code() {
        assert_eq!(
            convert_key_code(CrosstermKeyCode::Char('a')),
            KeyCode::Char('a')
        );
        assert_eq!(convert_key_code(CrosstermKeyCode::Enter), KeyCode::Enter);
        assert_eq!(convert_key_code(CrosstermKeyCode::Esc), KeyCode::Esc);
        assert_eq!(convert_key_code(CrosstermKeyCode::Up), KeyCode::Up);
    }

    #[test]
    fn test_convert_key_modifiers() {
        let mods = convert_key_modifiers(KeyModifiers::CONTROL);
        assert!(mods.control);
        assert!(!mods.shift);
        assert!(!mods.alt);

        let mods = convert_key_modifiers(KeyModifiers::SHIFT | KeyModifiers::ALT);
        assert!(!mods.control);
        assert!(mods.shift);
        assert!(mods.alt);
    }
}
