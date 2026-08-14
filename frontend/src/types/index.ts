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
