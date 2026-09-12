"""ResumeExportService — 简历生成区导出（Word/HTML/Markdown/JSON）。

- HTML：A4 打印友好模板，可嵌证件照（base64），浏览器可另存 PDF
- DOCX：python-docx，层级标题 + 段落 + 可选证件照
- MD：保留（结构化 `##` 输出）
- JSON：原样
正文统一去 Markdown 残留，避免 `###`/`- ` 直接进 Word/HTML。
"""

from __future__ import annotations

import base64
import html as _html
import io
import json
import re
from typing import Any

VALID_FORMATS = {"docx", "html", "md", "markdown", "json"}

_MD_NOISE = re.compile(r"^\s{0,3}(#{1,6}\s+|\*\*|__|`{1,3})")
_MD_LIST = re.compile(r"^\s{0,3}[-*+]\s+")


class ResumeExportError(ValueError):
    """导出业务错误。"""


def strip_markdown(text: str) -> str:
    """去掉行首 Markdown 标记，保留语义文本。"""
    if not text:
        return ""
    lines: list[str] = []
    for line in str(text).splitlines():
        s = _MD_NOISE.sub("", line)
        s = _MD_LIST.sub("· ", s)
        s = s.replace("**", "").replace("__", "")
        lines.append(s.rstrip())
    return "\n".join(lines).strip()


def _normalized_sections(content: dict[str, Any]) -> list[dict[str, str]]:
    sections = content.get("sections") if isinstance(content, dict) else None
    if not isinstance(sections, list):
        return []
    out: list[dict[str, str]] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        title = strip_markdown(str(sec.get("title") or ""))
        body = strip_markdown(str(sec.get("content") or ""))
        if not title and not body:
            continue
        out.append({"title": title, "content": body})
    return out


def _photo_data_url(photo_bytes: bytes | None, mime: str | None = None) -> str | None:
    if not photo_bytes:
        return None
    mime = (mime or "image/jpeg").split(";")[0].strip() or "image/jpeg"
    b64 = base64.b64encode(photo_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


# ---------- HTML（A4 打印模板） ----------

def build_html(
    content: dict[str, Any],
    title: str,
    photo_bytes: bytes | None = None,
    photo_mime: str | None = None,
) -> str:
    sections = _normalized_sections(content)
    name = title or "个人简历"
    # 尝试从「基本信息」里取姓名作页眉
    for sec in sections:
        if sec["title"] == "基本信息":
            for line in sec["content"].splitlines():
                if line.startswith("姓名："):
                    name = line.split("：", 1)[-1].strip() or name
            break

    photo_url = _photo_data_url(photo_bytes, photo_mime)
    photo_html = (
        f'<img class="photo" src="{photo_url}" alt="证件照" />' if photo_url else ""
    )

    body_parts: list[str] = []
    for sec in sections:
        if sec["title"] == "基本信息":
            # 基本信息渲染为联系方式行，姓名单独用页眉
            lines = [ln for ln in sec["content"].splitlines() if ln.strip()]
            contact = " · ".join(
                ln.split("：", 1)[-1].strip() if "：" in ln else ln.strip()
                for ln in lines
                if not ln.startswith("姓名：")
            )
            body_parts.append(
                f'<header class="hd"><div class="hd-main"><h1>{_html.escape(name)}</h1>'
                f'<p class="contact">{_html.escape(contact)}</p></div>{photo_html}</header>'
            )
            continue
        paras = "".join(
            f"<p>{_html.escape(line)}</p>"
            for line in sec["content"].splitlines()
            if line.strip()
        )
        body_parts.append(
            f'<section class="sec"><h2>{_html.escape(sec["title"])}</h2>{paras}</section>'
        )

    body = "\n".join(body_parts)
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_html.escape(title or name)}</title>"
        "<style>"
        "@page { size: A4; margin: 16mm 14mm; }"
        "* { box-sizing: border-box; }"
        "body { max-width: 210mm; margin: 0 auto; padding: 24px 28px; "
        "font-family: 'Source Han Sans SC','Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif; "
        "color: #1f1c19; line-height: 1.55; background: #fff; font-size: 10.5pt; }"
        ".hd { display: flex; justify-content: space-between; align-items: flex-start; "
        "border-bottom: 2px solid #c15f3c; padding-bottom: 12px; margin-bottom: 16px; }"
        ".hd h1 { margin: 0; font-size: 22pt; letter-spacing: 0.04em; }"
        ".contact { margin: 6px 0 0; color: #444; font-size: 10pt; }"
        ".photo { width: 92px; height: 124px; object-fit: cover; border: 1px solid #ddd; "
        "border-radius: 4px; margin-left: 16px; }"
        ".sec { margin: 14px 0 0; break-inside: avoid; }"
        ".sec h2 { margin: 0 0 6px; font-size: 12pt; color: #9c4a2b; "
        "border-left: 3px solid #c15f3c; padding-left: 8px; letter-spacing: 0.06em; }"
        ".sec p { margin: 2px 0; white-space: pre-wrap; }"
        "@media print { body { padding: 0; max-width: none; } .photo { -webkit-print-color-adjust: exact; } }"
        "</style></head>"
        f"<body>{body}</body></html>"
    )


