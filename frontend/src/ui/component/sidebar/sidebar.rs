//! # 侧边栏组件
//!
//! 显示 Alice 的思考过程（thinking 内容），支持自动滚动。

use ratatui::{
    layout::Rect,
    style::{Color, Modifier, Style},
    widgets::{Block, Borders, Paragraph, Wrap},
    Frame,
};

use crate::ui::util::text::format_text_to_lines;

/// 侧边栏配置
pub struct SidebarConfig {
    /// 滚动偏移量
    pub scroll_offset: usize,
    /// 是否自动滚动
    pub auto_scroll: bool,
    /// 旋转器索引（用于动画）
    pub spinner_index: usize,
    /// 当前 Agent 状态
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

/// 获取旋转器字符
const SPINNER: &[&str] = &["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

fn get_spinner(index: usize) -> &'static str {
    SPINNER[index % SPINNER.len()]
}

/// 渲染思考侧边栏
///
/// # 参数
/// * `f` - ratatui Frame
/// * `area` - 渲染区域
/// * `thinking_content` - 思考过程内容
/// * `config` - 侧边栏配置（可变，用于更新滚动状态）
pub fn render_sidebar(
    f: &mut Frame,
    area: Rect,
    thinking_content: &str,
    config: &mut SidebarConfig,
) {
    // 如果内容为空，显示占位文本
    let display_content = if thinking_content.is_empty() {
        "暂无思考过程..."
    } else {
        thinking_content
    };

    let width = area.width.saturating_sub(2) as usize;

    // 构建标题（根据状态显示旋转器）
    let sidebar_title = if config.is_thinking {
        format!(" 💭 {} ", get_spinner(config.spinner_index))
    } else {
        " 💭 ".to_string()
    };

    let style = Style::default().fg(Color::Gray).add_modifier(Modifier::ITALIC);

    // 计算内容行数以实现自动滚动
    let lines = format_text_to_lines(display_content, width);
    let total_lines = lines.len();
    let height = area.height.saturating_sub(2) as usize;

    // 更新滚动偏移量
    update_scroll_offset(config, total_lines, height);

    // 渲染侧边栏
    let thinking_paragraph = Paragraph::new(display_content)
        .style(style)
        .wrap(Wrap { trim: true })
        .scroll((config.scroll_offset as u16, 0))
        .block(Block::default().title(sidebar_title).borders(Borders::ALL));

    f.render_widget(thinking_paragraph, area);
}

/// 更新滚动偏移量
///
/// 实现与聊天视图相同的自动置底逻辑
fn update_scroll_offset(config: &mut SidebarConfig, total_lines: usize, height: usize) {
    if config.auto_scroll {
        if total_lines > height {
            config.scroll_offset = total_lines - height;
        } else {
            config.scroll_offset = 0;
        }
    } else {
        // 限制手动滚动范围
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_spinner() {
        assert_eq!(get_spinner(0), "⠋");
        assert_eq!(get_spinner(10), "⠋"); // 循环
    }

    #[test]
    fn test_scroll_offset_update() {
        let mut config = SidebarConfig::default();

        // 测试自动滚动 - 内容少于高度
        update_scroll_offset(&mut config, 5, 10);
        assert_eq!(config.scroll_offset, 0);
        assert!(config.auto_scroll);

        // 测试自动滚动 - 内容多于高度
        update_scroll_offset(&mut config, 20, 10);
        assert_eq!(config.scroll_offset, 10);
        assert!(config.auto_scroll);

        // 测试手动滚动后恢复
        config.auto_scroll = false;
        config.scroll_offset = 5;
        update_scroll_offset(&mut config, 20, 10);
        assert_eq!(config.scroll_offset, 5);
        assert!(!config.auto_scroll);

        // 超出范围时恢复自动滚动
        config.scroll_offset = 15;
        update_scroll_offset(&mut config, 20, 10);
        assert_eq!(config.scroll_offset, 10);
        assert!(config.auto_scroll);
    }
}
