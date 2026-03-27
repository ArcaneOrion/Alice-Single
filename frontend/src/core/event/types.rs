//! # 事件类型定义
//!
//! 定义 TUI 系统中使用的所有事件类型。

use ratatui::layout::Rect;

// 重新导出桥接消息类型
pub use crate::bridge::protocol::message::BridgeMessage;

/// 应用事件类型
#[derive(Debug, Clone, PartialEq)]
pub enum AppEvent {
    /// 键盘事件
    Key(KeyboardEvent),
    /// 鼠标事件
    Mouse(MouseEvent),
    /// 刻度事件（定时器触发）
    Tick,
    /// 后端消息事件
    Backend(BridgeMessage),
    /// 退出事件
    Quit,
}

/// 键盘事件
#[derive(Debug, Clone, PartialEq)]
pub struct KeyboardEvent {
    /// 按键代码
    pub code: KeyCode,
    /// 修饰键
    pub modifiers: KeyModifiers,
    /// 是否为释放事件
    pub is_release: bool,
}

/// 鼠标事件
#[derive(Debug, Clone, PartialEq)]
pub struct MouseEvent {
    /// 事件类型
    pub kind: MouseEventKind,
    /// 列位置
    pub column: u16,
    /// 行位置
    pub row: u16,
}

/// 按键代码
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KeyCode {
    /// Backspace 键
    Backspace,
    /// Enter 键
    Enter,
    /// 左箭头
    Left,
    /// 右箭头
    Right,
    /// 上箭头
    Up,
    /// 下箭头
    Down,
    /// Home 键
    Home,
    /// End 键
    End,
    /// Page Up
    PageUp,
    /// Page Down
    PageDown,
    /// Tab 键
    Tab,
    /// Delete 键
    Delete,
    /// Insert 键
    Insert,
    /// F 功能键 (1-12)
    F(u8),
    /// 字符键
    Char(char),
    /// null
    Null,
    /// Esc 键
    Esc,
}

/// 按键修饰键
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct KeyModifiers {
    /// Shift 键
    pub shift: bool,
    /// Control 键
    pub control: bool,
    /// Alt 键
    pub alt: bool,
}

impl KeyModifiers {
    /// 创建空的修饰键状态
    pub fn empty() -> Self {
        Self {
            shift: false,
            control: false,
            alt: false,
        }
    }

    /// 检查是否包含 Control
    pub fn contains_control(self) -> bool {
        self.control
    }
}

/// 鼠标事件类型
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MouseEventKind {
    /// 向上滚动
    ScrollUp,
    /// 向下滚动
    ScrollDown,
    /// 左键点击
    Down(MouseButton),
    /// 左键释放
    Up(MouseButton),
    /// 拖拽
    Drag(MouseButton),
    /// 移动
    Moved,
}

/// 鼠标按钮
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MouseButton {
    /// 左键
    Left,
    /// 右键
    Right,
    /// 中键
    Middle,
}

/// UI 区域类型
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UiArea {
    /// 聊天区域
    Chat,
    /// 侧边栏区域
    Sidebar,
    /// 输入区域
    Input,
    /// 未知区域
    None,
}

/// 滚动状态
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScrollState {
    /// 当前滚动偏移
    pub offset: usize,
    /// 是否自动滚动
    pub auto_scroll: bool,
}

impl ScrollState {
    /// 创建新的滚动状态
    pub fn new() -> Self {
        Self {
            offset: 0,
            auto_scroll: true,
        }
    }

    /// 向上滚动
    pub fn scroll_up(&mut self) {
        if self.offset > 0 {
            self.offset -= 1;
        }
        self.auto_scroll = false;
    }

    /// 向下滚动
    pub fn scroll_down(&mut self) {
        self.offset += 1;
        self.auto_scroll = false;
    }

    /// 更新自动滚动状态
    pub fn update_auto_scroll(&mut self, content_lines: usize, visible_lines: usize) {
        if self.auto_scroll {
            if content_lines > visible_lines {
                self.offset = content_lines - visible_lines;
            } else {
                self.offset = 0;
            }
        } else {
            if content_lines > visible_lines {
                let max_scroll = content_lines - visible_lines;
                if self.offset >= max_scroll {
                    self.offset = max_scroll;
                    self.auto_scroll = true;
                }
            } else {
                self.offset = 0;
                self.auto_scroll = true;
            }
        }
    }

    /// 重置到顶部
    pub fn reset(&mut self) {
        self.offset = 0;
        self.auto_scroll = true;
    }
}

impl Default for ScrollState {
    fn default() -> Self {
        Self::new()
    }
}

/// UI 区域边界信息
#[derive(Debug, Clone, Copy)]
pub struct AreaBounds {
    /// 聊天区域
    pub chat_area: Rect,
    /// 侧边栏区域
    pub sidebar_area: Rect,
    /// 输入区域
    pub input_area: Rect,
}

impl AreaBounds {
    /// 创建新的区域边界
    pub fn new() -> Self {
        Self {
            chat_area: Rect::default(),
            sidebar_area: Rect::default(),
            input_area: Rect::default(),
        }
    }

    /// 检测点所在的区域
    pub fn detect_area(&self, x: u16, y: u16, show_sidebar: bool) -> UiArea {
        // 检查侧边栏
        if show_sidebar {
            if x >= self.sidebar_area.x
                && x < self.sidebar_area.x + self.sidebar_area.width
                && y >= self.sidebar_area.y
                && y < self.sidebar_area.y + self.sidebar_area.height
            {
                return UiArea::Sidebar;
            }
        }

        // 检查聊天区
        if x >= self.chat_area.x
            && x < self.chat_area.x + self.chat_area.width
            && y >= self.chat_area.y
            && y < self.chat_area.y + self.chat_area.height
        {
            return UiArea::Chat;
        }

        // 检查输入区
        if x >= self.input_area.x
            && x < self.input_area.x + self.input_area.width
            && y >= self.input_area.y
            && y < self.input_area.y + self.input_area.height
        {
            return UiArea::Input;
        }

        UiArea::None
    }
}

impl Default for AreaBounds {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scroll_state() {
        let mut state = ScrollState::new();
        assert_eq!(state.offset, 0);
        assert!(state.auto_scroll);

        state.scroll_down();
        assert_eq!(state.offset, 1);
        assert!(!state.auto_scroll);

        state.scroll_up();
        assert_eq!(state.offset, 0);
        assert!(!state.auto_scroll);
    }

    #[test]
    fn test_key_modifiers() {
        let mods = KeyModifiers::empty();
        assert!(!mods.contains_control());

        let mods = KeyModifiers {
            shift: false,
            control: true,
            alt: false,
        };
        assert!(mods.contains_control());
    }

    #[test]
    fn test_area_detection() {
        let bounds = AreaBounds {
            chat_area: Rect::new(0, 3, 50, 10),
            sidebar_area: Rect::new(50, 3, 20, 10),
            input_area: Rect::new(0, 13, 70, 3),
        };

        // 在聊天区内
        assert_eq!(bounds.detect_area(10, 5, true), UiArea::Chat);

        // 在侧边栏内
        assert_eq!(bounds.detect_area(60, 5, true), UiArea::Sidebar);

        // 在输入区内
        assert_eq!(bounds.detect_area(10, 14, true), UiArea::Input);

        // 侧边栏隐藏但聊天区域未扩展时，应视为区域外
        assert_eq!(bounds.detect_area(60, 5, false), UiArea::None);
    }
}
