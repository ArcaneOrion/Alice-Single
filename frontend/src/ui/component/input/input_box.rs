//! # 输入框组件
//!
//! 处理用户输入的显示和光标定位。

use ratatui::{
    Frame,
    layout::Rect,
    style::{Color, Style},
    widgets::{Block, Borders, Paragraph},
};

use unicode_width::UnicodeWidthStr;

/// 输入框配置
pub struct InputBoxConfig {
    /// 是否允许输入（Idle 状态）
    pub enabled: bool,
    /// 输入提示文本
    pub title_enabled: String,
    /// 禁用状态提示文本
    pub title_disabled: String,
}

impl Default for InputBoxConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            title_enabled: " 输入消息 (Enter 发送, Ctrl+C 退出) ".to_string(),
            title_disabled: " 请等待 Alice 回复... ".to_string(),
        }
    }
}

/// 渲染输入框
///
/// # 参数
/// * `f` - ratatui Frame
/// * `area` - 渲染区域
/// * `input` - 用户输入内容
/// * `config` - 输入框配置
pub fn render_input_box(f: &mut Frame, area: Rect, input: &str, config: &InputBoxConfig) {
    let title = if config.enabled {
        &config.title_enabled
    } else {
        &config.title_disabled
    };

    let color = if config.enabled {
        Color::Yellow
    } else {
        Color::DarkGray
    };

    let input_paragraph = Paragraph::new(input)
        .style(Style::default().fg(color))
        .block(Block::default().borders(Borders::ALL).title(title.as_str()));

    f.render_widget(input_paragraph, area);

    // 仅在启用状态下设置光标位置
    if config.enabled {
        let input_width = UnicodeWidthStr::width(input);
        f.set_cursor_position((area.x + input_width as u16 + 1, area.y + 1));
    }
}

/// 获取输入框建议高度
pub const INPUT_HEIGHT: u16 = 3;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_input_box_config_default() {
        let config = InputBoxConfig::default();
        assert!(config.enabled);
        assert!(config.title_enabled.contains("Enter 发送"));
    }

    #[test]
    fn test_input_height_constant() {
        assert_eq!(INPUT_HEIGHT, 3);
    }
}