# ---------- DOCX ----------

def build_docx(
    content: dict[str, Any],
    title: str,
    photo_bytes: bytes | None = None,
    photo_mime: str | None = None,
) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    # 页边距偏窄，贴近简历
    for section in doc.sections:
        section.top_margin = Cm(1.6)
        section.bottom_margin = Cm(1.6)
        section.left_margin = Cm(1.8)
        section.right_margin = Cm(1.8)

    sections = _normalized_sections(content)
    name = title or "个人简历"
    basic_lines: list[str] = []
    for sec in sections:
        if sec["title"] == "基本信息":
            basic_lines = [ln for ln in sec["content"].splitlines() if ln.strip()]
            for ln in basic_lines:
                if ln.startswith("姓名："):
                    name = ln.split("：", 1)[-1].strip() or name
            break

    # 标题行
    head = doc.add_paragraph()
    head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = head.add_run(name)
    run.bold = True
    run.font.size = Pt(18)

    contact_parts = [
        ln.split("：", 1)[-1].strip() if "：" in ln else ln.strip()
        for ln in basic_lines
        if not ln.startswith("姓名：")
    ]
    if contact_parts:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(" · ".join(contact_parts))
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    if photo_bytes:
        try:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run = p.add_run()
            run.add_picture(io.BytesIO(photo_bytes), width=Cm(2.6))
        except Exception:
            # 图片格式异常时跳过，不阻断导出
            pass

    accent = RGBColor(0x9C, 0x4A, 0x2B)
    for sec in sections:
        if sec["title"] == "基本信息":
            continue
        if not sec["title"] and not sec["content"]:
            continue
        if sec["title"]:
            h = doc.add_paragraph()
            h.paragraph_format.space_before = Pt(10)
            h.paragraph_format.space_after = Pt(4)
            hr = h.add_run(sec["title"])
            hr.bold = True
            hr.font.size = Pt(12)
            hr.font.color.rgb = accent
        for line in sec["content"].splitlines():
            line = line.strip()
            if not line:
                continue
            p = doc.add_paragraph(line)
            p.paragraph_format.space_after = Pt(2)
            for run in p.runs:
                run.font.size = Pt(10.5)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# ---------- MD / JSON ----------

def build_markdown(content: dict[str, Any], title: str) -> str:
    """Markdown 导出（保留）。正文先去噪音，再以 ## 标题输出。"""
    sections = _normalized_sections(content)
    if sections:
        raw = "\n\n".join(f"## {s['title']}\n{s['content']}" for s in sections if s["title"])
    else:
        raw = strip_markdown(str(content.get("raw_text") or ""))
    return f"# {title or '简历'}\n\n{raw}".strip() + "\n"


def build_json(content: dict[str, Any]) -> str:
    return json.dumps(content, ensure_ascii=False, indent=2)


def build_export(
    content: dict[str, Any],
    title: str,
    format: str,
    photo_bytes: bytes | None = None,
    photo_mime: str | None = None,
) -> tuple[bytes, str, str]:
    fmt = (format or "docx").lower()
    if fmt == "docx":
        return (
            build_docx(content, title, photo_bytes, photo_mime),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        )
    if fmt == "html":
        return (
            build_html(content, title, photo_bytes, photo_mime).encode("utf-8"),
            "text/html; charset=utf-8",
            "html",
        )
    if fmt in ("md", "markdown"):
        return build_markdown(content, title).encode("utf-8"), "text/markdown; charset=utf-8", "md"
    if fmt == "json":
        return build_json(content).encode("utf-8"), "application/json; charset=utf-8", "json"
    raise ResumeExportError(f"不支持的导出格式: {format!r}，允许 {sorted(VALID_FORMATS)}")
