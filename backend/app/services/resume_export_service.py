"""ResumeExportService — 简历生成区导出（Word/HTML/Markdown/JSON 文件字节）。

输入为 `ResumeContent` 形态 {sections:[{title,content}], raw_text}，
返回可直接作为下载文件的字节/文本，不落盘。
"""

from __future__ import annotations

import html as _html
import io
import json
from typing import Any

VALID_FORMATS = {"docx", "html", "md", "markdown", "json"}


class ResumeExportError(ValueError):
    """导出业务错误。"""


def _normalized_sections(content: dict[str, Any]) -> list[dict[str, str]]:
    sections = content.get("sections") if isinstance(content, dict) else None
    if not isinstance(sections, list):
        return []
    out: list[dict[str, str]] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title") or "").strip()
        body = str(sec.get("content") or "").strip()
        out.append({"title": title, "content": body})
    return out


def build_docx(content: dict[str, Any], title: str) -> bytes:
    """用 python-docx 生成 Word 文档字节。"""
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    doc.add_heading(title or "简历", level=0)

    for sec in _normalized_sections(content):
        doc.add_heading(sec["title"], level=1)
        for line in sec["content"].split("\n"):
            line = line.strip()
            if not line:
                doc.add_paragraph("")
                continue
            p = doc.add_paragraph(line)
            for run in p.runs:
                run.font.size = Pt(10.5)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def build_html(content: dict[str, Any], title: str) -> str:
    """生成简洁、可打印的 HTML（浏览器可直接另存为 PDF）。"""
    parts = [f"<h1>{_html.escape(title or '简历')}</h1>"]
    for sec in _normalized_sections(content):
        parts.append(f"<h2>{_html.escape(sec['title'])}</h2>")
        parts.append(f"<p>{_html.escape(sec['content']).replace(chr(10), '<br>')}</p>")
    body = "\n".join(parts)
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_html.escape(title or '简历')}</title>"
        "<style>body{max-width:720px;margin:40px auto;font-family:'Noto Serif SC',Georgia,serif;"
        "line-height:1.7;color:#2d2a26;padding:0 24px}h1{font-size:26px}h2{font-size:18px;"
        "color:#9c4a2b;margin-top:24px}p{margin:6px 0}</style></head>"
        f"<body>{body}</body></html>"
    )


def build_markdown(content: dict[str, Any], title: str) -> str:
    sections = _normalized_sections(content)
    if sections:
        raw = "\n\n".join(f"## {s['title']}\n{s['content']}" for s in sections)
    else:
        raw = str(content.get("raw_text") or "").strip()
    return f"# {title or '简历'}\n\n{raw}".strip() + "\n"


def build_json(content: dict[str, Any]) -> str:
    return json.dumps(content, ensure_ascii=False, indent=2)


# 返回 (字节, media_type, 后缀)
def build_export(content: dict[str, Any], title: str, format: str) -> tuple[bytes, str, str]:
    fmt = (format or "docx").lower()
    if fmt == "docx":
        return build_docx(content, title), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    if fmt == "html":
        return build_html(content, title).encode("utf-8"), "text/html; charset=utf-8", "html"
    if fmt in ("md", "markdown"):
        return build_markdown(content, title).encode("utf-8"), "text/markdown; charset=utf-8", "md"
    if fmt == "json":
        return build_json(content).encode("utf-8"), "application/json; charset=utf-8", "json"
    raise ResumeExportError(f"不支持的导出格式: {format!r}，允许 {sorted(VALID_FORMATS)}")
