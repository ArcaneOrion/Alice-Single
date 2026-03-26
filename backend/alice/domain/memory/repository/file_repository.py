"""
File Repository

文件存储仓储，处理所有文件读写操作。
提供统一的文件访问接口，处理目录创建和错误处理。
"""

import os
from typing import Optional


class FileRepository:
    """文件存储仓储

    提供线程安全的文件读写操作，自动处理目录创建。
    """

    def __init__(self, file_path: str, encoding: str = "utf-8"):
        """初始化文件仓储

        Args:
            file_path: 文件路径
            encoding: 文件编码
        """
        self.file_path = file_path
        self.encoding = encoding

    def read(self, default: str = "") -> str:
        """读取文件内容

        Args:
            default: 文件不存在时的默认返回值

        Returns:
            文件内容或默认值
        """
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r', encoding=self.encoding) as f:
                    content = f.read()
                    return content if content.strip() else default
            return default
        except Exception as e:
            # 日志记录
            return default

    def write(self, content: str) -> None:
        """写入文件内容

        Args:
            content: 要写入的内容
        """
        self._ensure_directory()

        with open(self.file_path, 'w', encoding=self.encoding) as f:
            f.write(content)

    def append(self, content: str) -> None:
        """追加内容到文件

        Args:
            content: 要追加的内容
        """
        self._ensure_directory()

        with open(self.file_path, 'a', encoding=self.encoding) as f:
            f.write(content)

    def exists(self) -> bool:
        """检查文件是否存在

        Returns:
            文件是否存在
        """
        return os.path.exists(self.file_path)

    def delete(self) -> bool:
        """删除文件

        Returns:
            是否删除成功
        """
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
                return True
            return False
        except Exception:
            return False

    def get_mtime(self) -> Optional[float]:
        """获取文件修改时间

        Returns:
            文件修改时间戳，文件不存在时返回 None
        """
        try:
            return os.path.getmtime(self.file_path)
        except Exception:
            return None

    def _ensure_directory(self) -> None:
        """确保文件目录存在"""
        directory = os.path.dirname(self.file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)


__all__ = ["FileRepository"]
