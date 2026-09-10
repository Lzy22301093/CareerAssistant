"""Tests for ResumeExportService（生成区导出 Word/HTML/MD/JSON）。"""

import pytest

from app.services.resume_export_service import ResumeExportError, build_export

CONTENT = {
    "sections": [
        {"title": "基本信息", "content": "姓名：张三"},
        {"title": "技能", "content": "Python\nFastAPI"},
    ],
    "raw_text": "姓名：张三\n技能",
}


def test_docx_export():
    data, media, ext = build_export(CONTENT, "我的简历", "docx")
    assert ext == "docx"
    assert data[:2] == b"PK"  # docx 是 zip 容器
    assert "wordprocessingml" in media


def test_html_export():
    data, media, ext = build_export(CONTENT, "我的简历", "html")
    assert ext == "html"
    assert b"<h1>" in data and "姓名：张三".encode() in data
    assert "text/html" in media


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
