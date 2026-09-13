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
        result = extract_docx_text(doc)
        logger.info(f"[FileParser] DOCX 解析完成: {len(result)} 字符, 文件: {path.name}")
        if not result:
            raise ValueError(
                "DOCX 文件未提取到任何文本内容。可能原因：1) 纯图片/扫描简历 2) 文件损坏 3) 内容在旧版 .doc（请另存为 .docx）"
            )

        # 基础文本清洗
        result = self._clean_text(result)
        if not result:
            raise ValueError("DOCX 提取到的文本在清洗后为空（可能全是图片或特殊对象）")
        return result

    def _parse_docx_bytes(self, data: bytes) -> str:
        """解析 DOCX 字节数据。"""
        from docx import Document

        doc = Document(io.BytesIO(data))
        result = extract_docx_text(doc)
        logger.info(f"[FileParser] DOCX 字节数据解析完成: {len(result)} 字符")
        if not result:
            raise ValueError(
                "DOCX 文件未提取到任何文本内容。可能原因：1) 纯图片/扫描简历 2) 文件损坏 3) 内容在旧版 .doc（请另存为 .docx）"
            )

        # 基础文本清洗
        result = self._clean_text(result)
        if not result:
            raise ValueError("DOCX 提取到的文本在清洗后为空（可能全是图片或特殊对象）")
        return result

    def _parse_text(self, path: Path) -> str:
        """解析文本文件（TXT/MD）。"""
        return path.read_text(encoding="utf-8")

    def _decode_content(self, content: str) -> bytes:
        """解码 base64 内容。"""
        import base64

        return base64.b64decode(content)

    def _clean_text(self, text: str) -> str:
        """基础文本清洗：去空白噪音，**保留中文标点与常用符号**。"""
        # 统一换行符
        text = re.sub(r"\r\n?", "\n", text)
        # 去除多余空行（保留最多两个连续换行）
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 去除行首行尾空白
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)
        # 去除多余空格/制表（保留单个空格）
        text = re.sub(r"[ \t　]+", " ", text)
        # 仅去掉控制字符与替换符；不要扫掉中文标点（，、：；→· 等）
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f�]", "", text)
        return text.strip()


def extract_docx_text(doc) -> str:
    """从 python-docx Document 提取正文：段落 + 表格 + 文本框。

    简历模板大量使用表格/文本框排版，仅读 doc.paragraphs 会得到空文本。
    """
    parts: list[str] = []
    seen: set[str] = set()

    def _push(s: str) -> None:
        s = (s or "").strip()
        if s and s not in seen:
            seen.add(s)
            parts.append(s)

    def _walk_table(table) -> None:
        for row in table.rows:
            cells: list[str] = []
            for cell in row.cells:
                cell_lines = [p.text.strip() for p in cell.paragraphs if p.text and p.text.strip()]
                # 嵌套表格
                for nested in getattr(cell, "tables", []) or []:
                    nested_text = []
                    for nrow in nested.rows:
                        nested_text.append(" ".join(c.text.strip() for c in nrow.cells if c.text and c.text.strip()))
                    if any(nested_text):
                        cell_lines.append(" ".join(t for t in nested_text if t))
                if cell_lines:
                    cells.append(" / ".join(cell_lines) if len(cell_lines) > 1 else cell_lines[0])
            line = " | ".join(dict.fromkeys(c for c in cells if c))  # 去重相邻合并单元格
            _push(line)

    # 1) 文档流中的段落与表格（保持大致顺序）
    body = doc.element.body
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in body.iterchildren():
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            _push(Paragraph(child, doc).text)
        elif tag == "tbl":
            _walk_table(Table(child, doc))

    # 2) 兜底：仍为空则扫全部 tables / paragraphs
    if not parts:
        for p in doc.paragraphs:
            _push(p.text)
        for table in doc.tables:
            _walk_table(table)

    # 3) 文本框 / 形状内文字（w:txbxContent → w:t）
    try:
        from docx.oxml.ns import qn

        for txbx in body.iter(qn("w:txbxContent")):
            texts = [t.text or "" for t in txbx.iter(qn("w:t"))]
            _push("".join(texts))
    except Exception:
        pass

    # 4) 页眉页脚（部分模板把姓名/联系方式放页眉）
    try:
        for section in doc.sections:
            for part in (
                section.header,
                section.first_page_header,
                section.even_page_header,
                section.footer,
            ):
                if part is None:
                    continue
                for p in part.paragraphs:
                    _push(p.text)
                for table in part.tables:
                    _walk_table(table)
    except Exception:
        pass

    return "\n".join(parts)


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
