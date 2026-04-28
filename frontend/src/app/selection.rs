//! 文字选择状态管理模块。
//!
//! 使用内容坐标（非屏幕坐标）追踪选择状态，避免滚动偏移带来的映射问题。
//! 坐标系统使用 Unicode 显示宽度（display column），提取文本时映射回字符索引。

use ratatui::layout::Rect;
use unicode_width::UnicodeWidthChar;

use crate::core::event::types::UiArea;

/// 文字选择状态（使用内容相对坐标）
#[derive(Debug, Clone)]
pub struct SelectionState {
    /// 是否正在拖拽选择中
    pub active: bool,
    /// 选择所在的 UI 区域
    pub area: UiArea,
    /// 选择起始行（内容行索引）
    pub start_line: usize,
    /// 选择起始列（显示列，即 Unicode 宽度列）
    pub start_col: usize,
    /// 选择结束行（内容行索引）
    pub end_line: usize,
    /// 选择结束列（显示列）
    pub end_col: usize,
    /// 已选中的文本（在 extract_text 后填充）
    pub selected_text: String,
}

impl Default for SelectionState {
    fn default() -> Self {
        Self {
            active: false,
            area: UiArea::None,
            start_line: 0,
            start_col: 0,
            end_line: 0,
            end_col: 0,
            selected_text: String::new(),
        }
    }
}

impl SelectionState {
    /// 开始新的选择（内容坐标）
    pub fn start(&mut self, area: UiArea, line: usize, col: usize) {
        self.active = true;
        self.area = area;
        self.start_line = line;
        self.start_col = col;
        self.end_line = line;
        self.end_col = col;
        self.selected_text.clear();
    }

    /// 更新选择终点（内容坐标）
    pub fn update(&mut self, line: usize, col: usize) {
        if !self.active {
            return;
        }
        self.end_line = line;
        self.end_col = col;
    }

    /// 结束拖拽选择
    pub fn end(&mut self) {
        self.active = false;
    }

    /// 取消选择
    pub fn clear(&mut self) {
        self.active = false;
        self.selected_text.clear();
        self.area = UiArea::None;
        self.start_line = 0;
        self.start_col = 0;
        self.end_line = 0;
        self.end_col = 0;
    }

    /// 检查是否有一个有效的选择
    pub fn has_selection(&self) -> bool {
        self.area != UiArea::None
            && (self.start_line != self.end_line || self.start_col != self.end_col)
    }

    /// 检查内容行是否在选择范围内
    pub fn is_content_line_selected(&self, content_line: usize) -> bool {
        if !self.has_selection() {
            return false;
        }
        let (top, bottom) = self.selection_line_range();
        content_line >= top && content_line <= bottom
    }

    /// 获取选择范围的标准化行范围
    pub fn selection_line_range(&self) -> (usize, usize) {
        if self.start_line <= self.end_line {
            (self.start_line, self.end_line)
        } else {
            (self.end_line, self.start_line)
        }
    }

    /// 获取选择范围的标准化列范围
    pub fn selection_col_range(&self) -> (usize, usize) {
        if self.start_col <= self.end_col {
            (self.start_col, self.end_col)
        } else {
            (self.end_col, self.start_col)
        }
    }

    /// 从内容行文本中提取选中的文字。
    ///
    /// 选择坐标基于 Unicode 显示列（display column），
    /// 此方法将其映射回字符索引后提取子串。
    /// 左边界取字符起始字节，右边界取字符结束字节（包含最后一个被触碰的字符）。
    pub fn extract_text(&mut self, line_texts: &[String]) {
        let (top, bottom) = self.selection_line_range();

        if top >= line_texts.len() {
            return;
        }
        let end_line = bottom.min(line_texts.len().saturating_sub(1));

        let (left_col, right_col) = self.selection_col_range();

        let mut selected = String::new();

        if top == end_line {
            let line = &line_texts[top];
            let s = display_col_to_char_start(line, left_col);
            let e = display_col_to_char_end(line, right_col);
            if s < e {
                selected.push_str(&line[s..e]);
            }
        } else {
            let line = &line_texts[top];
            let s = display_col_to_char_start(line, left_col);
            if s < line.len() {
                selected.push_str(&line[s..]);
            }
            selected.push('\n');

            for line in line_texts.iter().take(end_line).skip(top + 1) {
                selected.push_str(line);
                selected.push('\n');
            }

            let line = &line_texts[end_line];
            let e = display_col_to_char_end(line, right_col);
            if e > 0 {
                selected.push_str(&line[..e]);
            }
        }

        self.selected_text = selected;
    }

