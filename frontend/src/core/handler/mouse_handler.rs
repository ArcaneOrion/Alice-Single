//! # 鼠标事件处理器
//!
//! 处理鼠标输入事件，包括滚动、点击和拖拽。
//! 包含碰撞检测逻辑，用于确定鼠标事件发生的 UI 区域。

use crossterm::event::{MouseEvent as CrosstermMouseEvent, MouseEventKind as CrosstermMouseEventKind};
use ratatui::layout::Rect;

use super::event::types::{MouseEvent, MouseEventKind, MouseButton, UiArea};

/// 鼠标事件处理结果
#[derive(Debug, Clone, PartialEq)]
pub enum MouseAction {
    /// 无操作
    None,
    /// 聊天区向上滚动
    ChatScrollUp,
    /// 聊天区向下滚动
    ChatScrollDown,
    /// 侧边栏向上滚动
    SidebarScrollUp,
    /// 侧边栏向下滚动
    SidebarScrollDown,
    /// 点击事件
    Click { area: UiArea, x: u16, y: u16 },
    /// 拖拽事件
    Drag { area: UiArea, from_x: u16, from_y: u16, to_x: u16, to_y: u16 },
}

/// 鼠标事件处理器
///
/// 负责检测鼠标事件发生的 UI 区域，并将原始鼠标事件转换为应用级别的操作指令。
/// 保持与原 main.rs 中鼠标处理逻辑的一致性。
pub struct MouseHandler {
    /// 聊天区域边界
    chat_area: Rect,
    /// 侧边栏区域边界
    sidebar_area: Rect,
    /// 输入区域边界
    input_area: Rect,
    /// 是否显示侧边栏
    show_thinking: bool,
}

impl MouseHandler {
    /// 创建新的鼠标处理器
    pub fn new() -> Self {
        Self {
            chat_area: Rect::default(),
            sidebar_area: Rect::default(),
            input_area: Rect::default(),
            show_thinking: false,
        }
    }

    /// 更新 UI 区域边界
    pub fn update_areas(&mut self, chat_area: Rect, sidebar_area: Rect, input_area: Rect) {
        self.chat_area = chat_area;
        self.sidebar_area = sidebar_area;
        self.input_area = input_area;
    }

    /// 设置是否显示侧边栏
    pub fn set_show_thinking(&mut self, show: bool) {
        self.show_thinking = show;
    }

    /// 处理 crossterm 鼠标事件
    pub fn handle_crossterm_event(&self, event: CrosstermMouseEvent) -> MouseAction {
        let (x, y) = (event.column, event.row);

        // 检测鼠标位置所在的区域
        let area = self.detect_area(x, y);

        match event.kind {
            // 滚轮向上
            CrosstermMouseEventKind::ScrollUp => match area {
                UiArea::Sidebar => MouseAction::SidebarScrollUp,
                UiArea::Chat => MouseAction::ChatScrollUp,
                _ => MouseAction::None,
            },

            // 滚轮向下
            CrosstermMouseEventKind::ScrollDown => match area {
                UiArea::Sidebar => MouseAction::SidebarScrollDown,
                UiArea::Chat => MouseAction::ChatScrollDown,
                _ => MouseAction::None,
            },

            // 点击
            CrosstermMouseEventKind::Down(_) => MouseAction::Click { area, x, y },

            _ => MouseAction::None,
        }
    }

    /// 处理内部鼠标事件
    pub fn handle(&self, event: &MouseEvent) -> MouseAction {
        let area = self.detect_area(event.column, event.row);

        match event.kind {
            MouseEventKind::ScrollUp => match area {
                UiArea::Sidebar => MouseAction::SidebarScrollUp,
                UiArea::Chat => MouseAction::ChatScrollUp,
                _ => MouseAction::None,
            },

            MouseEventKind::ScrollDown => match area {
                UiArea::Sidebar => MouseAction::SidebarScrollDown,
                UiArea::Chat => MouseAction::ChatScrollDown,
                _ => MouseAction::None,
            },

            MouseEventKind::Down(_) => MouseAction::Click {
                area,
                x: event.column,
                y: event.row,
            },

            _ => MouseAction::None,
        }
    }

