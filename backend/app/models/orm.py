"""SQLAlchemy ORM models for database persistence."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
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
    interview_reports: Mapped[list["InterviewReport"]] = relationship(cascade="all, delete-orphan")
    profile_items: Mapped[list["ProfileItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    job_postings: Mapped[list["JobPosting"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    match_tasks: Mapped[list["MatchTask"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    profile_update_proposals: Mapped[list["ProfileUpdateProposal"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    resume_documents: Mapped[list["ResumeDocument"]] = relationship(back_populates="user", cascade="all, delete-orphan")

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


class ResumeDocument(Base):
    """简历库文档（阶段2 指令2-1）—— 用户级简历资产，下挂多版本，支持回收站软删除。"""
    __tablename__ = "resume_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), default="未命名简历", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)  # manual | session | upload
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # 指向 resume_versions.id，无外键约束避免循环依赖
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 软删除 → 回收站
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="resume_documents")
    versions: Mapped[list["ResumeVersion"]] = relationship(back_populates="document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ResumeDocument(id={self.id}, title={self.title!r}, user_id={self.user_id})>"


class ResumeVersion(Base):
    """Resume version table for tracking resume iterations.

    阶段2 起一版简历既可挂在 analysis_sessions（聊天产物冷存）也可挂在
    resume_documents（简历库资产）下：session_id/document_id 至少一个非空。
    """
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("analysis_sessions.session_id"), nullable=True, index=True)
    document_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("resume_documents.id"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    render_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    session: Mapped["AnalysisSession | None"] = relationship(back_populates="resume_versions")
    document: Mapped["ResumeDocument | None"] = relationship(back_populates="versions")
    sections: Mapped[list["ResumeSection"]] = relationship(
        back_populates="resume_version", cascade="all, delete-orphan", order_by="ResumeSection.sort_order"
    )

    def __repr__(self) -> str:
        return f"<ResumeVersion(session_id={self.session_id!r}, document_id={self.document_id}, version={self.version})>"


class ResumeSection(Base):
    """简历区域（阶段2 指令2-1）—— 版本内可寻址的最小编辑单元，支持 boundingBox 定位。"""
    __tablename__ = "resume_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resume_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("resume_versions.id"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    section_type: Mapped[str] = mapped_column(String(32), default="custom", nullable=False)
    # header | summary | education | experience | project | skill | certification | custom
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    bounding_box: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON {"x","y","width","height","page"}
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    resume_version: Mapped["ResumeVersion"] = relationship(back_populates="sections")

    def __repr__(self) -> str:
        return f"<ResumeSection(version_id={self.resume_version_id}, type={self.section_type!r}, title={self.title!r})>"


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


class InterviewReport(Base):
    """模拟面试报告（AI Mock Interview）。"""
    __tablename__ = "interview_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interview_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    target_position: Mapped[str | None] = mapped_column(String(200), nullable=True)
    difficulty_level: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    dimension_scores_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    weaknesses_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_history_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    proposal_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list，关联 profile_update_proposals
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<InterviewReport(interview_id={self.interview_id!r}, position={self.target_position!r})>"


class ProfileItem(Base):
    """画像条目 —— 个人知识库的细分条目（事实/建议/反馈）。

    status: confirmed | suggested | rejected | archived
    category: basic_info | education | experience | skill | target | soft | interview_feedback
    item_type: fact | suggestion | feedback
    visibility: resume | interview | resume_interview | private
    """
    __tablename__ = "profile_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_type: Mapped[str] = mapped_column(String(32), default="fact", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), default="resume_interview", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="confirmed", nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="profile_items")
    evidences: Mapped[list["ProfileEvidence"]] = relationship(back_populates="profile_item", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ProfileItem(user_id={self.user_id}, category={self.category!r}, status={self.status!r})>"


class ProfileEvidence(Base):
    """画像条目证据 —— 支持该条画像的来源引用。

    source_type: user_input | resume | interview_report
    """
    __tablename__ = "profile_evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("profile_items.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    profile_item: Mapped["ProfileItem"] = relationship(back_populates="evidences")

    def __repr__(self) -> str:
        return f"<ProfileEvidence(profile_item_id={self.profile_item_id}, source_type={self.source_type!r})>"


class JobPosting(Base):
    """岗位 JD 资产 —— 独立于会话的一等岗位资产。"""
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    company: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    jd_image: Mapped[str | None] = mapped_column(Text, nullable=True)  # 图片文件/URL
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)  # manual | upload | scrape
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="job_postings")
    match_tasks: Mapped[list["MatchTask"]] = relationship(back_populates="job_posting", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<JobPosting(user_id={self.user_id}, company={self.company!r}, title={self.title!r})>"


class MatchTask(Base):
    """岗位匹配任务 —— 把"某个 JD + 某份简历 + 页数偏好 + 分数 + 阶段历史"绑成一个任务。"""
    __tablename__ = "match_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    job_posting_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("job_postings.id"), nullable=True, index=True)
    resume_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("resume_versions.id"), nullable=True, index=True)
    page_preference: Mapped[str] = mapped_column(String(20), default="one_page", nullable=False)  # one_page | two_pages
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100 匹配分数
    stage: Mapped[str] = mapped_column(String(32), default="created", nullable=False)  # created | analyzing | done | failed
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # 分析摘要/优势/缺口
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="match_tasks")
    job_posting: Mapped["JobPosting"] = relationship(back_populates="match_tasks")

    def __repr__(self) -> str:
        return f"<MatchTask(user_id={self.user_id}, score={self.score}, stage={self.stage!r})>"


class ProfileUpdateProposal(Base):
    """面试报告 → 画像更新提案（安全边界）。

    报告可产出建议，但只有用户采纳后才写回 ProfileItem。
    change_type: add | update | add_evidence | feedback
    status: pending | accepted | rejected | deferred
    """
    __tablename__ = "profile_update_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    report_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # 关联 interview_reports.interview_id
    target_profile_item_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("profile_items.id"), nullable=True, index=True)
    change_type: Mapped[str] = mapped_column(String(32), default="add", nullable=False)
    before_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of evidence ids/refs
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="profile_update_proposals")

    def __repr__(self) -> str:
        return f"<ProfileUpdateProposal(user_id={self.user_id}, change_type={self.change_type!r}, status={self.status!r})>"
