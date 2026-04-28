//! # 侧边栏组件
//!
//! 显示 Alice 的思考过程，支持自动滚动和选区高亮。

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

/// 侧边栏配置
pub struct SidebarConfig {
    pub scroll_offset: usize,
    pub auto_scroll: bool,
    pub spinner_index: usize,
    pub is_thinking: bool,
}

impl Default for SidebarConfig {
    fn default() -> Self {
        Self {
            scroll_offset: 0,
            auto_scroll: true,
            spinner_index: 0,
            is_thinking: false,
        }
    }
}

const SPINNER: &[&str] = &["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

fn get_spinner(index: usize) -> &'static str {
    SPINNER[index % SPINNER.len()]
}

/// 渲染思考侧边栏
pub fn render_sidebar(
    f: &mut Frame,
    area: Rect,
    thinking_content: &str,
    config: &mut SidebarConfig,
    selection: &SelectionState,
    content_lines_out: &mut Vec<String>,
) {
    content_lines_out.clear();

    let display_content = if thinking_content.is_empty() {
        "暂无思考过程..."
    } else {
        thinking_content
    };

    let width = area.width.saturating_sub(2) as usize;

    let sidebar_title = if config.is_thinking {
        format!(" 💭 {} ", get_spinner(config.spinner_index))
    } else {
        " 💭 ".to_string()
    };

    let lines = format_text_to_lines(display_content, width);
    let total_lines = lines.len();
    let height = area.height.saturating_sub(2) as usize;

    update_scroll_offset(config, total_lines, height);

    let mut items: Vec<ListItem> = Vec::new();
    for (idx, line_text) in lines.iter().enumerate() {
        let styled_line = build_selectable_sidebar_line(line_text, idx, selection);
        items.push(ListItem::new(styled_line));
        content_lines_out.push(line_text.clone());
    }

    let mut list_state = ListState::default();
    *list_state.offset_mut() = config.scroll_offset;

    let list = List::new(items).block(Block::default().title(sidebar_title).borders(Borders::ALL));

    f.render_stateful_widget(list, area, &mut list_state);
}

fn update_scroll_offset(config: &mut SidebarConfig, total_lines: usize, height: usize) {
    if config.auto_scroll {
        if total_lines > height {
            config.scroll_offset = total_lines - height;
        } else {
            config.scroll_offset = 0;
        }
    } else {
        if total_lines > height {
            let max_scroll = total_lines - height;
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

const SELECTED_STYLE: Style = Style::new()
    .bg(Color::DarkGray)
    .add_modifier(Modifier::REVERSED);

const NORMAL_STYLE: Style = Style::new().fg(Color::Gray).add_modifier(Modifier::ITALIC);

/// 构建带选择高亮的侧边栏文本行。
fn build_selectable_sidebar_line(
    line_text: &str,
    line_idx: usize,
    selection: &SelectionState,
) -> Line<'static> {
    if !selection.has_selection() || selection.area != UiArea::Sidebar {
        return Line::from(line_text.to_string()).style(NORMAL_STYLE);
    }

    let (top, bottom) = selection.selection_line_range();
    if line_idx < top || line_idx > bottom {
        return Line::from(line_text.to_string()).style(NORMAL_STYLE);
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
        return Line::from(line_text.to_string()).style(NORMAL_STYLE);
    }

    let mut spans: Vec<Span> = Vec::new();
    if sel_start > 0 {
        spans.push(Span::styled(
            line_text[..sel_start].to_string(),
            NORMAL_STYLE,
        ));
    }
    spans.push(Span::styled(
        line_text[sel_start..sel_end].to_string(),
        SELECTED_STYLE,
    ));
    if sel_end < line_text.len() {
        spans.push(Span::styled(line_text[sel_end..].to_string(), NORMAL_STYLE));
    }

    Line::from(spans)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_spinner() {
        assert_eq!(get_spinner(0), "⠋");
        assert_eq!(get_spinner(10), "⠋");
    }

    #[test]
    fn test_scroll_offset_update() {
        let mut config = SidebarConfig::default();

        update_scroll_offset(&mut config, 5, 10);
        assert_eq!(config.scroll_offset, 0);
        assert!(config.auto_scroll);

        update_scroll_offset(&mut config, 20, 10);
        assert_eq!(config.scroll_offset, 10);
        assert!(config.auto_scroll);

        config.auto_scroll = false;
        config.scroll_offset = 5;
        update_scroll_offset(&mut config, 20, 10);
        assert_eq!(config.scroll_offset, 5);
        assert!(!config.auto_scroll);

        config.scroll_offset = 15;
        update_scroll_offset(&mut config, 20, 10);
        assert_eq!(config.scroll_offset, 10);
        assert!(config.auto_scroll);
    }
}
