//! # 聊天视图组件
//!
//! 负责渲染对话历史消息，包括自动滚动和文本格式化。

use ratatui::{
    Frame,
    layout::Rect,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, ListState},
};

use crate::app::selection::SelectionState;
use crate::core::event::types::UiArea;
use crate::ui::util::text::format_text_to_lines;

/// 消息作者
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Author {
    User,
    Assistant,
}

impl Author {
    /// 获取作者显示名称
    pub fn display_name(&self) -> &str {
        match self {
            Author::User => " 你: ",
            Author::Assistant => " Alice: ",
        }
    }

    /// 获取作者颜色
    pub fn color(&self) -> Color {
        match self {
            Author::User => Color::Blue,
            Author::Assistant => Color::Magenta,
        }
    }
}

/// 单条消息结构
#[derive(Debug, Clone)]
pub struct Message {
    pub author: Author,
    pub thinking: String,
    pub content: String,
    pub is_complete: bool,
}

impl Message {
    pub fn new(author: Author, content: String) -> Self {
        Self {
            author,
            thinking: String::new(),
            content,
            is_complete: true,
        }
    }

    pub fn new_assistant_placeholder() -> Self {
        Self {
            author: Author::Assistant,
            thinking: String::new(),
            content: String::new(),
            is_complete: false,
        }
    }
}

/// 聊天视图配置
pub struct ChatViewConfig {
    pub scroll_offset: usize,
    pub auto_scroll: bool,
    pub spinner_index: usize,
}

impl Default for ChatViewConfig {
    fn default() -> Self {
        Self {
            scroll_offset: 0,
            auto_scroll: true,
            spinner_index: 0,
        }
    }
}

const SPINNER: &[&str] = &["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

fn get_spinner(index: usize) -> &'static str {
    SPINNER[index % SPINNER.len()]
}

#[derive(Default)]
pub struct ChatViewState {
    pub list_state: ListState,
}

/// 选中文本的高亮样式
const SELECTED_STYLE: Style = Style::new()
    .bg(Color::DarkGray)
    .add_modifier(Modifier::REVERSED);

/// 构建带选择高亮的文本行。
/// 对部分选中的行，用 Span 级别区分选中/未选中的字符。
/// `expected_area` 用于区分聊天区和侧边栏的选择。
fn build_selectable_line(
    line_text: &str,
    line_idx: usize,
    selection: &SelectionState,
    expected_area: crate::core::event::types::UiArea,
    normal_style: Style,
) -> Line<'static> {
    if !selection.has_selection() || selection.area != expected_area {
        return Line::from(line_text.to_string()).style(normal_style);
    }

    let (top, bottom) = selection.selection_line_range();
    if line_idx < top || line_idx > bottom {
        return Line::from(line_text.to_string()).style(normal_style);
    }

    let (left_col, right_col) = selection.selection_col_range();
    let is_first = line_idx == top;
    let is_last = line_idx == bottom;

    let sel_start = if is_first {
        crate::app::selection::display_col_to_char_start(line_text, left_col)
    } else {
        0
    };
    let sel_end = if is_last {
        crate::app::selection::display_col_to_char_end(line_text, right_col)
    } else {
        line_text.len()
    };

    if sel_start >= sel_end || sel_start >= line_text.len() {
        return Line::from(line_text.to_string()).style(normal_style);
    }

    let mut spans: Vec<Span> = Vec::new();
    if sel_start > 0 {
        spans.push(Span::styled(
            line_text[..sel_start].to_string(),
            normal_style,
        ));
    }
    spans.push(Span::styled(
        line_text[sel_start..sel_end].to_string(),
        SELECTED_STYLE,
    ));
    if sel_end < line_text.len() {
        spans.push(Span::styled(line_text[sel_end..].to_string(), normal_style));
    }

    Line::from(spans)
}

/// 渲染聊天视图
pub fn render_chat_view(
    f: &mut Frame,
    area: Rect,
    messages: &[Message],
    config: &mut ChatViewConfig,
    state: &mut ChatViewState,
    selection: &SelectionState,
    content_lines_out: &mut Vec<String>,
) {
    content_lines_out.clear();
    let mut message_items = Vec::new();
    let width = area.width.saturating_sub(4) as usize;
    let mut line_idx: usize = 0;

    for msg in messages {
        let name = msg.author.display_name();
        let color = msg.author.color();

        // 作者行
        let author_style = Style::default().fg(color).add_modifier(Modifier::BOLD);
        let author_line =
            build_selectable_line(name, line_idx, selection, UiArea::Chat, author_style);
        message_items.push(ListItem::new(author_line));
        content_lines_out.push(name.to_string());
        line_idx += 1;

        let content_text =
            if msg.content.is_empty() && !msg.is_complete && msg.author == Author::Assistant {
                format!("{} 正在处理中...", get_spinner(config.spinner_index))
            } else {
                msg.content.clone()
            };

        let content_lines = format_text_to_lines(&content_text, width);
        for line in content_lines {
            let normal_style = Style::default();
            let display_line =
                build_selectable_line(&line, line_idx, selection, UiArea::Chat, normal_style);
            message_items.push(ListItem::new(display_line));
            content_lines_out.push(line);
            line_idx += 1;
        }

        // 空行分隔
        let empty_line =
            build_selectable_line("", line_idx, selection, UiArea::Chat, Style::default());
        message_items.push(ListItem::new(empty_line));
        content_lines_out.push(String::new());
        line_idx += 1;
    }

    let total_lines = message_items.len();
    let list_height = area.height.saturating_sub(2) as usize;
    update_scroll_offset(config, total_lines, list_height);

    let history =
        List::new(message_items).block(Block::default().title(" 对话历史 ").borders(Borders::ALL));

    *state.list_state.offset_mut() = config.scroll_offset;
    f.render_stateful_widget(history, area, &mut state.list_state);
}

fn update_scroll_offset(config: &mut ChatViewConfig, total_lines: usize, list_height: usize) {
    if config.auto_scroll {
        if total_lines > list_height {
            config.scroll_offset = total_lines - list_height;
        } else {
            config.scroll_offset = 0;
        }
    } else {
        if total_lines > list_height {
            let max_scroll = total_lines - list_height;
            if config.scroll_offset > max_scroll {
                config.scroll_offset = max_scroll;
                config.auto_scroll = true;
            }
        } else {
            config.scroll_offset = 0;
            config.auto_scroll = true;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_author_display() {
        assert_eq!(Author::User.display_name(), " 你: ");
        assert_eq!(Author::Assistant.display_name(), " Alice: ");
    }

    #[test]
    fn test_message_creation() {
        let msg = Message::new(Author::User, "测试消息".to_string());
        assert_eq!(msg.author, Author::User);
        assert_eq!(msg.content, "测试消息");
        assert!(msg.is_complete);
    }

    #[test]
    fn test_scroll_offset_update() {
        let mut config = ChatViewConfig::default();

        update_scroll_offset(&mut config, 5, 10);
        assert_eq!(config.scroll_offset, 0);

        update_scroll_offset(&mut config, 20, 10);
        assert_eq!(config.scroll_offset, 10);
    }
}
