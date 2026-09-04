/** 后端 schema 镜像的 TypeScript 类型定义 */

// === 枚举 ===

export type SessionStage = 'init' | 'has_jd' | 'has_resume' | 'has_jd_and_resume' | 'completed'

// === JD 分析 ===

export interface JDRequirement {
  category: string
  content: string
  importance: 'high' | 'medium' | 'low'
}

export interface JDAnalysis {
  job_title: string
  company: string
  requirements: JDRequirement[]
  nice_to_have: string[]
  salary_range?: string
  location?: string
  summary: string
}

// === 个人画像 ===

export interface Experience {
  company: string
  title: string
  duration: string
  highlights: string[]
}

export interface Project {
  name: string
  description: string
  tech_stack: string[]
  highlights: string[]
}

export interface Profile {
  name: string
  email?: string
  phone?: string
  education: Record<string, unknown>[]
  experience: Experience[]
  projects: Project[]
  skills: string[]
  certifications: string[]
  summary: string
}

// === Gap 分析 ===

export interface GapItem {
  category: string
  requirement: string
  current_level: string
  gap_severity: 'critical' | 'major' | 'minor'
  suggestion: string
}

export interface GapAnalysis {
  overall_score: number
  gaps: GapItem[]
  strengths: string[]
  recommendations: string[]
}

// === 简历内容 ===

export interface ResumeSection {
  title: string
  content: string
}

export interface ResumeContent {
  sections: ResumeSection[]
  raw_text: string
}

// === 渲染配置 ===

export interface RenderConfig {
  template: string
  font_size: number
  margin_top: number
  margin_bottom: number
  margin_left: number
  margin_right: number
  line_spacing: number
  accent_color: string
}

// === 面试 ===

export interface InterviewQuestion {
  question: string
  category: string
  difficulty: 'easy' | 'medium' | 'hard'
  answer_points: string[]
  sample_answer: string
}

// === 消息 ===

export interface MessageResponse {
  role: string
  content: string
  timestamp: string
}

// === 会话 ===

export interface SessionCreateResponse {
  session_id: string
  created_at: string
}

export interface SessionDetail {
  session_id: string
  stage: SessionStage
  jd_analysis?: JDAnalysis
  profile?: Profile
  gap_analysis?: GapAnalysis
  resume_content?: ResumeContent
  render_config: RenderConfig
  interview_questions?: { questions: InterviewQuestion[] }
  messages: MessageResponse[]
  created_at: string
  updated_at: string
}

export interface SessionStatus {
  session_id: string
  stage: SessionStage
  has_jd: boolean
  has_profile: boolean
  has_gap_analysis: boolean
  has_resume_content: boolean
  message_count: number
  file_count: number
}

/** 历史会话列表项（GET /sessions/ 返回的摘要） */
export interface SessionListItem {
  session_id: string
  stage: SessionStage
  message_count: number
  updated_at: string
}

// === API 请求 ===

export interface MessageRequest {
  content: string
  role?: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: Userinfo
}

export interface Userinfo {
  id: number
  username: string
  email: string
  is_active: boolean
}

export interface PreferenceUpdateRequest {
  preferred_template?: string
  resume_style?: string
  job_preferences?: Record<string, unknown>
  extra?: Record<string, unknown>
}

export interface UserPreferences {
  preferred_template: string
  resume_style: string
  job_preferences: Record<string, unknown>
  extra: Record<string, unknown>
}

// === 个人画像 / 知识库（阶段0 指令0-3） ===

export type ProfileCategory =
  | 'basic_info'
  | 'education'
  | 'experience'
  | 'skill'
  | 'target'
  | 'soft'
  | 'interview_feedback'

export type ProfileItemType = 'fact' | 'suggestion' | 'feedback'

export type ProfileVisibility = 'resume' | 'interview' | 'resume_interview' | 'private'

export type ProfileStatus = 'confirmed' | 'suggested' | 'rejected' | 'archived'

export interface ProfileEvidence {
  id: number
  source_type: string
  source_id?: string
  quote?: string
  verified_by_user: boolean
  created_at: string
}

export interface ProfileItem {
  id: number
  category: ProfileCategory
  title: string
  content?: string
  item_type: ProfileItemType
  confidence: number
  visibility: ProfileVisibility
  status: ProfileStatus
  sort_order: number
  evidences: ProfileEvidence[]
  created_at: string
  updated_at: string
}

export interface ProfileItemCreate {
  category: ProfileCategory
  title: string
  content?: string
  item_type?: ProfileItemType
  confidence?: number
  visibility?: ProfileVisibility
  status?: ProfileStatus
}

export interface ProfileItemUpdate {
  category?: ProfileCategory
  title?: string
  content?: string
  item_type?: ProfileItemType
  confidence?: number
  visibility?: ProfileVisibility
  status?: ProfileStatus
  sort_order?: number
}

export interface CategorySummary {
  category: ProfileCategory
  count: number
  confirmed: number
  suggested: number
}

export interface ProfileUpdateProposal {
  id: number
  report_id?: string
  change_type: string
  target_profile_item_id?: number
  before_value?: string
  after_value?: string
  reason?: string
  status: string
  created_at: string
}

// === 模拟面试（文字版，阶段1 指令1-3） ===

export interface InterviewStartParams {
  jd_analysis: Record<string, unknown>
  profile: Record<string, unknown>
  referenced_questions?: string[]
  max_turns?: number
}

export interface InterviewStartResponse {
  interview_id: string
  question: string
}

export interface InterviewAnswerResponse {
  question?: string | null
  is_complete: boolean
  report?: Record<string, unknown> | null
}

export interface InterviewState {
  interview_id: string
  is_active: boolean
  is_complete: boolean
  turn_count: number
  phase: string
  current_question: string
  dimension_scores: Record<string, number>
  difficulty_level: string
}

// === 文件上传 ===

export interface UploadedFile {
  filename: string
  saved_name: string
  file_path: string
  file_type: string
  file_size: number
  uploaded_at: string
}

export interface UploadResponse {
  message: string
  file: UploadedFile
  hint: string
}

// === SSE 事件 ===

export interface SSEMessageEvent {
  type: 'message'
  data: { content: string; role: string }
}

export interface SSEAnalysisEvent {
  type: 'jd_analysis' | 'profile' | 'gap_analysis' | 'resume_content' | 'interview_questions' | 'render_config'
  data: Record<string, unknown>
}

export interface SSEClarificationEvent {
  type: 'clarification'
  data: { content: string; ready_to_proceed?: boolean; next_action?: string }
}

export interface SSEDoneEvent {
  type: 'done'
  data: { stage: string; message: string }
}

export interface SSEErrorEvent {
  type: 'error'
  data: { detail: string }
}

export type SSEEvent =
  | SSEMessageEvent
  | SSEAnalysisEvent
  | SSEClarificationEvent
  | SSEDoneEvent
  | SSEErrorEvent
