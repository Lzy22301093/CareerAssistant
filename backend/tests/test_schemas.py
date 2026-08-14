"""Tests for Pydantic schemas."""

import json

from app.models.schemas import (
    Experience,
    GapAnalysis,
    GapItem,
    JDAnalysis,
    JDRequirement,
    Profile,
    Project,
    RenderConfig,
    ResumeContent,
    ResumeSection,
    SessionDetail,
    SessionStage,
)


def test_jd_analysis_create():
    """Test JDAnalysis creation with required and default fields."""
    jd = JDAnalysis(
        job_title="Python Developer",
        company="Tech Corp",
        requirements=[
            JDRequirement(category="skill", content="Python 3.10+"),
            JDRequirement(category="experience", content="3+ years", importance="high"),
        ],
    )

    assert jd.job_title == "Python Developer"
    assert jd.company == "Tech Corp"
    assert len(jd.requirements) == 2
    assert jd.requirements[0].importance == "medium"  # default
    assert jd.requirements[1].importance == "high"
    assert jd.nice_to_have == []  # default
    assert jd.salary_range is None  # default


def test_profile_create():
    """Test Profile creation with nested models."""
    profile = Profile(
        name="John Doe",
        email="john@example.com",
        skills=["Python", "FastAPI"],
        experience=[
            Experience(company="Corp A", title="Dev", duration="2020-2022"),
        ],
        projects=[
            Project(name="Project X", tech_stack=["Python", "Redis"]),
        ],
    )

    assert profile.name == "John Doe"
    assert len(profile.skills) == 2
    assert len(profile.experience) == 1
    assert profile.experience[0].company == "Corp A"
    assert len(profile.projects) == 1
    assert profile.projects[0].tech_stack == ["Python", "Redis"]


def test_gap_analysis_score():
    """Test GapAnalysis overall_score defaults and constraints."""
    gap = GapAnalysis()
    assert gap.overall_score == 0.0  # default
    assert gap.gaps == []  # default
    assert gap.strengths == []  # default

    # Test with valid score
    gap_with_score = GapAnalysis(
        overall_score=75.5,
        gaps=[GapItem(category="skill", requirement="Docker", gap_severity="minor")],
    )
    assert gap_with_score.overall_score == 75.5
    assert len(gap_with_score.gaps) == 1


def test_render_config_defaults():
    """Test RenderConfig default values."""
    config = RenderConfig()

    assert config.template == "classic"
    assert config.font_size == 11
    assert config.margin_top == 1.0
    assert config.margin_bottom == 1.0
    assert config.margin_left == 1.0
    assert config.margin_right == 1.0
    assert config.line_spacing == 1.15
    assert config.accent_color == "#2563eb"


def test_session_detail_serialization():
    """Test SessionDetail can be serialized to JSON."""
    session = SessionDetail(
        session_id="test-123",
        stage=SessionStage.HAS_JD,
        jd_analysis=JDAnalysis(job_title="Dev"),
        messages=[],
    )

    # Serialize to dict
    data = session.model_dump()
    assert data["session_id"] == "test-123"
    assert data["stage"] == "has_jd"
    assert data["jd_analysis"]["job_title"] == "Dev"

    # Serialize to JSON string
    json_str = session.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["session_id"] == "test-123"


def test_resume_content():
    """Test ResumeContent with sections."""
    resume = ResumeContent(
        sections=[
            ResumeSection(title="Experience", content="Worked at Corp A"),
            ResumeSection(title="Education", content="BS in CS"),
        ],
        raw_text="Full resume text here",
    )

    assert len(resume.sections) == 2
    assert resume.sections[0].title == "Experience"
    assert resume.raw_text == "Full resume text here"
