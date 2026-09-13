"""面试上下文（JD+简历为主）单元测试。"""

from app.interview.context import (
    compact_resume,
    extract_resume_topics,
    format_profile_supplement,
    format_resume_for_prompt,
)


def test_compact_resume_from_sections():
    r = compact_resume(
        {
            "title": "张三·后端简历",
            "sections": [
                {"title": "项目经历", "content": "仿小红书 | 后端 | 2024\n· 实现 JWT\n· QPS+40%"},
                {"title": "技能", "content": "Python、Spring"},
            ],
            "raw_text": "",
        }
    )
    assert r["title"]
    assert len(r["sections"]) == 2
    assert "JWT" in r["raw_text"]


def test_format_resume_for_prompt_includes_sections():
    text = format_resume_for_prompt(
        {"sections": [{"title": "项目经历", "content": "某某平台"}], "title": "简历"}
    )
    assert "项目经历" in text
    assert "某某平台" in text


def test_extract_resume_topics():
    topics = extract_resume_topics(
        {
            "sections": [
                {"title": "项目经历", "content": "内容分享平台 | 后端\n· 细节"},
                {"title": "技能", "content": "Python"},
            ]
        }
    )
    assert any("内容分享平台" in t for t in topics)


def test_profile_supplement_short():
    s = format_profile_supplement(
        {"name": "张三", "skills": ["Python", "MySQL"], "summary": "认真"}
    )
    assert "张三" in s
    assert "Python" in s
