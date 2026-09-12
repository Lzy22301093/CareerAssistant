<template>
  <div class="vi-page">
    <AppNav>
      <el-button text @click="openHistory">历史记录</el-button>
      <el-button v-if="phase === 'conduct'" text @click="confirmEnd">结束面试</el-button>
      <el-button v-else-if="phase === 'report'" text @click="backToPrepare">再开一场</el-button>
    </AppNav>

    <main class="vi-main">
      <!-- 01 准备 -->
      <section v-if="phase === 'prepare'" class="prep-panel">
        <p class="eyebrow">语音模拟面试</p>
        <h1 class="prep-title">和面试官来一场真实对话</h1>
        <p class="prep-desc">基于你的已确认画像与目标岗位 JD，进行多轮语音面试，结束后生成反馈报告。</p>

        <div v-if="resumeHint" class="resume-banner">
          <div class="resume-text">
            <strong>检测到未完成的面试</strong>
            <span>{{ resumeHint }}</span>
          </div>
          <div class="resume-actions">
            <el-button type="primary" size="small" :loading="resuming" @click="resumeActive">
              继续面试
            </el-button>
            <el-button size="small" text @click="discardActive">丢弃</el-button>
          </div>
        </div>

        <el-form label-width="96px" class="prep-form">
          <el-form-item label="公司">
            <el-input v-model="company" placeholder="如：字节跳动（可选）" />
          </el-form-item>
          <el-form-item label="目标岗位" required>
            <el-input v-model="position" placeholder="如：后端开发实习生" />
          </el-form-item>
          <el-form-item label="岗位 JD">
            <el-input
              v-model="jdText"
              type="textarea"
              :rows="5"
              placeholder="粘贴岗位职责与要求，面试官会据此考察（可选，但强烈建议）"
            />
          </el-form-item>
          <el-form-item label="面试轮数">
            <el-input-number v-model="maxTurns" :min="3" :max="15" />
          </el-form-item>
        </el-form>

        <!-- TTS 语音偏好 -->
        <div class="tts-box">
          <div class="tts-head">
            <span class="tts-title">面试官声音</span>
            <el-button size="small" :loading="ttsPreviewing" @click="onTtsPreview">试听</el-button>
          </div>
          <el-form label-width="72px" class="tts-form">
            <el-form-item label="音色">
              <el-select v-model="ttsVoice" style="width: 220px" size="default">
                <el-option
                  v-for="v in voiceOptions"
                  :key="v.id"
                  :label="v.label"
                  :value="v.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="风格">
              <el-radio-group v-model="ttsStyle" size="small">
                <el-radio-button value="professional">专业面试官</el-radio-button>
                <el-radio-button value="casual">轻松聊天</el-radio-button>
                <el-radio-button value="concise">简洁干练</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="语速">
              <div class="tts-speed-row">
                <el-slider
                  v-model="ttsSpeed"
                  :min="0.7"
                  :max="1.6"
                  :step="0.1"
                  show-stops
                  style="flex: 1"
                />
                <span class="tts-speed-val">{{ ttsSpeed.toFixed(1) }}x</span>
              </div>
            </el-form-item>
          </el-form>
          <p class="tts-hint">试听满意后再开始面试；设置会记住，下次自动带上。</p>
        </div>

        <div v-if="profileBrief" class="profile-chip">
          已加载画像：{{ profileBrief }}
        </div>
        <div v-else class="profile-warn">
          暂未读取到已确认画像，面试仍可进行，但问题会偏通用。建议先到「个人知识库」完善。
        </div>

        <p v-if="prepError" class="err">{{ prepError }}</p>

        <div class="prep-actions">
          <el-button type="primary" size="large" :loading="preparing" @click="beginInterview">
            {{ preparing ? '正在进入面试…' : '开始语音面试' }}
          </el-button>
          <el-button text @click="goText">改用文字版</el-button>
          <el-button text @click="openHistory">查看历史</el-button>
        </div>
        <p v-if="preparing" class="prep-loading-hint">
          正在连接面试官并准备开场，进入后请等待第一题播报（约 20–40 秒）…
        </p>
      </section>

      <!-- 02 进行 -->
      <section v-else-if="phase === 'conduct'" class="conduct-panel">
        <div class="conduct-head">
          <div>
            <h2 class="conduct-title">{{ position }}</h2>
            <p class="conduct-sub">{{ company || '模拟面试' }} · 语音多轮</p>
          </div>
          <el-tag v-if="launching" type="warning" size="small" effect="light">面试官准备中</el-tag>
        </div>
        <div class="conduct-body">
          <VoiceInterviewPanel
            v-if="wsUrl"
            ref="voicePanelRef"
            :ws-url="wsUrl"
            mode="interview"
            :auto-connect="false"
            :max-turns="maxTurns"
            :start-payload="startPayload || undefined"
            @complete="onReport"
            @started="onStarted"
          />
        </div>
      </section>

      <!-- 03 报告 -->
      <section v-else class="report-panel">
        <p class="eyebrow">面试报告</p>
        <h1 class="prep-title">这一场的反馈</h1>

        <div v-if="hasReport" class="report-summary">
          <div class="score-badge">
            <div class="score-num">{{ overallScore ?? '—' }}</div>
            <div class="score-label">综合评分</div>
          </div>
          <div class="report-meta">
            <p class="meta-item">目标岗位：{{ position }}</p>
            <p v-if="turnCount" class="meta-item">回答轮数：{{ turnCount }}</p>
          </div>
        </div>
        <div v-else class="report-empty">本场暂无详细评价，可重开一场。</div>

        <div v-if="summary" class="report-block">
          <h3 class="sec">总体评价</h3>
          <p class="body-text">{{ summary }}</p>
        </div>
        <div v-if="dimensionList.length" class="report-block">
          <h3 class="sec">维度得分</h3>
          <div class="dim-list">
            <div v-for="d in dimensionList" :key="d.key" class="dim-item">
              <span class="dim-name">{{ d.key }}</span>
              <span class="dim-bar"><span class="dim-fill" :style="{ width: dimWidth(d.value) }" /></span>
              <span class="dim-score">{{ d.value }}</span>
            </div>
          </div>
        </div>
        <div v-if="strengths.length" class="report-block">
          <h3 class="sec">优势</h3>
          <ul class="body-list"><li v-for="(s, i) in strengths" :key="i">{{ s }}</li></ul>
        </div>
        <div v-if="weaknesses.length" class="report-block">
          <h3 class="sec">不足与提升</h3>
          <ul class="body-list"><li v-for="(w, i) in weaknesses" :key="i">{{ w }}</li></ul>
        </div>
        <div v-if="suggestions.length" class="report-block">
          <h3 class="sec">改进建议</h3>
          <ul class="body-list"><li v-for="(s, i) in suggestions" :key="i">{{ s }}</li></ul>
        </div>

        <div v-if="proposals.length" class="report-block">
          <div class="sec-row">
            <h3 class="sec">待确认画像更新（{{ proposals.length }}）</h3>
            <el-button size="small" text type="primary" @click="loadProposals">刷新</el-button>
          </div>
          <div v-for="p in proposals" :key="p.id" class="proposal">
            <div class="p-head">
              <el-tag size="small">{{ changeLabel(p.change_type) }}</el-tag>
              <el-tag size="small" :type="statusType(p.status)">{{ statusLabel(p.status) }}</el-tag>
            </div>
            <div class="p-val">{{ p.after_value }}</div>
            <div v-if="p.reason" class="p-reason">{{ p.reason }}</div>
            <div v-if="p.status === 'pending'" class="p-actions">
              <el-button size="small" type="success" @click="actProposal(p.id, 'accept')">采纳</el-button>
              <el-button size="small" @click="actProposal(p.id, 'defer')">稍后</el-button>
              <el-button size="small" type="danger" @click="actProposal(p.id, 'reject')">拒绝</el-button>
            </div>
          </div>
        </div>
        <div v-else-if="loadedProposals" class="empty-hint">本场暂无待确认提案</div>

        <div class="report-actions">
          <el-button type="primary" @click="backToPrepare">再开一场</el-button>
          <el-button @click="goWorkspace">去 AI 助手工作台</el-button>
        </div>
      </section>
    </main>

    <!-- 历史记录抽屉 -->
    <el-drawer v-model="historyOpen" title="面试历史记录" size="min(480px, 100%)">
      <div v-if="historyLoading" class="hist-loading">加载中…</div>
      <div v-else-if="!historyList.length" class="hist-empty">暂无已完成的面试记录</div>
      <div v-else class="hist-list">
        <button
          v-for="item in historyList"
          :key="item.interview_id"
          type="button"
          class="hist-item"
          @click="openHistoryDetail(item.interview_id)"
        >
          <div class="hist-item-top">
            <span class="hist-pos">{{ item.target_position || '未命名岗位' }}</span>
            <span v-if="item.overall_score != null" class="hist-score">{{ item.overall_score }}</span>
          </div>
          <div class="hist-item-meta">
            {{ formatTime(item.created_at) }} · {{ item.turn_count }} 轮
            <span v-if="item.completion_reason"> · {{ reasonLabel(item.completion_reason) }}</span>
          </div>
          <div v-if="item.summary" class="hist-summary">{{ item.summary }}</div>
        </button>
      </div>

      <el-divider v-if="historyDetail" />
      <div v-if="historyDetail" class="hist-detail">
        <h3 class="hist-detail-title">{{ historyDetail.target_position || '面试详情' }}</h3>
        <p class="hist-item-meta">{{ formatTime(historyDetail.created_at) }} · {{ historyDetail.turn_count }} 轮</p>

        <div v-if="historyDetail.conversation_history.length" class="hist-chat">
          <div
            v-for="(line, i) in historyDetail.conversation_history"
            :key="i"
            :class="['hist-line', line.role === 'assistant' ? 'ai' : 'user']"
          >
            <span class="hist-role">{{ line.role === 'assistant' ? '面试官' : '你' }}</span>
            <span class="hist-content">{{ line.content }}</span>
          </div>
        </div>

        <div v-if="historyDetail.final_report?.summary" class="report-block">
          <h4 class="sec">总体评价</h4>
          <p class="body-text">{{ historyDetail.final_report.summary }}</p>
        </div>
        <div v-if="historyDetail.strengths?.length" class="report-block">
          <h4 class="sec">优势</h4>
          <ul class="body-list">
            <li v-for="(s, i) in historyDetail.strengths" :key="i">{{ s }}</li>
          </ul>
        </div>
        <div v-if="historyDetail.weaknesses?.length" class="report-block">
          <h4 class="sec">不足</h4>
          <ul class="body-list">
            <li v-for="(w, i) in historyDetail.weaknesses" :key="i">{{ w }}</li>
          </ul>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppNav from '../components/AppNav.vue'
