//! # Header 组件
//!
//! 显示应用标题、运行状态、Token 统计等信息的头部区域。

use ratatui::{
    Frame,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
};

/// Agent 运行状态
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum AgentStatus {
    Starting,
    Idle,
    Thinking,
    Responding,
    ExecutingTool,
}

impl AgentStatus {
    /// 获取状态对应的样式
    pub fn style(&self) -> Style {
        match self {
            AgentStatus::Starting => Style::default().fg(Color::Blue),
            AgentStatus::Idle => Style::default().fg(Color::Green),
            AgentStatus::Thinking => Style::default()
                .fg(Color::Yellow)
                .add_modifier(Modifier::ITALIC),
            AgentStatus::Responding => Style::default().fg(Color::Magenta),
            AgentStatus::ExecutingTool => Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        }
    }

    /// 获取状态显示文本
    pub fn text(&self, spinner: &str) -> String {
        match self {
            AgentStatus::Starting => format!(" {} 正在启动后端...", spinner),
            AgentStatus::Idle => " ⚡ 就绪 ".to_string(),
            AgentStatus::Thinking => format!(" {} Alice 正在思考...", spinner),
            AgentStatus::Responding => format!(" {} Alice 正在回复...", spinner),
            AgentStatus::ExecutingTool => format!(" {} 正在执行工具任务...", spinner),
        }
    }
}

/// Header 渲染配置
pub struct HeaderConfig {
    /// 当前运行状态
    pub status: AgentStatus,
    /// 旋转器索引（用于动画）
    pub spinner_index: usize,
    /// 是否显示思考侧边栏
    pub show_thinking: bool,
    /// 总 Token 数量
    pub total_tokens: usize,
    /// Prompt Token 数量
    pub prompt_tokens: usize,
    /// Completion Token 数量
    pub completion_tokens: usize,
}

impl Default for HeaderConfig {
    fn default() -> Self {
        Self {
            status: AgentStatus::Starting,
            spinner_index: 0,
            show_thinking: false,
            total_tokens: 0,
            prompt_tokens: 0,
            completion_tokens: 0,
        }
    }
}

/// 获取旋转器字符
const SPINNER: &[&str] = &["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

fn get_spinner(index: usize) -> &'static str {
    SPINNER[index % SPINNER.len()]
}

/// 渲染 Header 组件
///
/// # 参数
/// * `f` - ratatui Frame
/// * `area` - 渲染区域
/// * `config` - Header 配置
pub fn render_header(f: &mut Frame, area: ratatui::layout::Rect, config: &HeaderConfig) {
    let status_style = config.status.style();
    let status_text = config.status.text(get_spinner(config.spinner_index));

    let thinking_hint = if config.show_thinking {
        "显示思考过程 (Ctrl+O 隐藏)"
    } else {
        "隐藏思考过程 (Ctrl+O 显示)"
    };

    let token_info = if config.total_tokens > 0 {
        format!(
            " | Tokens: {} (P:{} C:{})",
            config.total_tokens, config.prompt_tokens, config.completion_tokens
        )
    } else {
        String::new()
    };

    let header_line = Line::from(vec![
        Span::styled(
            " ALICE ASSISTANT ",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" | 状态:"),
        Span::styled(status_text, status_style),
        Span::raw(" | "),
        Span::raw(thinking_hint),
        Span::styled(token_info, Style::default().fg(Color::White)),
    ]);

    let header = Paragraph::new(header_line).block(Block::default().borders(Borders::ALL));
    f.render_widget(header, area);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_agent_status_style() {
        assert_eq!(AgentStatus::Idle.style().fg, Some(Color::Green));
        assert_eq!(AgentStatus::Thinking.style().fg, Some(Color::Yellow));
    }

    #[test]
    fn test_get_spinner() {
        assert_eq!(get_spinner(0), "⠋");
        assert_eq!(get_spinner(10), "⠋"); // 循环
    }
}
