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


class EvaluationDecision(BaseModel):
    """Evaluator Agent 输出结构。"""
    score: float = Field(..., ge=0, le=10)
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    feedback: str = Field(default="")
    next_action: str = Field(..., description="追问/切换话题/提高难度/降低难度/结束面试")
    reason: str = Field(default="")
    follow_up_question: str | None = None
    next_topic: str | None = None
    next_question: str | None = None
    new_difficulty: str | None = None


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


# === 个人画像 / 知识库（阶段0 指令0-3） ===

class ProfileEvidenceOut(BaseModel):
    """画像条目证据输出。"""
    id: int
    source_type: str
    source_id: str | None = None
    quote: str | None = None
    verified_by_user: bool = False
    created_at: datetime


class ProfileItemCreate(BaseModel):
    """新建画像条目。"""
    category: str = Field(..., description="分类")
    title: str = Field(..., description="标题")
    content: str | None = None
    item_type: str = Field(default="fact", description="fact | suggestion | feedback")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    visibility: str = Field(default="resume_interview", description="resume | interview | resume_interview | private")
    status: str = Field(default="confirmed", description="confirmed | suggested | rejected | archived")


class ProfileItemUpdate(BaseModel):
    """更新画像条目（部分字段）。"""
    category: str | None = None
    title: str | None = None
    content: str | None = None
    item_type: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    visibility: str | None = None
    status: str | None = None
    sort_order: int | None = None


class ProfileItemOut(BaseModel):
    """画像条目输出（含证据）。"""
    id: int
    category: str
    title: str
    content: str | None = None
    item_type: str
    confidence: float
    visibility: str
    status: str
    sort_order: int
    evidences: list[ProfileEvidenceOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EvidenceCreate(BaseModel):
    """为画像条目新增证据。"""
    source_type: str = Field(..., description="user_input | resume | interview_report")
    source_id: str | None = None
    quote: str | None = None
    verified_by_user: bool = False


class StatusChange(BaseModel):
    """切换画像条目状态。"""
    status: str = Field(..., description="confirmed | suggested | rejected | archived")


# === 结构化画像表单（知识库 分阶段向导，阶段3） ===

class ProfileEducationEntry(BaseModel):
    """一条教育经历（结构化）。"""
    school: str = ""
    degree: str = ""
    major: str = ""
    courses: str = ""
    start: str = ""
    end: str = ""
    gpa: str = ""


class ProfileSocialEntry(BaseModel):
    """一条社交账号（结构化）。"""
    platform: str = ""
    account: str = ""


class ProfileExtraEntry(BaseModel):
    """其他分类的纯文本条目（experience/skill/target/soft/interview_feedback 兜底）。"""
    category: str = Field(..., description="experience | skill | target | soft | interview_feedback")
    title: str = ""
    content: str = ""


class ProfileFormSave(BaseModel):
    """保存知识库分阶段向导（基本信息/教育经历/个人奖项/社交账号）。"""
    basic_info: dict[str, str] = Field(default_factory=dict, description="固定字段键值；键取自 BASIC_INFO_FIELDS")
    education: list[ProfileEducationEntry] = Field(default_factory=list)
    awards: str = Field(default="", description="个人奖项（多行，每行一条）")
    social: list[ProfileSocialEntry] = Field(default_factory=list)
    extra: list[ProfileExtraEntry] = Field(default_factory=list, description="其他分类兜底")


class ProfileFormOut(BaseModel):
    """知识库分阶段向导的已保存数据（供前端回显/继续编辑）。"""
    basic_info: dict[str, str] = Field(default_factory=dict)
    education: list[ProfileEducationEntry] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)
    social: list[ProfileSocialEntry] = Field(default_factory=list)
    extra: list[ProfileExtraEntry] = Field(default_factory=list)


# === 画像更新提案（阶段1 指令1-2） ===

class ProfileUpdateProposalOut(BaseModel):
    """画像更新提案输出。"""
    id: int
    report_id: str | None = None
    change_type: str
    target_profile_item_id: int | None = None
    before_value: str | None = None
    after_value: str | None = None
    reason: str | None = None
    status: str
    created_at: datetime


class ProposalAction(BaseModel):
    """确认提案操作。"""
    action: str = Field(..., description="accept | reject | defer")
    after_value: str | None = Field(default=None, description="修改后采纳的自定义值（可选）")


# === 简历库资产（阶段2 指令2-1） ===

class ResumeDocumentCreate(BaseModel):
    """新建简历库文档。"""
    title: str = Field(..., min_length=1, max_length=200, description="简历名称")
    source: str = Field(default="manual", description="manual | session | upload")
    notes: str | None = None


class ResumeDocumentUpdate(BaseModel):
    """更新简历库文档（部分字段）。"""
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = None


class ResumeVersionCreate(BaseModel):
    """为文档新增一版简历内容。"""
    content: dict = Field(..., description='简历内容 {"sections": [{"title","content"}], "raw_text": str}')
    render_config: dict | None = None
    page_preference: str = Field(default="one_page", description="one_page | two_pages（页数偏好，阶段3 3-2）")