import VoiceInterviewPanel from '../components/VoiceInterviewPanel.vue'
import { listProfileItems, listProposals, actOnProposal } from '../api/profile'
import {
  getInterviewState,
  listInterviewHistory,
  getInterviewHistoryDetail,
  previewTts,
  readTtsPreviewError,
  listTtsVoices,
} from '../api/interview'
import { useAuthStore } from '../stores/auth'
import type {
  ActiveVoiceInterviewStore,
  InterviewHistoryDetail,
  InterviewHistoryItem,
  ProfileUpdateProposal,
} from '../types'

const router = useRouter()
const auth = useAuthStore()

const ACTIVE_KEY = 'mock_voice_interview_active'

type Phase = 'prepare' | 'conduct' | 'report'
const phase = ref<Phase>('prepare')

const company = ref('')
const position = ref('')
const jdText = ref('')
const maxTurns = ref(8)
const preparing = ref(false)
const prepError = ref('')
const launching = ref(true)

// TTS 用户偏好
const TTS_PREF_KEY = 'mock_interview_tts_pref'
const ttsStyle = ref<'professional' | 'casual' | 'concise' | string>('professional')
const ttsSpeed = ref(1.1)
const ttsVoice = ref('Chloe')
const ttsPreviewing = ref(false)
const voiceOptions = ref<{ id: string; label: string }[]>([
  { id: 'Chloe', label: 'Chloe · 明亮女声' },
  { id: 'Mia', label: 'Mia · 温暖女声' },
  { id: 'Milo', label: 'Milo · 阳光男声' },
  { id: 'Dean', label: 'Dean · 沉稳男声' },
])

