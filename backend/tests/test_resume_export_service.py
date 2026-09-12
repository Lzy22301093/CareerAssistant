"""Tests for ResumeExportService（生成区导出 Word/HTML/MD/JSON）。"""

import pytest

from app.services.resume_export_service import (
    ResumeExportError,
    build_export,
    strip_markdown,
)

CONTENT = {
    "sections": [
        {"title": "基本信息", "content": "姓名：张三\n电话：13800000000"},
        {"title": "项目经历", "content": "校园图书管理系统 | 后端\n职责：设计接口\n成果：延迟降低 30%"},
        {"title": "技能", "content": "Python\nFastAPI"},
    ],
    "raw_text": "姓名：张三\n技能",
}

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_strip_markdown():
    assert strip_markdown("### 标题") == "标题"
    assert "- 职责：做 X".startswith("· 职责") or strip_markdown("- 职责：做 X") == "· 职责：做 X"
    assert "**加粗**" not in strip_markdown("**加粗**")


def test_docx_export():
    data, media, ext = build_export(CONTENT, "我的简历", "docx")
    assert ext == "docx"
    assert data[:2] == b"PK"  # docx 是 zip 容器
    assert "wordprocessingml" in media


def test_docx_export_with_photo():
    data, media, ext = build_export(CONTENT, "张三·后端简历", "docx", PNG_1PX, "image/png")
    assert ext == "docx" and data[:2] == b"PK"


def test_html_export():
    data, media, ext = build_export(CONTENT, "我的简历", "html")
    assert ext == "html"
    assert b"<h1>" in data and "姓名：张三".encode() in data or b"\xe5\xbc\xa0\xe4\xb8\x89" in data
    assert b"###" not in data  # 无 Markdown 残留
    assert "text/html" in media


def test_html_export_embeds_photo():
    data, _, _ = build_export(CONTENT, "简历", "html", PNG_1PX, "image/png")
    assert b"data:image/png;base64," in data


def test_md_export_and_alias():
    data, media, ext = build_export(CONTENT, "我的简历", "md")
    assert ext == "md" and "## 基本信息".encode() in data and "技能".encode() in data
    _, _, ext2 = build_export(CONTENT, "x", "markdown")
    assert ext2 == "md"


def test_json_export():
    data, media, ext = build_export(CONTENT, "x", "json")
    assert ext == "json" and "基本信息".encode() in data


def test_invalid_format_rejected():
    with pytest.raises(ResumeExportError):
        build_export(CONTENT, "x", "pdf")


def test_empty_content_ok():
    _, _, ext = build_export({}, "x", "json")
    assert ext == "json"