class VersionPagePreferenceRequest(BaseModel):
    """更新简历版本页数偏好（阶段3 3-2 多页数导出）。"""
    page_preference: str = Field(..., description="one_page | two_pages")


class ResumeSectionUpdate(BaseModel):
    """更新简历区域（部分字段，供区域改写/定位用）。"""
    title: str | None = None
    content: str | None = None
    section_type: str | None = Field(default=None, description="header|summary|education|experience|project|skill|certification|custom")
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: dict | None = Field(default=None, description='{"x","y","width","height","page"}')
    sort_order: int | None = None


class ResumeSectionOut(BaseModel):
    """简历区域输出。"""
    id: int
    resume_version_id: int
    page_number: int
    section_type: str
    title: str | None = None
    content: str | None = None
    bounding_box: dict | None = None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ResumeVersionOut(BaseModel):
    """简历版本输出（含区域）。"""
    id: int
    document_id: int | None = None
    session_id: str | None = None
    version: int
    content: dict | None = None
    render_config: dict | None = None
    sections: list[ResumeSectionOut] = Field(default_factory=list)
    is_current: bool = False
    created_at: datetime


class ResumeDocumentOut(BaseModel):
    """简历库文档输出。"""
    id: int
    title: str
    source: str
    current_version_id: int | None = None
    version_count: int = 0
    deleted_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ResumeDocumentDetailOut(ResumeDocumentOut):
    """简历库文档详情（含版本列表与当前版本内容）。"""
    versions: list[ResumeVersionOut] = Field(default_factory=list)
    current_version: ResumeVersionOut | None = None


class SessionImportRequest(BaseModel):
    """从聊天会话导入简历到简历库。"""
    session_id: str = Field(..., min_length=1, description="分析会话 ID")


class SectionRewriteRequest(BaseModel):
    """区域改写请求（阶段2 指令2-2）。"""
    instruction: str = Field(default="", description="用户改写指令（空则用默认：优化表达与量化）")
    conversation_history: list[dict] = Field(default_factory=list, description="区域对话历史 [{role, content}]，最多取最近 8 条")
    jd_analysis: dict | None = Field(default=None, description="目标岗位分析（可选）")


class SectionAdoptRequest(BaseModel):
    """采纳区域改写：以替换后的内容生成新版本。"""
    section_id: int = Field(..., description="被改写的区域 ID")
    rewrite: str = Field(..., min_length=1, description="采纳的改写文本")


# === 岗位匹配任务（阶段2 指令2-4） ===

class JobPostingCreate(BaseModel):
    """新建岗位 JD 资产。"""
    company: str = Field(..., min_length=1, max_length=100, description="公司名称")
    title: str = Field(..., min_length=1, max_length=100, description="岗位名称")
    jd_text: str = Field(..., min_length=1, description="JD 原文")
    jd_image: str | None = None
    source: str = Field(default="manual", description="manual | upload | scrape")


class JobPostingOut(BaseModel):
    """岗位资产输出。"""
    id: int
    company: str | None = None
    title: str | None = None
    jd_text: str | None = None
    source: str
    task_count: int = 0
    created_at: datetime
    updated_at: datetime


class MatchTaskCreate(BaseModel):
    """新建匹配任务。"""
    job_posting_id: int = Field(..., description="岗位资产 ID")
    resume_version_id: int | None = Field(default=None, description="所用简历版本（可选，缺省用已确认画像）")
    page_preference: str = Field(default="one_page", description="one_page | two_pages")


class MatchTaskOut(BaseModel):
    """匹配任务输出。"""
    id: int
    job_posting_id: int | None = None
    company: str | None = None
    posting_title: str | None = None
    resume_version_id: int | None = None
    page_preference: str
    score: int | None = None
    stage: str
    summary: dict | None = None
    created_at: datetime
    updated_at: datetime


class MatchRunRequest(BaseModel):
    """执行匹配分析。"""
    with_draft: bool = Field(default=True, description="是否生成定向简历草稿")


# === 简历生成区（8 步向导后端） ===

class ResumeDraftSave(BaseModel):
    """保存生成向导草稿（暂存退出）。"""
    step: int = Field(ge=1, le=8, description="当前步骤 01-08")
    data: dict = Field(default_factory=dict, description="向导数据快照")


class ResumeDraftOut(BaseModel):
    """生成向导草稿输出。"""
    step: int | None = None
    data: dict = Field(default_factory=dict)
    updated_at: datetime | None = None


class WizardExperienceCreate(BaseModel):
    """向导单条经历（03 经历补充）。"""
    exp_type: str = Field(default="项目", description="项目 | 实习 | 竞赛 | 课程 | 校园")
    company: str | None = None      # 公司/项目/机构
    title: str | None = None        # 角色/名称
    duration: str | None = None
    duty: str | None = None         # 职责（做了什么）
    achievement: str | None = None  # 成果/收获


