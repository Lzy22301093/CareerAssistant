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

/** localStorage key for persisting the current session ID */
const SESSION_ID_KEY = 'current_session_id'

/** 聊天消息（包含系统事件） */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  eventType?: string
}

function formatInterviewReport(data: Record<string, unknown>): string {
  const lines: string[] = ['📊 **面试评估报告**\n']
  const overall = data.overall_assessment as Record<string, unknown> | undefined
  if (overall) {
    lines.push(`综合评分：**${overall.total_score || 0}/100**`)
    lines.push(`等级：${overall.grade || '-'}`)
    if (overall.strengths) lines.push(`\n**优势：** ${(overall.strengths as string[])?.join('、')}`)
    if (overall.weaknesses) lines.push(`**不足：** ${(overall.weaknesses as string[])?.join('、')}`)
    if (overall.suggestion) lines.push(`\n💡 ${overall.suggestion}`)
  }
  return lines.join('\n')
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
  const coverLetter = ref<Record<string, unknown> | null>(null)
  const lastAnswer = ref('')

  // 模拟面试状态
  const interviewActive = ref(false)
  const interviewWsUrl = ref('')

  // AI 语音对话状态
  const voiceChatActive = ref(false)
  const voiceChatWsUrl = ref('')

  // 调试数据
  const triggeredAgents = ref<string[]>([])

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
    coverLetter.value = null
    lastAnswer.value = ''
    interviewActive.value = false
    interviewWsUrl.value = ''
    voiceChatActive.value = false
    voiceChatWsUrl.value = ''
    triggeredAgents.value = []
    activeTab.value = 'jd'
    isLoading.value = false

    const res = await apiCreateSession()
    sessionId.value = res.data.session_id
    // 持久化 session ID，刷新后可恢复
    localStorage.setItem(SESSION_ID_KEY, res.data.session_id)
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
    renderConfig.value = d.render_config || null

    // 兼容多种数据结构：数组 或 { questions: [...] }
    const iq = d.interview_questions
    interviewQuestions.value = Array.isArray(iq) ? iq : (iq?.questions || [])

    messages.value = (d.messages || []).map((m, i) => ({
      id: String(i),
      role: m.role as 'user' | 'assistant' | 'system',
      content: m.content,
      timestamp: m.timestamp,
    }))
    msgCounter = (d.messages || []).length

    // 持久化 session ID，刷新后可恢复
    localStorage.setItem(SESSION_ID_KEY, id)

    // 同时更新历史列表
    const savedIds: string[] = JSON.parse(localStorage.getItem('session_ids') || '[]')
    if (!savedIds.includes(id)) {
      savedIds.unshift(id)
      localStorage.setItem('session_ids', JSON.stringify(savedIds))
    }

    autoSelectTab()
  }

  function handleSSEEvent(event: string, data: Record<string, unknown>) {
    switch (event) {
      case 'progress':
        // 流式进度：只保留一行"当前进度"，替换上一条 progress 消息避免刷屏
        addProgressMessage((data as Record<string, unknown>).message as string || '处理中…')
        break
      case 'intent': {
        // v3：展示意图识别与执行计划
        const intentData = data as Record<string, unknown>
        const plan = (intentData.plan as unknown[]) || []
        addMessage({
          role: 'system',
          content: `🎯 识别到意图：${intentData.intent}${plan.length ? `，计划：${plan.join(' → ')}` : ''}`,
          timestamp: new Date().toISOString(),
          eventType: 'intent',
        })
        break
      }
      case 'trace':
        // 节点执行轨迹（轻量展示，避免刷屏：仅失败节点）
        if ((data as Record<string, unknown>).status === 'failed') {
          addMessage({
            role: 'system',
            content: `⚠️ 步骤 ${(data as Record<string, unknown>).node} 失败：${(data as Record<string, unknown>).error || '未知错误'}`,
            timestamp: new Date().toISOString(),
            eventType: 'trace',
          })
        }
        break
      case 'review_plan': {
        // M3：基于历史失分点的针对性复习清单
        const plan = data as Record<string, unknown>
        const items = (plan.items as { topic: string; reason: string; suggestion: string }[]) || []
        if (!items.length) break
        const lines = items.map((it, i) => `${i + 1}. **${it.topic}**：${it.suggestion}`)
        addMessage({
          role: 'assistant',
          content: `📌 结合你上次面试的失分点，为你准备了针对性复习清单：\n${lines.join('\n')}`,
          timestamp: new Date().toISOString(),
          eventType: 'review_plan',
        })
        break
      }
      case 'answer':
        lastAnswer.value = (data as Record<string, unknown>).answer as string || ''
        addMessage({
          role: 'assistant',
          content: lastAnswer.value,
          timestamp: new Date().toISOString(),
          eventType: 'answer',
        })
        break
      case 'cover_letter':
        coverLetter.value = data as Record<string, unknown>
        {
          const cl = data as Record<string, unknown>
          const body = (cl.body as string) || ''
          const subject = (cl.subject as string) ? `主题：${cl.subject}\n\n` : ''
          addMessage({
            role: 'assistant',
            content: subject + body,
            timestamp: new Date().toISOString(),
            eventType: 'cover_letter',
          })
        }
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
      case 'done':
        stage.value = ((data as Record<string, unknown>).stage as SessionStage) || stage.value
        // 更新 triggered_agents（调试 Tab 用）
        const doneData = data as Record<string, unknown>
        if (doneData.triggered_agents) {
          triggeredAgents.value = doneData.triggered_agents as string[]
        }
        addMessage({
          role: 'system',
          content: doneData.message as string || '处理完成',
          timestamp: new Date().toISOString(),
          eventType: 'done',
        })
        isLoading.value = false
        autoSelectTab()
        break
      case 'error': {
        const errData = data as Record<string, unknown>
        const detail = (errData.detail as string) || ''
        const hint = (errData.hint as string) || ''
        addMessage({
          role: 'system',
          content: `❌ ${detail || hint || '未知错误'}`,
          timestamp: new Date().toISOString(),
          eventType: 'error',
        })
        isLoading.value = false
        break
      }
      case 'route':
        // 路由事件，显示 agent 路由信息
        addMessage({
          role: 'system',
          content: `🔀 ${(data as Record<string, unknown>).reason || '正在处理...'}`,
          timestamp: new Date().toISOString(),
          eventType: 'route',
        })
        break
      case 'interview_started': {
        // 模拟面试启动（前端收到后连接 WS 并发送 START）
        interviewActive.value = true
        interviewWsUrl.value = (data as Record<string, unknown>).ws_url as string || '/ws/interview'
        addMessage({
          role: 'system',
          content: `🎤 模拟面试已启动`,
          timestamp: new Date().toISOString(),
          eventType: 'interview_started',
        })
        isLoading.value = false
        break
      }
      case 'interview_ended':
        // 模拟面试结束
        interviewActive.value = false
        addMessage({
          role: 'system',
          content: `✅ 模拟面试结束`,
          timestamp: new Date().toISOString(),
          eventType: 'interview_ended',
        })
        break
      case 'interview_answer':
        // 面试官追问（文字模式）
        addMessage({
          role: 'assistant',
          content: (data as Record<string, unknown>).content as string || '',
          timestamp: new Date().toISOString(),
          eventType: 'interview_answer',
        })
        break
      case 'interview_report':
        // 面试报告
        addMessage({
          role: 'assistant',
          content: formatInterviewReport(data as Record<string, unknown>),
          timestamp: new Date().toISOString(),
          eventType: 'interview_report',
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
      // 如果删除的是当前会话，清除 localStorage
      if (targetId === sessionId.value) {
        localStorage.removeItem(SESSION_ID_KEY)
        sessionId.value = ''
        stage.value = 'init'
        messages.value = []
        jdAnalysis.value = null
        profile.value = null
        gapAnalysis.value = null
        resumeContent.value = null
        interviewQuestions.value = []
        renderConfig.value = null
      }
      // 从历史列表中移除
      const savedIds: string[] = JSON.parse(localStorage.getItem('session_ids') || '[]')
      const updated = savedIds.filter(i => i !== targetId)
      localStorage.setItem('session_ids', JSON.stringify(updated))
    }
  }

  /**
   * 恢复上次的会话（页面刷新时调用）。
   * 如果 localStorage 中有 session ID 且后端仍有该会话，则加载它。
   */
  async function restoreSession(): Promise<boolean> {
    const savedId = localStorage.getItem(SESSION_ID_KEY)
    if (!savedId) return false

    try {
      await loadSession(savedId)
      return true
    } catch {
      // 会话已过期或不存在，清除无效 ID
      localStorage.removeItem(SESSION_ID_KEY)
      return false
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
    coverLetter,
    lastAnswer,
    activeTab,
    interviewActive,
    interviewWsUrl,
    voiceChatActive,
    voiceChatWsUrl,
    triggeredAgents,
    createSession,
    loadSession,
    restoreSession,
    handleSSEEvent,
    deleteSession,
    abortSSE,
    addMessage,
  }
})
