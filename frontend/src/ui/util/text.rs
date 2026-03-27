//! # 文本处理工具
//!
//! 提供文本格式化和换行功能。

use unicode_width::UnicodeWidthChar;

/// 手动文本换行辅助函数
///
/// 将给定文本按指定宽度进行换行处理，正确处理 Unicode 字符宽度。
///
/// # 参数
/// * `text` - 要格式化的文本
/// * `width` - 每行最大宽度（字符宽度）
///
/// # 返回
/// 格式化后的行向量
///
/// # 示例
/// ```
/// use alice_frontend::ui::format_text_to_lines;
///
/// let lines = format_text_to_lines("Hello 世界", 5);
/// // ["Hello", "世界"]
/// ```
pub fn format_text_to_lines(text: &str, width: usize) -> Vec<String> {
    if width == 0 {
        return vec![text.to_string()];
    }

    let mut lines = Vec::new();

    for paragraph in text.split('\n') {
        if paragraph.is_empty() {
            lines.push(String::new());
            continue;
        }

        let mut current_line = String::new();
        let mut current_width = 0;
        let mut preserving_leading_whitespace = true;

        for ch in paragraph.chars() {
            let ch_width = UnicodeWidthChar::width(ch).unwrap_or(1);

            // 如果添加当前字符会超出宽度
            if current_width + ch_width > width {
                // 当前行非空时，先保存当前行
                if !current_line.is_empty() {
                    lines.push(current_line);
                    current_line = String::new();
                    current_width = 0;
                }

                // 处理单个字符宽度超过行宽的情况
                if ch_width > width {
                    // 这种情况下，将字符单独成行
                    current_line.push(ch);
                    current_width = ch_width;
                    continue;
                }
            }

            if current_line.is_empty() && ch.is_whitespace() && !preserving_leading_whitespace {
                continue;
            }

            current_line.push(ch);
            current_width += ch_width;

            if !ch.is_whitespace() {
                preserving_leading_whitespace = false;
            }
        }

        // 添加最后一行
        if !current_line.is_empty() {
            lines.push(current_line);
        }
    }

    lines
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_text() {
        assert_eq!(format_text_to_lines("", 10), vec![""]);
    }

    #[test]
    fn test_zero_width() {
        assert_eq!(format_text_to_lines("test", 0), vec!["test"]);
    }

    #[test]
    fn test_simple_wrapping() {
        let result = format_text_to_lines("Hello World", 5);
        assert_eq!(result, vec!["Hello", "World"]);
    }

    #[test]
    fn test_preserve_newlines() {
        let result = format_text_to_lines("Line1\nLine2", 10);
        assert_eq!(result, vec!["Line1", "Line2"]);
    }

    #[test]
    fn test_unicode_width() {
        let result = format_text_to_lines("你好世界", 4);
        // 每个中文字符宽度为 2
        assert_eq!(result, vec!["你好", "世界"]);
    }

    #[test]
    fn test_mixed_unicode() {
        let result = format_text_to_lines("Hi你好", 5);
        // H=1, i=1, 你=2 -> 总共 4，可以放下
        // 好=2，另起一行
        assert_eq!(result, vec!["Hi你", "好"]);
    }

    #[test]
    fn test_preserve_leading_spaces_when_wrapping() {
        let result = format_text_to_lines("    abc", 4);
        assert_eq!(result, vec!["    ", "abc"]);
    }

    #[test]
    fn test_preserve_leading_spaces_after_newline() {
        let result = format_text_to_lines("title\n  nested", 20);
        assert_eq!(result, vec!["title", "  nested"]);
    }
}
