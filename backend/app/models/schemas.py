"""Pydantic schemas for API data validation."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SessionStage(str, Enum):
    """Session processing stages."""
    INIT = "init"
    HAS_JD = "has_jd"
    HAS_RESUME = "has_resume"
    HAS_JD_AND_RESUME = "has_jd_and_resume"
    COMPLETED = "completed"


# === JD Analysis ===

class JDRequirement(BaseModel):
    """Single job requirement item."""
    category: str = Field(..., description="Category: skill, experience, education, etc.")
    content: str = Field(..., description="Requirement content")
    importance: str = Field(default="medium", description="Importance: high, medium, low")


class JDAnalysis(BaseModel):
    """Job description analysis result."""
    job_title: str = Field(..., description="Job title")
    company: str = Field(default="", description="Company name")
    requirements: list[JDRequirement] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    salary_range: Optional[str] = None
    location: Optional[str] = None
    summary: str = Field(default="", description="Brief summary of the JD")


# === Profile ===

class Experience(BaseModel):
    """Work experience entry."""
    company: str = Field(..., description="Company name")
    title: str = Field(..., description="Job title")
    duration: str = Field(..., description="Duration, e.g., '2022-2024'")
    highlights: list[str] = Field(default_factory=list)


class Project(BaseModel):
    """Project entry."""
    name: str = Field(..., description="Project name")
    description: str = Field(default="", description="Project description")
    tech_stack: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    """Candidate profile."""
    name: str = Field(default="", description="Candidate name")
    email: Optional[str] = None
    phone: Optional[str] = None
    education: list[dict[str, Any]] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    summary: str = Field(default="", description="Professional summary")


# === Gap Analysis ===

class GapItem(BaseModel):
    """Single gap between profile and JD."""
    category: str = Field(..., description="Category: skill, experience, etc.")
    requirement: str = Field(..., description="What JD requires")
    current_level: str = Field(default="", description="Current level in profile")
    gap_severity: str = Field(default="medium", description="Severity: critical, major, minor")
    suggestion: str = Field(default="", description="How to bridge the gap")


class GapAnalysis(BaseModel):
    """Gap analysis result."""
    overall_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Match score 0-100")
    gaps: list[GapItem] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


# === Resume ===

class ResumeSection(BaseModel):
    """Single resume section."""
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content in markdown")


class ResumeContent(BaseModel):
    """Structured resume content."""
    sections: list[ResumeSection] = Field(default_factory=list)
    raw_text: str = Field(default="", description="Raw resume text")


# === Render Config ===

class RenderConfig(BaseModel):
    """Resume render configuration."""
    template: str = Field(default="classic", description="Template name")
    font_size: int = Field(default=11, ge=8, le=14)
    margin_top: float = Field(default=1.0, ge=0.5, le=2.0)
    margin_bottom: float = Field(default=1.0, ge=0.5, le=2.0)
    margin_left: float = Field(default=1.0, ge=0.5, le=2.0)
    margin_right: float = Field(default=1.0, ge=0.5, le=2.0)
    line_spacing: float = Field(default=1.15, ge=1.0, le=2.0)
    accent_color: str = Field(default="#2563eb", description="Accent color hex")


# === Interview ===

class InterviewQuestion(BaseModel):
    """Interview question with answer guidance."""
    question: str = Field(..., description="The interview question")
    category: str = Field(default="behavioral", description="Category: behavioral, technical, situational")
    difficulty: str = Field(default="medium", description="Difficulty: easy, medium, hard")
    answer_points: list[str] = Field(default_factory=list, description="Key points for answer")
    sample_answer: str = Field(default="", description="Sample answer")


# === API Request/Response Models ===

class SessionCreateResponse(BaseModel):
    """Response for session creation."""
    session_id: str = Field(..., description="Unique session ID")
    created_at: datetime = Field(default_factory=datetime.now)


class MessageRequest(BaseModel):
    """Request to send a message."""
    content: str = Field(..., description="Message content")
    role: str = Field(default="user", description="Message role: user or assistant")


class MessageResponse(BaseModel):
    """Response message."""
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionDetail(BaseModel):
    """Detailed session information."""
    session_id: str
    stage: SessionStage = Field(default=SessionStage.INIT)
    jd_analysis: Optional[JDAnalysis] = None
    profile: Optional[Profile] = None
    gap_analysis: Optional[GapAnalysis] = None
    resume_content: Optional[ResumeContent] = None
    render_config: RenderConfig = Field(default_factory=RenderConfig)
    messages: list[MessageResponse] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SSEEvent(BaseModel):
    """Server-Sent Event data."""
    event: str = Field(..., description="Event type: message, error, done")
    data: dict[str, Any] = Field(default_factory=dict)
    id: Optional[str] = None
    retry: Optional[int] = None


class ErrorResponse(BaseModel):
    """Error response."""
    detail: str = Field(..., description="Error message")
    code: str = Field(default="UNKNOWN_ERROR", description="Error code")