    /// 检测坐标所在的 UI 区域
    ///
    /// 这是核心的碰撞检测逻辑，从原 main.rs 提取：
    /// - 首先检查侧边栏（如果显示）
    /// - 然后检查聊天区
    /// - 最后检查输入区
    pub fn detect_area(&self, x: u16, y: u16) -> UiArea {
        // 检查侧边栏
        if self.show_thinking {
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

    /// 检查点是否在指定矩形区域内
    pub fn is_point_in_rect(x: u16, y: u16, rect: Rect) -> bool {
        x >= rect.x && x < rect.x + rect.width && y >= rect.y && y < rect.y + rect.height
    }

    /// 检查点是否在聊天区内
    pub fn is_in_chat_area(&self, x: u16, y: u16) -> bool {
        Self::is_point_in_rect(x, y, self.chat_area)
    }

    /// 检查点是否在侧边栏内
    pub fn is_in_sidebar_area(&self, x: u16, y: u16) -> bool {
        self.show_thinking && Self::is_point_in_rect(x, y, self.sidebar_area)
    }

    /// 检查点是否在输入区内
    pub fn is_in_input_area(&self, x: u16, y: u16) -> bool {
        Self::is_point_in_rect(x, y, self.input_area)
    }

    /// 获取聊天区域边界
    pub fn chat_area(&self) -> Rect {
        self.chat_area
    }

    /// 获取侧边栏区域边界
    pub fn sidebar_area(&self) -> Rect {
        self.sidebar_area
    }

    /// 获取输入区域边界
    pub fn input_area(&self) -> Rect {
        self.input_area
    }
}

impl Default for MouseHandler {
    fn default() -> Self {
        Self::new()
    }
}

/// 从 crossterm MouseEventKind 转换为内部 MouseEventKind
pub fn convert_mouse_kind(kind: CrosstermMouseEventKind) -> MouseEventKind {
    match kind {
        CrosstermMouseEventKind::ScrollUp => MouseEventKind::ScrollUp,
        CrosstermMouseEventKind::ScrollDown => MouseEventKind::ScrollDown,
        CrosstermMouseEventKind::Down(btn) => {
            MouseEventKind::Down(convert_mouse_button(btn))
        }
        CrosstermMouseEventKind::Up(btn) => MouseEventKind::Up(convert_mouse_button(btn)),
        CrosstermMouseEventKind::Drag(btn) => {
            MouseEventKind::Drag(convert_mouse_button(btn))
        }
        CrosstermMouseEventKind::Moved => MouseEventKind::Moved,
        _ => MouseEventKind::Moved,
    }
}

/// 从 crossterm MouseButton 转换为内部 MouseButton
fn convert_mouse_button(btn: crossterm::event::MouseButton) -> MouseButton {
    match btn {
        crossterm::event::MouseButton::Left => MouseButton::Left,
        crossterm::event::MouseButton::Right => MouseButton::Right,
        crossterm::event::MouseButton::Middle => MouseButton::Middle,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_handler() -> MouseHandler {
        let mut handler = MouseHandler::new();
        handler.update_areas(
            Rect::new(0, 3, 50, 10),
            Rect::new(50, 3, 20, 10),
            Rect::new(0, 13, 70, 3),
        );
        handler.set_show_thinking(true);
        handler
    }

    #[test]
    fn test_detect_area_chat() {
        let handler = create_handler();
        assert_eq!(handler.detect_area(10, 5), UiArea::Chat);
        assert_eq!(handler.detect_area(0, 3), UiArea::Chat);
        assert_eq!(handler.detect_area(49, 12), UiArea::Chat);
    }

    #[test]
    fn test_detect_area_sidebar() {
        let handler = create_handler();
        assert_eq!(handler.detect_area(60, 5), UiArea::Sidebar);
        assert_eq!(handler.detect_area(50, 3), UiArea::Sidebar);
        assert_eq!(handler.detect_area(69, 12), UiArea::Sidebar);
    }

    #[test]
    fn test_detect_area_input() {
        let handler = create_handler();
        assert_eq!(handler.detect_area(10, 14), UiArea::Input);
        assert_eq!(handler.detect_area(0, 13), UiArea::Input);
        assert_eq!(handler.detect_area(69, 15), UiArea::Input);
    }

    #[test]
    fn test_detect_area_none() {
        let handler = create_handler();
        // 越界坐标
        assert_eq!(handler.detect_area(100, 100), UiArea::None);
    }

    #[test]
    fn test_detect_area_without_sidebar() {
        let mut handler = create_handler();
        handler.set_show_thinking(false);

        // 侧边栏隐藏时，原侧边栏位置应为 None（因为不在聊天区边界内）
        assert_eq!(handler.detect_area(60, 5), UiArea::None);
    }

    #[test]
    fn test_scroll_in_chat() {
        let handler = create_handler();

        let event = CrosstermMouseEvent {
            kind: CrosstermMouseEventKind::ScrollUp,
            column: 10,
            row: 5,
            modifiers: crossterm::event::KeyModifiers::empty(),
        };
        assert_eq!(
            handler.handle_crossterm_event(event),
            MouseAction::ChatScrollUp
        );

        let event = CrosstermMouseEvent {
            kind: CrosstermMouseEventKind::ScrollDown,
            column: 10,
            row: 5,
            modifiers: crossterm::event::KeyModifiers::empty(),
        };
        assert_eq!(
            handler.handle_crossterm_event(event),
            MouseAction::ChatScrollDown
        );
    }

    #[test]
    fn test_scroll_in_sidebar() {
        let handler = create_handler();

        let event = CrosstermMouseEvent {
            kind: CrosstermMouseEventKind::ScrollUp,
            column: 60,
            row: 5,
            modifiers: crossterm::event::KeyModifiers::empty(),
        };
        assert_eq!(
            handler.handle_crossterm_event(event),
            MouseAction::SidebarScrollUp
        );

        let event = CrosstermMouseEvent {
            kind: CrosstermMouseEventKind::ScrollDown,
            column: 60,
            row: 5,
            modifiers: crossterm::event::KeyModifiers::empty(),
        };
        assert_eq!(
            handler.handle_crossterm_event(event),
            MouseAction::SidebarScrollDown
        );
    }

    #[test]
    fn test_is_point_in_rect() {
        let rect = Rect::new(10, 20, 30, 40);

        // 边界内
        assert!(MouseHandler::is_point_in_rect(10, 20, rect));
        assert!(MouseHandler::is_point_in_rect(25, 30, rect));
        assert!(MouseHandler::is_point_in_rect(39, 59, rect));

        // 边界外
        assert!(!MouseHandler::is_point_in_rect(9, 20, rect));
        assert!(!MouseHandler::is_point_in_rect(10, 19, rect));
        assert!(!MouseHandler::is_point_in_rect(40, 20, rect));
        assert!(!MouseHandler::is_point_in_rect(10, 60, rect));
    }

    #[test]
    fn test_convert_mouse_kind() {
        assert_eq!(
            convert_mouse_kind(CrosstermMouseEventKind::ScrollUp),
            MouseEventKind::ScrollUp
        );
        assert_eq!(
            convert_mouse_kind(CrosstermMouseEventKind::ScrollDown),
            MouseEventKind::ScrollDown
        );
        assert_eq!(
            convert_mouse_kind(CrosstermMouseEventKind::Down(
                crossterm::event::MouseButton::Left
            )),
            MouseEventKind::Down(MouseButton::Left)
        );
    }
}
