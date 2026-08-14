"""文件处理工具：file_parser, text_cleaner。"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from .base import Tool, ToolResult

logger = logging.getLogger(__name__)


class FileParserTool(Tool):
    """文件解析工具 — 支持 PDF / DOCX / TXT / MD。"""

    name = "file_parser"
    description = "解析 PDF/DOCX/TXT/MD 文件，提取纯文本内容。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "文件路径（与 file_content 二选一）",
            },
            "file_content": {
                "type": "string",
                "description": "文件内容（base64 编码，与 file_path 二选一）",
            },
            "filename": {
                "type": "string",
                "description": "文件名（用于判断文件类型）",
            },
        },
        "required": [],
    }

    _SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}

    async def execute(
        self,
        file_path: str | None = None,
        file_content: str | None = None,
        filename: str | None = None,
        **kwargs,
    ) -> ToolResult:
        """解析文件内容。支持文件路径或 base64 编码内容。"""
        try:
            if file_path:
                path = Path(file_path)
                if not path.exists():
                    return ToolResult.fail(f"文件不存在: {file_path}")
                text = self._parse_file(path)
            elif file_content and filename:
                data = self._decode_content(file_content)
                text = self._parse_bytes(data, filename)
            else:
                return ToolResult.fail("必须提供 file_path 或 file_content + filename")

            return ToolResult.ok({"text": text, "length": len(text)})
        except Exception as e:
            return ToolResult.fail(f"文件解析失败: {e}")

    def _parse_file(self, path: Path) -> str:
        """解析文件路径。"""
        suffix = path.suffix.lower()
        if suffix not in self._SUPPORTED_SUFFIXES:
            raise ValueError(f"不支持的文件类型: {suffix}")

        if suffix == ".pdf":
            return self._parse_pdf(path)
        elif suffix == ".docx":
            return self._parse_docx(path)
        else:
            return self._parse_text(path)

    def _parse_bytes(self, data: bytes, filename: str) -> str:
        """解析内存中的文件内容。"""
        suffix = Path(filename).suffix.lower()
        if suffix not in self._SUPPORTED_SUFFIXES:
            raise ValueError(f"不支持的文件类型: {suffix}")

        if suffix == ".pdf":
            return self._parse_pdf_bytes(data)
        elif suffix == ".docx":
            return self._parse_docx_bytes(data)
        else:
            return data.decode("utf-8")

    def _parse_pdf(self, path: Path) -> str:
        """解析 PDF 文件。"""
        import pdfplumber

        text_parts = []
        with pdfplumber.open(path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"[FileParser] PDF 总页数: {total_pages}, 文件: {path.name}")
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    text_parts.append(text)
                    logger.debug(f"[FileParser] PDF 第 {i+1}/{total_pages} 页提取到 {len(text)} 字符")
                else:
                    logger.warning(f"[FileParser] PDF 第 {i+1}/{total_pages} 页未提取到文本（可能是扫描件或图片页）")

        result = "\n\n".join(text_parts)
        logger.info(f"[FileParser] PDF 解析完成: {len(text_parts)}/{total_pages} 页有文本, 总计 {len(result)} 字符")
        if not result:
            raise ValueError(f"PDF 文件所有页面均未提取到文本（共 {total_pages} 页）。可能原因：1) 扫描件/图片型 PDF 2) PDF 加密 3) PDF 损坏")

        # 基础文本清洗
        result = self._clean_text(result)
        return result

    def _parse_pdf_bytes(self, data: bytes) -> str:
        """解析 PDF 字节数据。"""
        import pdfplumber

        text_parts = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"[FileParser] PDF 字节数据解析, 总页数: {total_pages}")
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    text_parts.append(text)
                    logger.debug(f"[FileParser] PDF 第 {i+1}/{total_pages} 页提取到 {len(text)} 字符")
                else:
                    logger.warning(f"[FileParser] PDF 第 {i+1}/{total_pages} 页未提取到文本")

        result = "\n\n".join(text_parts)
        logger.info(f"[FileParser] PDF 解析完成: {len(text_parts)}/{total_pages} 页有文本, 总计 {len(result)} 字符")
        if not result:
            raise ValueError(f"PDF 文件所有页面均未提取到文本（共 {total_pages} 页）。可能原因：1) 扫描件/图片型 PDF 2) PDF 加密 3) PDF 损坏")

        # 基础文本清洗
        result = self._clean_text(result)
        return result

    def _parse_docx(self, path: Path) -> str:
        """解析 DOCX 文件。"""
        from docx import Document

        doc = Document(str(path))
        text_parts = [p.text for p in doc.paragraphs if p.text.strip()]
        logger.info(f"[FileParser] DOCX 解析完成: {len(text_parts)} 个段落, 文件: {path.name}")
        result = "\n\n".join(text_parts)
        if not result:
            raise ValueError(f"DOCX 文件未提取到任何文本内容")

        # 基础文本清洗
        result = self._clean_text(result)
        return result

    def _parse_docx_bytes(self, data: bytes) -> str:
        """解析 DOCX 字节数据。"""
        from docx import Document

        doc = Document(io.BytesIO(data))
        text_parts = [p.text for p in doc.paragraphs if p.text.strip()]
        logger.info(f"[FileParser] DOCX 字节数据解析完成: {len(text_parts)} 个段落")
        result = "\n\n".join(text_parts)
        if not result:
            raise ValueError(f"DOCX 文件未提取到任何文本内容")

        # 基础文本清洗
        result = self._clean_text(result)
        return result

    def _parse_text(self, path: Path) -> str:
        """解析文本文件（TXT/MD）。"""
        return path.read_text(encoding="utf-8")

    def _decode_content(self, content: str) -> bytes:
        """解码 base64 内容。"""
        import base64

        return base64.b64decode(content)

    def _clean_text(self, text: str) -> str:
        """基础文本清洗，去除 PDF 解析产生的格式噪音。"""
        # 统一换行符
        text = re.sub(r"\r\n", "\n", text)
        # 去除多余空行（保留最多两个连续换行）
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 去除行首行尾空白
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)
        # 去除多余空格（保留单个空格）
        text = re.sub(r"[ \t]+", " ", text)
        # 去除 PDF 解析常见噪音字符
        text = re.sub(r"[^\w\s一-鿿.,;:!?()（）【】《》\"'\-@#/\\]", "", text)
        return text.strip()


class TextCleanerTool(Tool):
    """文本清洗工具 — 清理文本格式，提取有效内容。"""

    name = "text_cleaner"
    description = "清理文本格式，去除多余空白、特殊字符等。"
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "待清洗的文本",
            },
            "mode": {
                "type": "string",
                "enum": ["basic", "aggressive"],
                "description": "清洗模式：basic（基础）或 aggressive（激进）",
            },
        },
        "required": ["text"],
    }

    async def execute(
        self, text: str, mode: str = "basic", **kwargs
    ) -> ToolResult:
        """清洗文本。"""
        try:
            cleaned = self._clean(text, mode)
            return ToolResult.ok(
                {"text": cleaned, "original_length": len(text), "cleaned_length": len(cleaned)}
            )
        except Exception as e:
            return ToolResult.fail(f"文本清洗失败: {e}")

    def _clean(self, text: str, mode: str) -> str:
        """执行清洗。"""
        # 基础清洗
        text = text.strip()
        text = re.sub(r"\r\n", "\n", text)  # 统一换行符
        text = re.sub(r"\n{3,}", "\n\n", text)  # 去除多余空行
        text = re.sub(r"[ \t]+", " ", text)  # 去除多余空格

        if mode == "aggressive":
            # 激进清洗
            text = re.sub(r"[^\w\s一-鿿.,;:!?()（）【】《》\"']", "", text)  # 保留中英文和标点
            text = re.sub(r"\s+", " ", text)  # 合并所有空白

        return text.strip()
