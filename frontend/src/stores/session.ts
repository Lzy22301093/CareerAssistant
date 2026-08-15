import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createSession as apiCreateSession, getSession, deleteSession as apiDeleteSession } from '../api/sessions'
import type {
  SessionStage,
  JDAnalysis,
  Profile,
  GapAnalysis,
  ResumeContent,
  InterviewQuestion,
  RenderConfig,
} from '../types'

/** 聊天消息（包含系统事件） */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  eventType?: string
}

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref('')
  const stage = ref<SessionStage>('init')
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const sseController = ref<AbortController | null>(null)

  // 分析结果
  const jdAnalysis = ref<JDAnalysis | null>(null)
  const profile = ref<Profile | null>(null)
  const gapAnalysis = ref<GapAnalysis | null>(null)
  const resumeContent = ref<ResumeContent | null>(null)
  const interviewQuestions = ref<InterviewQuestion[]>([])
  const renderConfig = ref<RenderConfig | null>(null)

  // 活跃 tab（ResultPanel 用）
  const activeTab = ref('jd')

  let msgCounter = 0
  function addMessage(msg: Omit<ChatMessage, 'id'>) {
    messages.value.push({ ...msg, id: String(++msgCounter) })
  }

  async function createSession() {
    // 清理旧状态
    if (sseController.value) {
      sseController.value.abort()
      sseController.value = null
    }
    sessionId.value = ''
    stage.value = 'init'
    messages.value = []
    jdAnalysis.value = null
    profile.value = null
    gapAnalysis.value = null
    resumeContent.value = null
    interviewQuestions.value = []
    renderConfig.value = null
    activeTab.value = 'jd'
    isLoading.value = false

    const res = await apiCreateSession()
    sessionId.value = res.data.session_id
    addMessage({
      role: 'system',
      content: '会话已创建，请输入目标岗位的 JD 或上传 JD 文件。',
      timestamp: new Date().toISOString(),
    })
  }

  async function loadSession(id: string) {
    const res = await getSession(id)
    const d = res.data
    sessionId.value = d.session_id
    stage.value = d.stage
    jdAnalysis.value = d.jd_analysis || null
    profile.value = d.profile || null
    gapAnalysis.value = d.gap_analysis || null
    resumeContent.value = d.resume_content || null
    renderConfig.value = d.render_config
    interviewQuestions.value = (d.interview_questions?.questions) || []
    messages.value = d.messages.map((m, i) => ({
      id: String(i),
      role: m.role as 'user' | 'assistant' | 'system',
      content: m.content,
      timestamp: m.timestamp,
    }))
    msgCounter = d.messages.length
    autoSelectTab()
  }

  function handleSSEEvent(event: string, data: Record<string, unknown>) {
    switch (event) {
      case 'progress':
        // 流式进度：只保留一行"当前进度"，替换上一条 progress 消息避免刷屏
        addProgressMessage((data as Record<string, unknown>).message as string || '处理中…')
        break
      case 'jd_analysis':
        jdAnalysis.value = data as unknown as JDAnalysis
        activeTab.value = 'jd'
        addMessage({
          role: 'system',
          content: `✅ JD 分析完成：${(data as Record<string, unknown>).job_title || '未知职位'}`,
          timestamp: new Date().toISOString(),
          eventType: 'jd_analysis',
        })
        break
      case 'profile':
        profile.value = data as unknown as Profile
        activeTab.value = 'profile'
        addMessage({
          role: 'system',
          content: `✅ 个人画像提取完成：${(data as Record<string, unknown>).name || ''}`,
          timestamp: new Date().toISOString(),
          eventType: 'profile',
        })
        break
      case 'gap_analysis':
        gapAnalysis.value = data as unknown as GapAnalysis
        activeTab.value = 'gap'
        addMessage({
          role: 'system',
          content: `✅ Gap 分析完成，匹配度 ${(data as Record<string, unknown>).overall_score || 0}%`,
          timestamp: new Date().toISOString(),
          eventType: 'gap_analysis',
        })
        break
      case 'resume_content':
        resumeContent.value = data as unknown as ResumeContent
        activeTab.value = 'resume'
        addMessage({
          role: 'system',
          content: '✅ 简历内容已生成',
          timestamp: new Date().toISOString(),
          eventType: 'resume_content',
        })
        break
      case 'interview_questions':
        interviewQuestions.value = ((data as Record<string, unknown>).questions as InterviewQuestion[]) || []
        activeTab.value = 'interview'
        addMessage({
          role: 'system',
          content: `✅ 生成了 ${interviewQuestions.value.length} 道面试题`,
          timestamp: new Date().toISOString(),
          eventType: 'interview_questions',
        })
        break
      case 'render_config':
        renderConfig.value = data as unknown as RenderConfig
        break
      case 'clarification':
        addMessage({
          role: 'assistant',
          content: ((data as Record<string, unknown>).question || (data as Record<string, unknown>).content) as string || '请提供更多信息',
          timestamp: new Date().toISOString(),
          eventType: 'clarification',
        })
        break
      case 'done':
        stage.value = ((data as Record<string, unknown>).stage as SessionStage) || stage.value
        addMessage({
          role: 'system',
          content: (data as Record<string, unknown>).message as string || '处理完成',
          timestamp: new Date().toISOString(),
          eventType: 'done',
        })
        isLoading.value = false
        autoSelectTab()
        break
      case 'error':
        addMessage({
          role: 'system',
          content: `❌ ${(data as Record<string, unknown>).detail || '未知错误'}`,
          timestamp: new Date().toISOString(),
          eventType: 'error',
        })
        isLoading.value = false
        break
      case 'route':
        // 路由事件，显示 agent 路由信息
        addMessage({
          role: 'system',
          content: `🔀 ${(data as Record<string, unknown>).reason || '正在处理...'}`,
          timestamp: new Date().toISOString(),
          eventType: 'route',
        })
        break
      case 'message':
        addMessage({
          role: ((data as Record<string, unknown>).role as 'user' | 'assistant') || 'assistant',
          content: (data as Record<string, unknown>).content as string || '',
          timestamp: new Date().toISOString(),
        })
        break
      default:
        // 其他事件作为系统消息显示
        addMessage({
          role: 'system',
          content: `[${event}] ${JSON.stringify(data)}`,
          timestamp: new Date().toISOString(),
          eventType: event,
        })
    }
  }

  function autoSelectTab() {
    // 选择最靠后（最完整）的有数据的 tab
    if (interviewQuestions.value.length > 0) {
      activeTab.value = 'interview'
    } else if (resumeContent.value) {
      activeTab.value = 'resume'
    } else if (gapAnalysis.value) {
      activeTab.value = 'gap'
    } else if (profile.value) {
      activeTab.value = 'profile'
    } else if (jdAnalysis.value) {
      activeTab.value = 'jd'
    }
  }

  function addProgressMessage(content: string) {
    const last = messages.value[messages.value.length - 1]
    if (last && last.eventType === 'progress') {
      last.content = content
    } else {
      addMessage({
        role: 'system',
        content,
        timestamp: new Date().toISOString(),
        eventType: 'progress',
      })
    }
  }

  async function deleteSession(id?: string) {
    const targetId = id || sessionId.value
    if (targetId) {
      await apiDeleteSession(targetId)
    }
  }

  function abortSSE() {
    if (sseController.value) {
      sseController.value.abort()
      sseController.value = null
    }
    isLoading.value = false
  }

  return {
    sessionId,
    stage,
    messages,
    isLoading,
    sseController,
    jdAnalysis,
    profile,
    gapAnalysis,
    resumeContent,
    interviewQuestions,
    renderConfig,
    activeTab,
    createSession,
    loadSession,
    handleSSEEvent,
    deleteSession,
    abortSSE,
    addMessage,
  }
})
