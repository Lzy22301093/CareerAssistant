"""SQLAlchemy ORM models for database persistence."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class User(Base):
    """User table for authentication."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    sessions: Mapped[list["AnalysisSession"]] = relationship(back_populates="user")
    preferences: Mapped["UserPreference | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    career_profile: Mapped["CareerProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    applications: Mapped[list["JobApplication"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    interviews: Mapped[list["InterviewLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(username={self.username!r}, email={self.email!r})>"


class UserPreference(Base):
    """User preferences for long-term memory."""
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    preferred_template: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job_preferences_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # {"industry": "互联网", "role": "后端工程师"}
    resume_style: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "concise" | "detailed"
    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # 其他自定义偏好
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="preferences")

    def __repr__(self) -> str:
        return f"<UserPreference(user_id={self.user_id})>"


class CareerProfile(Base):
    """Long-term career profile (跨会话记忆 v3).

    持续演进的求职档案：技能/经历/偏好/缺口，由上传简历规则合并 +
    consolidate 提炼维护。
    """
    __tablename__ = "career_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    profile_json: Mapped[str] = mapped_column(Text, nullable=False)  # 长期画像
    source: Mapped[str] = mapped_column(String(32), default="resume", nullable=False)  # resume | consolidate
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="career_profile")

    def __repr__(self) -> str:
        return f"<CareerProfile(user_id={self.user_id}, source={self.source})>"


class AnalysisSession(Base):
    """Main analysis session table."""
    __tablename__ = "analysis_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(20), default="init", nullable=False)
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    jd_analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    gap_analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    render_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User | None"] = relationship(back_populates="sessions")
    resume_versions: Mapped[list["ResumeVersion"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AnalysisSession(session_id={self.session_id!r}, stage={self.stage!r})>"


class ResumeVersion(Base):
    """Resume version table for tracking resume iterations."""
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("analysis_sessions.session_id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    render_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    session: Mapped["AnalysisSession"] = relationship(back_populates="resume_versions")

    def __repr__(self) -> str:
        return f"<ResumeVersion(session_id={self.session_id!r}, version={self.version})>"


class UploadedFile(Base):
    """Uploaded file tracking table."""
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("analysis_sessions.session_id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # jd, resume, etc.
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    session: Mapped["AnalysisSession"] = relationship(back_populates="uploaded_files")

    def __repr__(self) -> str:
        return f"<UploadedFile(filename={self.filename!r}, type={self.file_type!r})>"


class JobApplication(Base):
    """Job application record (M3 长久陪伴)."""
    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    company: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    jd_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JD 快照
    status: Mapped[str] = mapped_column(String(20), default="applied", nullable=False)  # applied | interview | offer | rejected
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="applications")

    def __repr__(self) -> str:
        return f"<JobApplication(user_id={self.user_id}, title={self.job_title!r})>"


class InterviewLog(Base):
    """Interview record (M3 长久陪伴) — 真实面试与未来模拟面试统一建模。"""
    __tablename__ = "interview_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    application_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("job_applications.id"), nullable=True)
    company: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # passed | failed | pending
    questions_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # ["问题1", ...]
    weak_points_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # ["Redis 原理", ...]
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="real", nullable=False)  # real | mock（模拟面试预留）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="interviews")

    def __repr__(self) -> str:
        return f"<InterviewLog(user_id={self.user_id}, company={self.company!r}, result={self.result})>"