class StarResultItem(BaseModel):
    """单条经历的 STAR 结构化结果（04 STAR 结构化）。"""
    exp_type: str = "项目"
    company: str | None = None
    title: str | None = None
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""


class StarBatch(BaseModel):
    """LLM 结构化输出：多条经历的 STAR 结果。"""
    items: list[StarResultItem] = Field(default_factory=list)


class StarRequest(BaseModel):
    """STAR 结构化请求。"""
    experiences: list[WizardExperienceCreate] = Field(default_factory=list)


class StarResponse(BaseModel):
    """STAR 结构化响应。"""
    items: list[StarResultItem] = Field(default_factory=list)


class WizardGenerateRequest(BaseModel):
    """08 生成与导出：从向导数据组装简历。"""
    title: str = Field(default="我的新简历", max_length=200, description="生成简历的标题")
    basic_info: dict = Field(default_factory=dict, description="01 基础信息 {name,email,phone,location,...}")
    directions: list[str] = Field(default_factory=list, description="02 选中的方向（1-3）")
    experiences: list[StarResultItem] = Field(default_factory=list, description="03/04 经历（已 STAR 化）")
    soft_info: dict = Field(default_factory=dict, description="05 {personality,vision,disinterested,self_eval}")
    photo_id: int | None = Field(default=None, description="06 证件照（resume_photos.id）")
    module_order: list[str] = Field(default_factory=list, description="07 模块标题顺序（缺省用默认顺序）")
    page_preference: str = Field(default="one_page", description="one_page | two_pages")
    polish: bool = Field(default=True, description="是否 AI 润色")
    import_to_library: bool = Field(default=True, description="生成后是否直接导入简历库")


class ImportGeneratedRequest(BaseModel):
    """把结构化简历内容导入简历库（生成区产物 / 外部内容）。"""
    title: str = Field(..., max_length=200)
    content: dict = Field(..., description='ResumeContent {"sections":[{"title","content"}],"raw_text":str}')
    page_preference: str = Field(default="one_page", description="one_page | two_pages")


class ResumeExportRequest(BaseModel):
    """导出简历（生成区/库内版本内容）。"""
    title: str = Field(default="我的简历", max_length=200, description="导出文件名（不含扩展名）")
    content: dict = Field(..., description='ResumeContent {"sections":[{"title","content"}],"raw_text":str}')
    format: str = Field(default="docx", description="docx | html | md | json")


class PhotoOut(BaseModel):
    """证件照输出。"""
    id: int
    filename: str
    url: str
    created_at: datetime


# === 投递记录（阶段3 指令3-3） ===

class JobApplicationCreate(BaseModel):
    """新增投递记录。"""
    company: str = Field(..., min_length=1, max_length=100, description="公司")
    job_title: str = Field(..., min_length=1, max_length=100, description="岗位")
    status: str = Field(default="applied", description="applied | written_test | interview | offer | rejected")
    notes: str | None = None
    applied_at: datetime | None = Field(default=None, description="投递时间，缺省用当前时间")


class JobApplicationUpdate(BaseModel):
    """更新投递记录（部分字段）。"""
    company: str | None = Field(default=None, max_length=100)
    job_title: str | None = Field(default=None, max_length=100)
    status: str | None = None
    notes: str | None = None


class JobApplicationOut(BaseModel):
    """投递记录输出。"""
    id: int
    company: str | None = None
    job_title: str | None = None
    status: str
    result: str  # ongoing | passed | failed（由 status 推导）
    notes: str | None = None
    applied_at: datetime
    created_at: datetime


# === 画像方向推荐（阶段3 指令3-1） ===

class DirectionCandidate(BaseModel):
    """单个岗位方向候选（LLM 结构化输出 + API 请求/响应复用）。"""
    title: str = Field(..., description="岗位方向名称，如：后端开发工程师")
    reason: str = Field(..., description="推荐理由（为何适合该方向）")
    detail: str = Field(default="", description="方向详情/匹配点说明（对应参考图「查看详情」）")


class DirectionRecommendation(BaseModel):
    """画像方向推荐结果（LLM 结构化输出）。"""
    directions: list[DirectionCandidate] = Field(..., description="候选方向列表（3~8 条）")


class DirectionConfirmRequest(BaseModel):
    """保存用户选中的方向（1~3 个）。"""
    selected: list[DirectionCandidate] = Field(..., description="选中的方向候选（最多 3 个）")


# === 软性信息（阶段3 指令3-2） ===

class SoftInfoSuggestion(BaseModel):
    """软性信息建议（LLM 结构化输出 + AI 生成）。"""
    personality: str = Field(default="", description="性格特点")
    vision: str = Field(default="", description="职业愿景")
    disinterested: str = Field(default="", description="不感兴趣的方向")
    self_eval: str = Field(default="", description="自我评价")


class SoftInfoSaveRequest(BaseModel):
    """保存软性信息为画像条目。"""
    personality: str = Field(default="", description="性格特点")
    vision: str = Field(default="", description="职业愿景")
    disinterested: str = Field(default="", description="不感兴趣的方向")
    self_eval: str = Field(default="", description="自我评价")