async function loadVoices() {
  try {
    const res = await listTtsVoices()
    if (res.data?.voices?.length) {
      voiceOptions.value = res.data.voices
      if (res.data.default) {
        const has = voiceOptions.value.some((v) => v.id === ttsVoice.value)
        if (!has) ttsVoice.value = res.data.default
      }
    }
  } catch {
    /* 用本地默认列表 */
  }
}

function loadTtsPref() {
  try {
    const raw = localStorage.getItem(TTS_PREF_KEY)
    if (!raw) return
    const p = JSON.parse(raw) as { style?: string; speed?: number; voice?: string }
    if (p.style) ttsStyle.value = p.style
    if (typeof p.speed === 'number') ttsSpeed.value = p.speed
    if (p.voice) ttsVoice.value = p.voice
  } catch {
    /* ignore */
  }
}

function saveTtsPref() {
  localStorage.setItem(
    TTS_PREF_KEY,
    JSON.stringify({
      style: ttsStyle.value,
      speed: ttsSpeed.value,
      voice: ttsVoice.value,
    }),
  )
}

watch([ttsStyle, ttsSpeed, ttsVoice], saveTtsPref)

/** 试听：PCM16 24kHz mono → AudioContext 播放 */
async function onTtsPreview() {
  ttsPreviewing.value = true
  try {
    const res = await previewTts({
      text: '你好，我是今天的面试官。请简单介绍一下你自己。',
      style: ttsStyle.value,
      speed: ttsSpeed.value,
      voice: ttsVoice.value,
    })
    const buf = res.data
    if (!buf || (buf as ArrayBuffer).byteLength === 0) {
      ElMessage.error('试听失败：未返回音频')
      return
    }
    const ctx = new AudioContext({ sampleRate: 24000 })
    const pcm = new Int16Array(buf as ArrayBuffer)
    const f32 = new Float32Array(pcm.length)
    for (let i = 0; i < pcm.length; i++) f32[i] = pcm[i] / 32768
    const audio = ctx.createBuffer(1, f32.length, 24000)
    audio.getChannelData(0).set(f32)
    const src = ctx.createBufferSource()
    src.buffer = audio
    src.connect(ctx.destination)
    src.onended = () => ctx.close()
    src.start()
  } catch (e: unknown) {
    const msg = await readTtsPreviewError(e)
    ElMessage.error(msg)
  } finally {
    ttsPreviewing.value = false
  }
}

