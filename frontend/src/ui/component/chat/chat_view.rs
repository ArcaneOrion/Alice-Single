//! # 聊天视图组件
//!
//! 负责渲染对话历史消息，包括自动滚动和文本格式化。

use ratatui::{
    layout::Rect,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, ListState},
    Frame,
};

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
    /// 消息作者
    pub author: Author,
    /// 思考过程内容
    pub thinking: String,
    /// 消息正文
    pub content: String,
    /// 是否已完成
    pub is_complete: bool,
}

impl Message {
    /// 创建新消息
    pub fn new(author: Author, content: String) -> Self {
        Self {
            author,
            thinking: String::new(),
            content,
            is_complete: true,
        }
    }

    /// 创建空的助手消息（用于流式更新）
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
    /// 滚动偏移量
    pub scroll_offset: usize,
    /// 是否自动滚动
    pub auto_scroll: bool,
    /// 旋转器索引（用于"正在处理中"动画）
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

/// 获取旋转器字符
const SPINNER: &[&str] = &["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

fn get_spinner(index: usize) -> &'static str {
    SPINNER[index % SPINNER.len()]
}

/// 聊天视图状态
pub struct ChatViewState {
    /// List 状态
    pub list_state: ListState,
}

impl Default for ChatViewState {
    fn default() -> Self {
        Self {
            list_state: ListState::default(),
        }
    }
}

/// 渲染聊天视图
///
/// # 参数
/// * `f` - ratatui Frame
/// * `area` - 渲染区域
/// * `messages` - 消息列表
/// * `config` - 视图配置（可变，用于更新滚动状态）
/// * `state` - List 状态（可变，用于渲染）
pub fn render_chat_view(
    f: &mut Frame,
    area: Rect,
    messages: &[Message],
    config: &mut ChatViewConfig,
    state: &mut ChatViewState,
) {
    let mut message_items = Vec::new();
    let width = area.width.saturating_sub(4) as usize;

    for msg in messages {
        // 1. 渲染作者行
        let name = msg.author.display_name();
        let color = msg.author.color();

        message_items.push(ListItem::new(Line::from(vec![Span::styled(
            name,
            Style::default().fg(color).add_modifier(Modifier::BOLD),
        )])));

        // 2. 渲染正文内容
        // 思考过程已移至侧边栏，此处不再渲染
        let content_text = if msg.content.is_empty() && !msg.is_complete && msg.author == Author::Assistant
        {
            format!("{} 正在处理中...", get_spinner(config.spinner_index))
        } else {
            msg.content.clone()
        };

        let content_lines = format_text_to_lines(&content_text, width);
        for line in content_lines {
            message_items.push(ListItem::new(Line::from(line)));
        }

        // 3. 添加分隔空行
        message_items.push(ListItem::new(""));
    }

    // 计算滚动位置
    let total_lines = message_items.len();
    let list_height = area.height.saturating_sub(2) as usize;

    update_scroll_offset(config, total_lines, list_height);

    // 渲染消息列表
    let history = List::new(message_items)
        .block(Block::default().title(" 对话历史 ").borders(Borders::ALL));

    *state.list_state.offset_mut() = config.scroll_offset;
    f.render_stateful_widget(history, area, &mut state.list_state);
}

/// 更新滚动偏移量
///
/// 实现自动置底逻辑：
/// - 如果启用自动滚动，始终保持在最底部
/// - 如果用户手动滚动，则保持当前位置
/// - 当滚动超出范围时，恢复自动滚动
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

        // 测试自动滚动 - 内容少于高度
        update_scroll_offset(&mut config, 5, 10);
        assert_eq!(config.scroll_offset, 0);

        // 测试自动滚动 - 内容多于高度
        update_scroll_offset(&mut config, 20, 10);
        assert_eq!(config.scroll_offset, 10);
    }
}
