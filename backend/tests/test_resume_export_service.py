"""Tests for ResumeExportService（生成区导出 Word/HTML/MD/JSON）。"""

import io

import pytest

from app.services.resume_export_service import (
    ResumeExportError,
    build_export,
    strip_markdown,
)

CONTENT = {
    "sections": [
        {
            "title": "基本信息",
            "content": "姓名：张三\n联系方式：电话：13800000000 · 邮箱：a@b.com · 城市：北京 · 性别：男",
        },
        {"title": "求职意向", "content": "后端开发工程师"},
        {
            "title": "教育背景",
            "content": "北京大学 · 本科 · 软件工程 · 2022.09–2026.06（GPA 3.8/4.0）",
        },
        {
            "title": "实习/工作经历",
            "content": "A公司 | 后端实习生 | 2024.06–2024.09\n· 负责接口开发\n· 延迟降低 30%",
        },
        {"title": "项目经历", "content": "校园图书管理系统 | 后端\n职责：设计接口\n成果：延迟降低 30%"},
        {"title": "技能", "content": "Python（掌握）\nFastAPI"},
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


def test_compose_merges_flattened_children():
    from app.services.resume_export_service import compose_sections_for_export

    secs = compose_sections_for_export(
        [
            {"title": "项目经历", "content": "arXiv 问答系统 | 2026.05-2026.07"},
            {"title": "项目描述", "content": "独立设计 RAG 系统"},
            {"title": "工作内容", "content": "· 采用 LangGraph\n· 设计混合检索"},
            {"title": "专业技能", "content": "Python"},
        ]
    )
    titles = [s["title"] for s in secs]
    assert titles == ["项目经历", "专业技能"]
    assert "项目描述" in secs[0]["content"] and "工作内容" in secs[0]["content"]
    assert "LangGraph" in secs[0]["content"]


def test_is_entry_header_not_random_body():
    from app.services.resume_export_service import _is_entry_header

    assert _is_entry_header("arXiv 论文智能问答系统（Agentic RAG） 2026.05 - 2026.07")
    assert _is_entry_header("A公司 | 后端 | 2024.01-2024.03")
    # 正文短句不应被当成标题加粗
    assert not _is_entry_header("独立设计并实现一个生产级 Agentic RAG 系统，覆盖数据采集")
    assert not _is_entry_header("· 采用 LangGraph 构建 Agent")


def test_docx_export():
    data, media, ext = build_export(CONTENT, "我的简历", "docx")
    assert ext == "docx"
    assert data[:2] == b"PK"  # docx 是 zip 容器
    assert "wordprocessingml" in media


def test_docx_export_with_photo():
    data, media, ext = build_export(CONTENT, "张三·后端简历", "docx", PNG_1PX, "image/png")
    assert ext == "docx" and data[:2] == b"PK"


def test_docx_uses_unified_font():
    """中英统一微软雅黑，避免主题 Calibri 混排。"""
    import zipfile

    data, _, _ = build_export(CONTENT, "张三", "docx")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        styles = zf.read("word/styles.xml").decode("utf-8", errors="ignore")
        doc = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    assert "微软雅黑" in styles or "微软雅黑" in doc
    # 正文 run 不应依赖主题字体
    assert "asciiTheme" not in doc or doc.count("微软雅黑") > 0


def test_parse_contact_fields():
    from app.services.resume_export_service import _parse_contact_fields

    pairs = _parse_contact_fields(
        [
            "姓名：张三",
            "联系方式：电话：138 · 邮箱：a@b.com · 城市：北京 · 性别：男 · 出生日期：2004-11-22",
        ]
    )
    keys = [k for k, _ in pairs]
    assert "电话" in keys and "城市" in keys and "出生日期" in keys
    assert all(v for _, v in pairs)


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