    /// 将选中文本写入剪贴板。
    ///
    /// 优先使用 OSC 52 终端协议（跨平台、无需系统库），
    /// 失败时回退到 arboard。
    pub fn copy_to_clipboard(&self) -> Result<(), String> {
        if self.selected_text.is_empty() {
            return Err("没有选中的文字".to_string());
        }
        if osc52_set(&self.selected_text) {
            return Ok(());
        }
        arboard::Clipboard::new()
            .and_then(|mut c| c.set_text(self.selected_text.clone()))
            .map_err(|e| format!("剪贴板错误: {}", e))
    }

    /// 从剪贴板读取文本。
    ///
    /// 依次尝试 arboard → 外部命令 → OSC 52。
    pub fn paste_from_clipboard() -> Result<String, String> {
        // 1. arboard（Wayland 需 wayland-data-control feature）
        match arboard::Clipboard::new().and_then(|mut c| c.get_text()) {
            Ok(text) if !text.is_empty() => return Ok(text),
            Err(e) => {
                runtime_log("clipboard", "arboard.error", &format!("{}", e));
            }
            _ => {}
        }

        // 2. 外部剪贴板命令
        for cmd in &["wl-paste", "xclip", "xsel"] {
            match clipboard_cmd(cmd) {
                Ok(text) if !text.is_empty() => return Ok(text),
                Err(e) => {
                    runtime_log("clipboard", "cmd.error", &format!("{}", e));
                }
                _ => {}
            }
        }

        // 3. OSC 52 兜底
        osc52_get()
    }
}

/// 调用外部剪贴板命令读取文本
fn clipboard_cmd(cmd: &str) -> Result<String, String> {
    let args: &[&str] = match cmd {
        "wl-paste" => &[],
        "xclip" => &["-selection", "clipboard", "-o"],
        "xsel" => &["--clipboard", "--output"],
        _ => return Err(format!("unknown cmd: {}", cmd)),
    };
    std::process::Command::new(cmd)
        .args(args)
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .map_err(|e| format!("{}: {}", cmd, e))
}

/// 运行时日志辅助（避免循环导入）
fn runtime_log(category: &str, event: &str, detail: &str) {
    crate::util::runtime_log::runtime_log(category, event, detail);
}

// ============================================================================
// OSC 52 终端剪贴板协议
// ============================================================================

/// 通过 OSC 52 转义序列设置系统剪贴板。
/// 返回 true 表示成功写入。
fn osc52_set(text: &str) -> bool {
    use std::io::Write;
    let encoded = base64_encode(text);
    // OSC 52 限制有效载荷长度，超长时分片或截断
    let chunk = if encoded.len() > 768 {
        &encoded[..768]
    } else {
        &encoded
    };
    let seq = format!("\x1b]52;c;{}\x1b\\", chunk);
    let mut stdout = std::io::stdout().lock();
    stdout.write_all(seq.as_bytes()).is_ok() && stdout.flush().is_ok()
}

/// 通过 OSC 52 尝试读取剪贴板。
/// 需要终端支持且响应及时，多数情况下不可用。
fn osc52_get() -> Result<String, String> {
    // OSC 52 读取需要终端在 stdin 响应，且需异步解析。
    // 绝大部分终端对 OSC 52 只写不读，这里作为占位。
    Err("OSC 52 读取不支持".to_string())
}