const profile = ref<Record<string, unknown>>({})
const profileBrief = ref('')

const startPayload = ref<{
  jd_analysis: Record<string, unknown>
  profile: Record<string, unknown>
  max_turns: number
  user_id?: number | null
  voice?: string
  speed?: number
  tts_style?: string
} | null>(null)

const voicePanelRef = ref<InstanceType<typeof VoiceInterviewPanel> | null>(null)
const interviewId = ref('')
const report = ref<Record<string, unknown>>({})
const proposals = ref<ProfileUpdateProposal[]>([])
const loadedProposals = ref(false)

// 历史与恢复
const historyOpen = ref(false)
const historyLoading = ref(false)
const historyList = ref<InterviewHistoryItem[]>([])
const historyDetail = ref<InterviewHistoryDetail | null>(null)
const resuming = ref(false)
const activeLocal = ref<ActiveVoiceInterviewStore | null>(null)

const resumeHint = computed(() => {
  const a = activeLocal.value
  if (!a?.interviewId) return ''
  return `${a.position || '面试'} · 已有 ${a.chatLog?.length || 0} 条对话`
})

const wsUrl = computed(() => {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws/interview`
})

const overallScore = computed(() =>
  typeof report.value.overall_score === 'number' ? report.value.overall_score : null,
)
const summary = computed(() => (typeof report.value.summary === 'string' ? report.value.summary : ''))
const suggestions = computed<string[]>(() => asArr(report.value.suggestions))
const strengths = computed<string[]>(() => asArr(report.value.strengths))
const weaknesses = computed<string[]>(() => asArr(report.value.weaknesses))
const turnCount = computed(() =>
  typeof report.value.turn_count === 'number' ? report.value.turn_count : 0,
)
const dimensionList = computed(() => {
  const ds = report.value.dimension_scores
  if (!ds || typeof ds !== 'object') return []
  return Object.entries(ds as Record<string, unknown>).map(([key, val]) => ({
    key,
    value: typeof val === 'number' ? val : Number(val) || 0,
  }))
})
const hasReport = computed(
  () =>
    overallScore.value != null ||
    !!summary.value ||
    strengths.value.length > 0 ||
    suggestions.value.length > 0,
)

function asArr(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
}

function dimWidth(v: number) {
  return `${Math.min(100, Math.max(0, (v / 10) * 100)).toFixed(1)}%`
}

function changeLabel(t: string) {
  const map: Record<string, string> = { add: '新增', update: '更新', strengthen: '强化', feedback: '反馈' }
  return map[t] || t
}
function statusLabel(s: string) {
  const map: Record<string, string> = {
    pending: '待确认',
    accepted: '已采纳',
    rejected: '已拒绝',
    deferred: '稍后',
  }
  return map[s] || s
}
function statusType(s: string): 'success' | 'info' | 'warning' | 'danger' {
  if (s === 'accepted') return 'success'
  if (s === 'rejected') return 'danger'
  if (s === 'deferred') return 'warning'
  return 'info'
}

function buildJdAnalysis() {
  const title = position.value.trim()
  const lines = jdText.value
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .slice(0, 20)
  return {
    job_title: title,
    company: company.value.trim(),
    summary: jdText.value.trim().slice(0, 500) || title,
    requirements: lines.map((content) => ({ content, importance: 'high' })),
    nice_to_have: [],
  }
}

async function loadProfile() {
  try {
    const res = await listProfileItems(undefined, 'confirmed')
    const items = res.data || []
    const p: Record<string, unknown> = {
      skills: [] as string[],
      experience: [] as { title: string; content: string }[],
      education: [] as string[],
      target_roles: [] as string[],
      summary: '',
    }
    for (const it of items) {
      const content = it.content || ''
      if (it.category === 'skill') {
        ;(p.skills as string[]).push(content || it.title || '')
      } else if (it.category === 'experience') {
        ;(p.experience as { title: string; content: string }[]).push({
          title: it.title || '',
          content,
        })
      } else if (it.category === 'education') {
        ;(p.education as string[]).push(it.title || content)
      } else if (it.category === 'target') {
        ;(p.target_roles as string[]).push(content || it.title || '')
      } else if (it.category === 'soft' && content) {
        p.summary = content
      } else if (it.category === 'basic_info' && it.title === '姓名') {
        p.name = content
      }
    }
    profile.value = p
    const skills = (p.skills as string[]).slice(0, 4)
    const targets = (p.target_roles as string[]).slice(0, 2)
    if (skills.length || targets.length) {
      profileBrief.value = [targets.join('、'), skills.join('、')].filter(Boolean).join(' · ')
    } else {
      profileBrief.value = ''
    }
  } catch {
    profile.value = {}
    profileBrief.value = ''
  }
}

async function beginInterview() {
  if (!position.value.trim()) {
    prepError.value = '请填写目标岗位'
    return
  }
  prepError.value = ''
  preparing.value = true
  launching.value = true
  try {
    if (!Object.keys(profile.value).length) await loadProfile()
    startPayload.value = {
      jd_analysis: buildJdAnalysis(),
      profile: profile.value,
      max_turns: maxTurns.value,
      user_id: auth.user?.id ?? null,
      voice: ttsVoice.value,
      speed: ttsSpeed.value,
      tts_style: ttsStyle.value,
    }
    // 新开一场：清掉旧的本地暂存
    clearActiveLocal()
    // 稍等一拍，让按钮 loading 可见，再切到面试页
    await new Promise((r) => setTimeout(r, 120))
    phase.value = 'conduct'
  } finally {
    preparing.value = false
  }
}

function onStarted(id: string) {
  interviewId.value = id
  persistActiveLocal()
}

// 首题就绪后去掉“准备中”标签
watch(
  () => voicePanelRef.value?.state.stage,
  (s) => {
    if (s === 'speaking' || s === 'listening') launching.value = false
    if (s === 'connecting' || s === 'thinking') launching.value = true
  },
)

// 进入进行态后面板挂载，再注入最新负载并连 WS / START
// resume 流程自己 connect，这里只处理「新开一场」
const skipAutoStart = ref(false)
watch(phase, async (p) => {
  if (p !== 'conduct') {
    if (p === 'report') clearActiveLocal()
    return
  }
  if (skipAutoStart.value) return
  if (!startPayload.value) return
  await nextTick()
  voicePanelRef.value?.startWithPayload(startPayload.value)
})

function onReport(r: Record<string, unknown>) {
  report.value = r || {}
  clearActiveLocal()
  phase.value = 'report'
  loadProposals()
}

// ── 本地持久化（刷新恢复） ──────────────────────────

function loadActiveLocal(): ActiveVoiceInterviewStore | null {
  try {
    const raw = localStorage.getItem(ACTIVE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as ActiveVoiceInterviewStore
  } catch {
    return null
  }
}

function persistActiveLocal() {
  if (!interviewId.value || phase.value !== 'conduct') return
  const payload: ActiveVoiceInterviewStore = {
    interviewId: interviewId.value,
    company: company.value,
    position: position.value,
    jdText: jdText.value,
    maxTurns: maxTurns.value,
    chatLog: voicePanelRef.value?.state.chatLog ? [...voicePanelRef.value.state.chatLog] : [],
    updatedAt: Date.now(),
  }
  localStorage.setItem(ACTIVE_KEY, JSON.stringify(payload))
}

function clearActiveLocal() {
  localStorage.removeItem(ACTIVE_KEY)
  activeLocal.value = null
}

function discardActive() {
  clearActiveLocal()
  ElMessage.success('已丢弃未完成的面试')
}

async function resumeActive() {
  const a = activeLocal.value
  if (!a?.interviewId) return
  resuming.value = true
  skipAutoStart.value = true
  try {
    const st = await getInterviewState(a.interviewId)
    if (!st.data || st.data.is_complete) {
      clearActiveLocal()
      ElMessage.info('该面试已结束或不存在，已清除恢复记录')
      skipAutoStart.value = false
      return
    }
    company.value = a.company || ''
    position.value = a.position || ''
    jdText.value = a.jdText || ''
    maxTurns.value = a.maxTurns || 8
    interviewId.value = a.interviewId
    await loadProfile()
    startPayload.value = {
      jd_analysis: buildJdAnalysis(),
      profile: profile.value,
      max_turns: maxTurns.value,
      user_id: auth.user?.id ?? null,
      voice: ttsVoice.value,
      speed: ttsSpeed.value,
      tts_style: ttsStyle.value,
    }
    phase.value = 'conduct'
    await nextTick()
    if (a.chatLog?.length && voicePanelRef.value) {
      voicePanelRef.value.state.chatLog = [...a.chatLog]
    }
    if (voicePanelRef.value) {
      voicePanelRef.value.state.interviewId = a.interviewId
      voicePanelRef.value.connect()
    }
  } catch {
    ElMessage.error('恢复面试失败，请重新开始')
    clearActiveLocal()
  } finally {
    resuming.value = false
    // 稍后再允许自动 START，避免本次 watch 竞态
    setTimeout(() => {
      skipAutoStart.value = false
    }, 500)
  }
}

// 监听对话变化，持续写本地
watch(
  () => voicePanelRef.value?.state.chatLog?.length ?? 0,
  () => {
    if (phase.value === 'conduct') persistActiveLocal()
  },
)

// ── 历史记录 ────────────────────────────────────────

async function openHistory() {
  historyOpen.value = true
  historyDetail.value = null
  historyLoading.value = true
  try {
    const res = await listInterviewHistory(50)
    historyList.value = res.data || []
  } catch {
    historyList.value = []
    ElMessage.error('加载历史失败')
  } finally {
    historyLoading.value = false
  }
}

async function openHistoryDetail(id: string) {
  try {
    const res = await getInterviewHistoryDetail(id)
    historyDetail.value = res.data
  } catch {
    ElMessage.error('加载详情失败')
  }
}

function formatTime(iso: string | null) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return iso
  }
}

function reasonLabel(r: string) {
  const map: Record<string, string> = {
    max_turns: '达到轮数',
    all_topics_covered: '话题完成',
    evaluator_ended: '面试官结束',
  }
  return map[r] || r
}

async function loadProposals() {
  if (!interviewId.value) return
  try {
    const res = await listProposals(interviewId.value)
    proposals.value = res.data || []
    loadedProposals.value = true
  } catch {
    loadedProposals.value = true
  }
}

async function actProposal(id: number, action: string) {
  try {
    await actOnProposal(id, action)
    ElMessage.success(
      action === 'accept' ? '已采纳，画像已更新' : action === 'reject' ? '已拒绝，画像不变' : '已标记稍后处理',
    )
    loadProposals()
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

async function confirmEnd() {
  try {
    await ElMessageBox.confirm('确定结束本场面试并查看报告吗？', '结束面试', {
      type: 'warning',
      confirmButtonText: '结束并看报告',
      cancelButtonText: '继续面试',
    })
  } catch {
    return
  }
  voicePanelRef.value?.endInterview()
  if (interviewId.value) {
    // 尽力拉取报告；WS done 可能尚未到达
    try {
      const { getInterviewReport } = await import('../api/interview')
      const res = await getInterviewReport(interviewId.value)
      report.value = res.data || {}
    } catch {
      /* ignore */
    }
  }
  clearActiveLocal()
  phase.value = 'report'
  loadProposals()
}

function backToPrepare() {
  voicePanelRef.value?.disconnect()
  interviewId.value = ''
  report.value = {}
  proposals.value = []
  loadedProposals.value = false
  phase.value = 'prepare'
}

function goText() {
  router.push('/workspace')
}

function goWorkspace() {
  router.push('/workspace')
}

onMounted(() => {
  loadProfile()
  loadTtsPref()
  loadVoices()
  const a = loadActiveLocal()
  // 24h 内的未完成面试才提示恢复
  if (a?.interviewId && Date.now() - (a.updatedAt || 0) < 24 * 3600 * 1000) {
    activeLocal.value = a
  }
})
</script>

<style scoped>
.vi-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-page);
}

.vi-main {
  flex: 1;
  width: 100%;
  max-width: 760px;
  margin: 0 auto;
  padding: var(--space-8) var(--space-5) var(--space-10);
}

.eyebrow {
  font-size: var(--text-sm);
  color: var(--color-accent-600);
  font-weight: 600;
  letter-spacing: 0.06em;
  margin: 0 0 var(--space-2);
}

.prep-title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  margin: 0 0 var(--space-3);
  color: var(--color-text-primary);
}

.prep-desc {
  color: var(--color-text-secondary);
  line-height: 1.7;
  margin: 0 0 var(--space-6);
}

.prep-panel,
.report-panel {
  background: var(--color-bg);
  border: var(--border-light);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  box-shadow: var(--shadow-card);
}

.prep-form {
  max-width: 560px;
}

.profile-chip {
  display: inline-block;
  font-size: var(--text-xs);
  color: var(--color-accent-600);
  background: var(--color-accent-50);
  border-radius: var(--radius-full);
  padding: 4px 10px;
  margin-bottom: var(--space-3);
}

.profile-warn {
  font-size: var(--text-xs);
  color: var(--color-warning-600);
  margin-bottom: var(--space-3);
}

.err {
  color: var(--color-danger-600);
  font-size: var(--text-sm);
  margin: 0 0 var(--space-3);
}

.prep-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.prep-loading-hint {
  margin: var(--space-3) 0 0;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.tts-box {
  margin-top: var(--space-4);
  padding: var(--space-4);
  border: var(--border-light);
  border-radius: var(--radius-xl);
  background: var(--color-bg-elevated);
}

.tts-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.tts-title {
  font-weight: 600;
  font-size: var(--text-sm);
  color: var(--color-text-primary);
}

.tts-form {
  max-width: 520px;
}

.tts-speed-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
}

.tts-speed-val {
  min-width: 40px;
  font-size: var(--text-sm);
  color: var(--color-accent-600);
  font-weight: 600;
}

.tts-hint {
  margin: 4px 0 0;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.resume-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-accent-50);
  border: 1px solid var(--color-accent-200);
}

.resume-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.resume-text strong {
  color: var(--color-accent-600);
}

.resume-actions {
  display: flex;
  gap: var(--space-2);
}

.hist-loading,
.hist-empty {
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  padding: var(--space-4) 0;
}

.hist-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.hist-item {
  text-align: left;
  width: 100%;
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  background: var(--color-bg-elevated);
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-default);
}

.hist-item:hover {
  border-color: var(--color-accent-400);
}

.hist-item-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
}

.hist-pos {
  font-weight: 600;
  color: var(--color-text-primary);
}

.hist-score {
  color: var(--color-accent-600);
  font-weight: 700;
}

.hist-item-meta {
  margin-top: 4px;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.hist-summary {
  margin-top: 6px;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.hist-detail-title {
  font-family: var(--font-display);
  margin: 0 0 4px;
}

.hist-chat {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: var(--space-3) 0;
  max-height: 320px;
  overflow-y: auto;
}

.hist-line {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}

.hist-line.ai {
  background: var(--color-bg-page);
}

.hist-line.user {
  background: var(--color-accent-50);
}

.hist-role {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.hist-content {
  color: var(--color-text-primary);
  line-height: 1.6;
  word-break: break-word;
}

.conduct-panel {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  min-height: 520px;
  background: var(--color-bg);
  border: var(--border-light);
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: var(--shadow-card);
}

.conduct-head {
  flex-shrink: 0;
  padding: var(--space-4) var(--space-5);
  border-bottom: var(--border-light);
}

.conduct-title {
  font-family: var(--font-display);
  margin: 0;
  font-size: var(--text-lg);
}

.conduct-sub {
  margin: 4px 0 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.conduct-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.report-summary {
  display: flex;
  gap: var(--space-5);
  align-items: center;
  margin-bottom: var(--space-5);
}

.score-badge {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--color-accent-50);
  border: 2px solid var(--color-accent-200);
}

.score-num {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-accent-600);
}

.score-label {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.report-meta .meta-item {
  margin: 0 0 4px;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.report-empty {
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
}

.report-block {
  margin-bottom: var(--space-5);
}

.sec {
  margin: 0 0 var(--space-2);
  font-size: var(--text-md);
  font-family: var(--font-display);
}

.sec-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.body-text {
  margin: 0;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.body-list {
  margin: 0;
  padding-left: 1.2em;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.dim-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dim-item {
  display: grid;
  grid-template-columns: 80px 1fr 40px;
  gap: 8px;
  align-items: center;
  font-size: var(--text-sm);
}

.dim-bar {
  height: 6px;
  background: var(--color-gray-100);
  border-radius: 99px;
  overflow: hidden;
}

.dim-fill {
  display: block;
  height: 100%;
  background: var(--color-accent-500);
  border-radius: 99px;
}

.proposal {
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  margin-bottom: var(--space-2);
}

.p-head {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}

.p-val {
  font-size: var(--text-sm);
  color: var(--color-text-primary);
}

.p-reason {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.p-actions {
  margin-top: 8px;
  display: flex;
  gap: 6px;
}

.empty-hint {
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
}

.report-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-5);
}
</style>
