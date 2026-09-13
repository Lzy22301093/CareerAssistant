"""Resume template assembly tests."""

from app.models.schemas import StarResultItem, WizardGenerateRequest
from app.services.resume_template import (
    assemble_with_template,
    clamp_text,
    format_skills,
    get_template,
)
from app.services.resume_wizard_service import ResumeWizardService


def test_clamp_text_stops_at_sentence():
    s = clamp_text("这是一句很长的自我评价。后面还有很多字不该出现", 12)
    assert s.endswith("。") or s.endswith("…")
    assert len(s) <= 13


def test_format_skills_groups():
    text = format_skills(
        ["Python", "Java", "Spring Boot", "MySQL", "Docker", "Git", "沟通能力", "Kafka"]
    )
    assert "语言" in text or "Python" in text
    assert "、" in text or ":" in text or "：" in text


def test_assemble_campus_clamps_summary_and_bullets():
    long_eval = "本人热爱钻研。" * 30
    assembled = assemble_with_template(
        basic={
            "name": "张三",
            "phone": "13800000000",
            "email": "a@b.com",
            "education": ["北京大学 本科 软件工程"],
            "skills": ["Python", "FastAPI", "MySQL"],
        },
        directions=["后端开发"],
        experiences=[
            StarResultItem(
                exp_type="项目",
                company="某平台",
                title="后端",
                duration="2024",
                duty="负责接口开发与优化，完成多项指标",
                action="设计缓存与异步任务",
                result="QPS 提升 40%",
                achievement="QPS 提升 40%",
            )
        ],
        soft={"self_eval": long_eval, "personality": "踏实"},
        template_key="campus_one_page",
        page_preference="one_page",
    )
    titles = [s["title"] for s in assembled.sections]
    assert "基本信息" in titles
    assert "项目经历" in titles
    # 模板顺序：教育在项目前
    assert titles.index("教育背景") < titles.index("项目经历")
    summary = next(s for s in assembled.sections if s["title"] == "个人优势")
    assert len(summary["content"]) <= 110
    proj = next(s for s in assembled.sections if s["title"] == "项目经历")
    assert "· " in proj["content"]
    # 空证书不生成
    assert "证书/荣誉" not in titles


def test_assemble_tech_puts_project_before_education():
    assembled = assemble_with_template(
        basic={"name": "李四", "education": ["某大学"], "skills": ["Go"]},
        directions=["后端"],
        experiences=[
            StarResultItem(exp_type="项目", company="X", title="dev", duty="写代码", result="上线")
        ],
        soft={},
        template_key="tech",
    )
    titles = [s["title"] for s in assembled.sections]
    assert titles.index("项目经历") < titles.index("教育背景")


def test_generate_resume_uses_template_no_polish(db_session=None):
    # 纯组装路径（不依赖 db）
    from app.services.resume_template import assemble_with_template

    req = WizardGenerateRequest(
        title="测试",
        basic_info={"name": "王五", "skills": ["Python"]},
        directions=["算法"],
        experiences=[],
        soft_info={"self_eval": "认真负责"},
        polish=False,
        import_to_library=False,
        template="general",
    )
    assembled = assemble_with_template(
        basic=req.basic_info,
        directions=req.directions,
        experiences=req.experiences,
        soft=req.soft_info,
        template_key=req.template,
    )
    titles = [s["title"] for s in assembled.sections]
    assert "自我评价" in titles  # general 模板用「自我评价」标题
    assert get_template("general").summary_title == "自我评价"


def test_empty_modules_hidden():
    assembled = assemble_with_template(
        basic={"name": "空空"},
        directions=[],
        experiences=[],
        soft={},
        template_key="campus_one_page",
    )
    titles = [s["title"] for s in assembled.sections]
    assert titles == ["基本信息"]