/// 简单 base64 编码（不引入额外依赖）
fn base64_encode(input: &str) -> String {
    const CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let bytes = input.as_bytes();
    let mut result = String::with_capacity((bytes.len() + 2) / 3 * 4);
    for chunk in bytes.chunks(3) {
        let b0 = chunk[0] as u32;
        let b1 = if chunk.len() > 1 { chunk[1] as u32 } else { 0 };
        let b2 = if chunk.len() > 2 { chunk[2] as u32 } else { 0 };
        let triple = (b0 << 16) | (b1 << 8) | b2;
        result.push(CHARS[((triple >> 18) & 0x3F) as usize] as char);
        result.push(CHARS[((triple >> 12) & 0x3F) as usize] as char);
        if chunk.len() > 1 {
            result.push(CHARS[((triple >> 6) & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
        if chunk.len() > 2 {
            result.push(CHARS[(triple & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
    }
    result
}

/// 将 Unicode 显示列号映射为该位置字符的起始字节偏移。
///
/// 如果 `col` 落在宽字符内部（如中文），回退到该字符的起始字节。
/// 如果 `col` 超出行的显示宽度，返回字符串的字节长度。
pub fn display_col_to_char_start(line: &str, col: usize) -> usize {
    let mut display_col = 0;
    for (byte_idx, ch) in line.char_indices() {
        let ch_width = UnicodeWidthChar::width(ch).unwrap_or(1);
        if col < display_col + ch_width {
            return byte_idx;
        }
        display_col += ch_width;
    }
    line.len()
}

/// 将 Unicode 显示列号映射为该位置字符的结束字节偏移（不含）。
///
/// 与 `display_col_to_char_start` 对称，用于选区右边界——
/// 落在宽字符内部时包含该完整字符。
pub fn display_col_to_char_end(line: &str, col: usize) -> usize {
    let mut display_col = 0;
    for (byte_idx, ch) in line.char_indices() {
        let ch_width = UnicodeWidthChar::width(ch).unwrap_or(1);
        if col < display_col + ch_width {
            return byte_idx + ch.len_utf8();
        }
        display_col += ch_width;
    }
    line.len()
}

/// 将屏幕坐标转换为内容坐标。
///
/// 返回 `(content_line, display_col)`，其中 `display_col` 是 Unicode 显示列号。
pub fn screen_to_content(
    screen_x: u16,
    screen_y: u16,
    area_rect: Rect,
    scroll_offset: usize,
) -> (usize, usize) {
    // 内容行号 = 可见行偏移 + 滚动偏移
    let visible_row = screen_y.saturating_sub(area_rect.y.saturating_add(1)) as usize;
    let content_line = visible_row.saturating_add(scroll_offset);
    // 内容列号 = 屏幕列 - 区域左边框
    let content_col = screen_x.saturating_sub(area_rect.x.saturating_add(1)) as usize;
    (content_line, content_col)
}

/// 将内容坐标转换为屏幕坐标
///
/// 返回 `(screen_x, screen_y)`，内容不可见时返回 `None`
pub fn content_to_screen(
    content_line: usize,
    content_col: usize,
    area_rect: Rect,
    scroll_offset: usize,
    visible_height: usize,
) -> Option<(u16, u16)> {
    if content_line < scroll_offset {
        return None;
    }
    let visible_line = content_line - scroll_offset;
    if visible_line >= visible_height {
        return None;
    }
    let screen_x = area_rect.x + 1 + content_col as u16;
    let screen_y = area_rect.y + 1 + visible_line as u16;
    Some((screen_x, screen_y))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_display_col_to_char_start_ascii() {
        assert_eq!(display_col_to_char_start("Hello", 0), 0);
        assert_eq!(display_col_to_char_start("Hello", 2), 2);
        assert_eq!(display_col_to_char_start("Hello", 5), 5);
        assert_eq!(display_col_to_char_start("Hello", 10), 5);
    }

    #[test]
    fn test_display_col_to_char_start_cjk() {
        // "你好" — 每个中文字符占 2 显示列、3 字节
        assert_eq!(display_col_to_char_start("你好", 0), 0);
        assert_eq!(display_col_to_char_start("你好", 1), 0); // 宽字符内部 → 回到起点
        assert_eq!(display_col_to_char_start("你好", 2), 3); // 跳过 '你'
        assert_eq!(display_col_to_char_start("你好", 3), 3); // '好' 内部
        assert_eq!(display_col_to_char_start("你好", 4), 6); // 超出
        assert_eq!(display_col_to_char_start("你好", 10), 6);
    }

    #[test]
    fn test_display_col_to_char_start_mixed() {
        // "Hi你好" — H=1,i=1,你=2,好=2
        assert_eq!(display_col_to_char_start("Hi你好", 0), 0);
        assert_eq!(display_col_to_char_start("Hi你好", 1), 1);
        assert_eq!(display_col_to_char_start("Hi你好", 2), 2);
        assert_eq!(display_col_to_char_start("Hi你好", 3), 2); // '你' 内部
        assert_eq!(display_col_to_char_start("Hi你好", 4), 5);
        assert_eq!(display_col_to_char_start("Hi你好", 5), 5); // '好' 内部
        assert_eq!(display_col_to_char_start("Hi你好", 6), 8);
    }

    #[test]
    fn test_display_col_to_char_end_cjk() {
        // "你好" — end 返回 char 的结尾字节（包含完整字符）
        assert_eq!(display_col_to_char_end("你好", 0), 3); // '你' 结束
        assert_eq!(display_col_to_char_end("你好", 1), 3); // '你' 内部也包含
        assert_eq!(display_col_to_char_end("你好", 2), 6); // '好' 结束
        assert_eq!(display_col_to_char_end("你好", 3), 6);
    }

    #[test]
    fn test_extract_text_single_line_ascii() {
        let mut sel = SelectionState::default();
        // "Hello World!" — col 2='l', col 5=' '，选区包含两端字符
        sel.start(UiArea::Chat, 0, 2);
        sel.update(0, 5);
        sel.end();

        let lines = vec!["Hello World!".to_string()];
        sel.extract_text(&lines);
        assert_eq!(sel.selected_text, "llo ");
    }

    #[test]
    fn test_extract_text_single_line_cjk() {
        let mut sel = SelectionState::default();
        // "你好世界" — 你(0-1) 好(2-3) 世(4-5) 界(6-7)
        // col 2~4 触碰 '好' 和 '世' → "好世"
        sel.start(UiArea::Chat, 0, 2);
        sel.update(0, 4);
        sel.end();

        let lines = vec!["你好世界".to_string()];
        sel.extract_text(&lines);
        assert_eq!(sel.selected_text, "好世");
    }

    #[test]
    fn test_extract_text_single_line_cjk_partial() {
        let mut sel = SelectionState::default();
        // "你好世界" — 选择 col 1~3，'你'(0-1) 和 '好'(2-3) 均被触碰 → "你好"
        sel.start(UiArea::Chat, 0, 1);
        sel.update(0, 3);
        sel.end();

        let lines = vec!["你好世界".to_string()];
        sel.extract_text(&lines);
        assert_eq!(sel.selected_text, "你好");
    }

    #[test]
    fn test_extract_text_single_line_cjk_single_char() {
        let mut sel = SelectionState::default();
        // "你好世界" — 选择 col 0~1，只触碰 '你'
        sel.start(UiArea::Chat, 0, 0);
        sel.update(0, 1);
        sel.end();

        let lines = vec!["你好世界".to_string()];
        sel.extract_text(&lines);
        assert_eq!(sel.selected_text, "你");
    }

    #[test]
    fn test_extract_text_single_line_cjk_exact_char() {
        let mut sel = SelectionState::default();
        // "你好世界" — 选择 col 4~5，只选 '世'
        sel.start(UiArea::Chat, 0, 4);
        sel.update(0, 5);
        sel.end();

        let lines = vec!["你好世界".to_string()];
        sel.extract_text(&lines);
        assert_eq!(sel.selected_text, "世");
    }

    #[test]
    fn test_screen_to_content_no_scroll() {
        let rect = Rect::new(0, 3, 50, 10);
        let (line, col) = screen_to_content(5, 4, rect, 0);
        assert_eq!(line, 0);
        assert_eq!(col, 4);
    }

    #[test]
    fn test_screen_to_content_with_scroll() {
        let rect = Rect::new(0, 3, 50, 10);
        let (line, col) = screen_to_content(5, 5, rect, 3);
        assert_eq!(line, 4);
        assert_eq!(col, 4);
    }
}
