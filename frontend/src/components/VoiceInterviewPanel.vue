<template>
  <div class="voice-interview-panel">
    <!-- 顶部状态栏 -->
    <div class="vi-header">
      <el-tag :type="stageTagType" size="small">{{ stageLabel }}</el-tag>
      <el-tag v-if="state.connected" type="success" size="small">已连接</el-tag>
      <el-tag v-else type="info" size="small">未连接</el-tag>
      <span v-if="turnHint" class="vi-turn-hint">{{ turnHint }}</span>
    </div>

    <!-- 主内容区 -->
    <div class="vi-body" ref="bodyRef">
      <!-- 连接中 / 开场准备（首题前的可见反馈） -->
      <div v-if="showStarting" class="vi-starting">
        <div class="starting-orb" aria-hidden="true">
          <Loader2 :size="28" class="spin" />
        </div>
        <p class="starting-title">{{ startingTitle }}</p>
        <p class="starting-desc">{{ startingDesc }}</p>
        <div class="starting-steps">
          <div class="s-step" :class="{ on: state.connected }">
            <span class="s-dot" />连接面试服务
          </div>
          <div class="s-step" :class="{ on: state.stage === 'thinking' || state.stage === 'speaking' || state.chatLog.length > 0 }">
            <span class="s-dot" />面试官准备开场
          </div>
          <div class="s-step" :class="{ on: state.stage === 'speaking' || state.chatLog.length > 0 }">
            <span class="s-dot" />第一题就绪
          </div>
        </div>
      </div>

      <!-- 空状态（未自动启动时） -->
      <div v-else-if="state.stage === 'idle' && state.chatLog.length === 0" class="vi-empty">
        <el-button type="primary" size="large" @click="handleStart">
          <Mic :size="18" />
          {{ idleLabel }}
        </el-button>
      </div>

      <!-- 对话历史 -->
      <div
        v-for="(entry, idx) in state.chatLog"
        :key="idx"
        :class="['vi-chat-entry', entry.role === 'user' ? 'vi-chat-user' : 'vi-chat-ai']"
      >
        <div class="vi-chat-label">{{ entry.role === 'user' ? '你' : '面试官' }}</div>
        <div class="vi-chat-text">{{ entry.text }}</div>
      </div>

      <!-- 当前 ASR 转写（用户正在说 / 刚说完） -->
      <div v-if="state.asrText && state.stage === 'listening'" class="vi-chat-entry vi-chat-user">
        <div class="vi-chat-label">你（正在说）</div>
        <div class="vi-chat-text vi-chat-pending">{{ state.asrText }}</div>
      </div>

      <!-- AI 正在生成的回答（实时 token 流） -->
      <div v-if="state.currentQuestion && state.stage === 'speaking'" class="vi-chat-entry vi-chat-ai">
        <div class="vi-chat-label">面试官</div>
        <div class="vi-chat-text">{{ state.currentQuestion }}</div>
      </div>

      <!-- 轮次思考中（有对话后的思考） -->
      <div v-if="!showStarting && state.stage === 'thinking' && state.chatLog.length > 0" class="vi-thinking">
        <Loader2 :size="16" class="spin" />
        面试官正在思考下一句…
      </div>
      <div v-else-if="!showStarting && state.stage === 'thinking'" class="vi-thinking">
        <Loader2 :size="16" class="spin" />
        面试官正在准备开场，通常需要 20–40 秒…
      </div>

      <!-- 错误 -->
      <el-alert
        v-if="state.errorMessage"
        :title="state.errorMessage"
        type="error"
        show-icon
        closable
        @close="state.errorMessage = ''"
      />

      <!-- 面试报告（简版，完整报告由父级渲染） -->
      <div v-if="state.stage === 'done' && state.report" class="vi-report">
        <el-card>
          <template #header>
            <span>面试结束</span>
          </template>
          <p v-if="state.report.summary">{{ state.report.summary }}</p>
          <p v-if="state.report.overall_score != null">
            综合评分：<el-tag type="primary">{{ state.report.overall_score }}</el-tag>
          </p>
        </el-card>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <div class="vi-footer">
      <!-- 连接/开场中：禁止误触录音 -->
      <template v-if="showStarting">
        <el-button type="primary" circle size="large" disabled>
          <Loader2 :size="18" class="spin" />
        </el-button>
        <span class="vi-hint">{{ startingHint }}</span>
      </template>

      <!-- 录音中：显示停止/打断按钮 -->
      <template v-else-if="state.recording">
        <el-button type="warning" circle size="large" @click="handleEndOfSpeech">
          <Square :size="18" />
        </el-button>
        <span class="vi-hint">点击结束回答</span>
      </template>

      <!-- AI 播放中：显示打断按钮 -->
      <template v-else-if="state.playing">
        <el-button type="danger" circle size="large" @click="handleInterrupt">
          <X :size="18" />
        </el-button>
        <span class="vi-hint">点击打断</span>
      </template>

      <!-- 等待用户说话 -->
      <template v-else-if="state.stage === 'listening' || state.stage === 'idle'">
        <el-button type="primary" circle size="large" @click="handleStartRecording">
          <Mic :size="18" />
        </el-button>
        <span class="vi-hint">点击开始回答</span>
      </template>

      <!-- 面试结束 -->
      <template v-else-if="state.stage === 'done'">
        <el-button type="primary" @click="handleRestart">重新开始</el-button>
      </template>

      <!-- 出错：仍保留恢复入口，避免只剩文字框 -->
      <template v-else-if="state.stage === 'error'">
        <el-button type="primary" circle size="large" @click="handleRecover">
          <Mic :size="18" />
        </el-button>
        <span class="vi-hint">出错了 · 点击重试连接并继续回答</span>
      </template>

      <!-- 文字输入（调试/补充） -->
      <div v-if="state.connected && state.stage !== 'done'" class="vi-text-input">
        <el-input
          v-model="textInput"
          placeholder="或直接输入文字..."
          size="small"
          @keyup.enter="handleSendText"
        >
          <template #append>
            <el-button @click="handleSendText">发送</el-button>
          </template>
        </el-input>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { Mic, Loader2, Square, X } from 'lucide-vue-next'
import { useVoiceChat, type UseVoiceChatOptions } from '../composables/useVoiceChat'
import { useSessionStore } from '../stores/session'

const props = withDefaults(defineProps<{
  wsUrl: string
  mode?: 'interview' | 'chat'
  /** 外部注入启动参数（主页语音面试）；不传则回退 session 会话上下文 */
  startPayload?: UseVoiceChatOptions['startPayload']
  /** 挂载后是否自动连接。false 时由父级点「开始」触发 */
  autoConnect?: boolean
  maxTurns?: number
}>(), {
  mode: 'interview',
  autoConnect: true,
  maxTurns: 8,
})

const session = useSessionStore()

const emit = defineEmits<{
  (e: 'complete', report: Record<string, unknown>): void
  (e: 'end'): void
  (e: 'started', interviewId: string): void
}>()

function endInterview() {
  disconnect()
  emit('end')
}

const resolvedPayload = computed<UseVoiceChatOptions['startPayload']>(() => {
  if (props.startPayload) return props.startPayload
  const jd = (session.jdAnalysis as unknown as Record<string, unknown>) || {}
  const profile = (session.profile as unknown as Record<string, unknown>) || {}
  if (props.mode !== 'interview') {
    return { jd_analysis: jd, profile }
  }
  return {
    jd_analysis: jd,
    profile,
    referenced_questions: (session.interviewQuestions || []).map(q => q.question).slice(0, 20),
    max_turns: props.maxTurns,
  }
})

const options: UseVoiceChatOptions = {
  wsUrl: props.wsUrl,
  startPayload: resolvedPayload.value,
}

const {
  state,
  connect,
  disconnect,
  resetForNewInterview,
  setStartPayload,
  startRecording,
  stopRecording,
  endOfSpeech,
  interrupt,
  sendText,
} = useVoiceChat(options)

const textInput = ref('')
const bodyRef = ref<HTMLElement>()

const idleLabel = computed(() => (props.mode === 'chat' ? '开始语音对话' : '开始面试'))

/** 首题尚未就绪：连接中 / 开场生成中 */
const showStarting = computed(() => {
  if (state.stage === 'done' || state.stage === 'error') return false
  if (state.chatLog.length > 0) return false
  if (state.stage === 'connecting') return true
  if (state.stage === 'thinking' && !state.currentQuestion) return true
  if (state.stage === 'speaking' && !state.currentQuestion && !state.playing) return true
  return false
})

const startingTitle = computed(() => {
  if (state.stage === 'connecting' || !state.connected) return '正在连接面试服务…'
  return '面试官正在准备开场…'
})

const startingDesc = computed(() => {
  if (state.stage === 'connecting' || !state.connected) {
    return '建立安全语音通道，请稍候'
  }
  return '正在根据你的岗位与画像生成第一题，通常需要 20–40 秒。生成后会自动开始播报。'
})

const startingHint = computed(() =>
  state.connected ? '面试官准备中，请稍候…' : '连接中…',
)

const turnHint = computed(() => {
  if (props.mode !== 'interview') return ''
  const userTurns = state.chatLog.filter(e => e.role === 'user').length
  return userTurns ? `已答 ${userTurns} / ${props.maxTurns} 轮` : ''
})

function scrollToBottom() {
  nextTick(() => {
    if (bodyRef.value) {
      bodyRef.value.scrollTop = bodyRef.value.scrollHeight
    }
  })
}

watch(() => state.chatLog.length, scrollToBottom)
watch(() => state.currentQuestion, scrollToBottom)

watch(() => state.interviewId, (id) => {
  if (id) emit('started', id)
})

// ── 计算属性 ──────────────────────────────────────────

const stageLabel = computed(() => {
  const map: Record<string, string> = {
    idle: '准备中',
    connecting: '连接中',
    listening: '正在听',
    thinking: '思考中',
    speaking: '面试官发言',
    done: '面试结束',
    error: '出错',
  }
  return map[state.stage] || state.stage
})

const stageTagType = computed(() => {
  const map: Record<string, string> = {
    idle: 'info',
    connecting: 'warning',
    listening: 'success',
    thinking: 'warning',
    speaking: 'primary',
    done: 'success',
    error: 'danger',
  }
  return (map[state.stage] || 'info') as 'success' | 'info' | 'warning' | 'danger'
})

// ── 事件处理 ──────────────────────────────────────────

function handleStart() {
  connect()
}

function handleStartRecording() {
  startRecording()
}

function handleEndOfSpeech() {
  stopRecording()
  endOfSpeech()
}

function handleInterrupt() {
  interrupt()
}

function handleSendText() {
  const text = textInput.value.trim()
  if (!text) return
  sendText(text)
  textInput.value = ''
}

function handleRestart() {
  disconnect()
  resetForNewInterview()
  setStartPayload(resolvedPayload.value)
  connect()
}

/** 错误态恢复：清错误 → 若有 interviewId 则 RESUME，否则重新 START */
function handleRecover() {
  state.errorMessage = ''
  state.stage = 'connecting'
  if (state.interviewId || props.startPayload || resolvedPayload.value) {
    // 有 id 走 resume（useVoiceChat.connect 内优先 resume）
    connect()
  } else {
    handleStart()
  }
}

/** 父级准备页点「开始」时调用：注入最新负载并连接 */
function startWithPayload(payload: NonNullable<UseVoiceChatOptions['startPayload']>) {
  disconnect()
  resetForNewInterview()
  setStartPayload(payload)
  state.stage = 'connecting'
  connect()
}

// ── 监听完成 ─────────────────────────────────────────

watch(() => state.report, (report) => {
  if (report) emit('complete', report)
})

onMounted(() => {
  if (props.autoConnect) {
    connect()
  }
})

defineExpose({
  state,
  connect,
  disconnect,
  resetForNewInterview,
  setStartPayload,
  startWithPayload,
  endInterview,
})
</script>

<style scoped>
.voice-interview-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding: var(--space-4);
  gap: var(--space-3);
  overflow: hidden;
}

.vi-header {
  flex-shrink: 0;
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.vi-turn-hint {
  margin-left: auto;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.vi-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  -webkit-overflow-scrolling: touch;
}

.vi-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.vi-starting {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: var(--space-3);
  padding: var(--space-6);
  text-align: center;
}

.starting-orb {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--color-accent-50);
  border: 1px solid var(--color-accent-200);
  color: var(--color-accent-600);
}

.starting-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--text-lg);
  color: var(--color-text-primary);
}

.starting-desc {
  margin: 0;
  max-width: 360px;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.starting-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: var(--space-2);
  text-align: left;
}

.s-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.s-step.on {
  color: var(--color-accent-600);
}

.s-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-gray-300);
  flex-shrink: 0;
}

.s-step.on .s-dot {
  background: var(--color-accent-600);
}

.vi-label {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-1);
}

/* 对话历史条目 */
.vi-chat-entry {
  margin-bottom: var(--space-3);
}

.vi-chat-label {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-1);
}

.vi-chat-text {
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  word-break: break-word;
}

.vi-chat-user .vi-chat-text {
  background: var(--color-accent-50);
  color: var(--color-text-primary);
  margin-left: var(--space-10);
  border-radius: var(--radius-md) var(--radius-md) var(--radius-sm) var(--radius-md);
}

.vi-chat-ai .vi-chat-text {
  background: var(--color-bg-page);
  border: var(--border-light);
  color: var(--color-text-primary);
  margin-right: var(--space-10);
  border-radius: var(--radius-md) var(--radius-md) var(--radius-md) var(--radius-sm);
}

.vi-chat-pending {
  opacity: 0.7;
  font-style: italic;
}

.vi-thinking {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-secondary);
  font-size: var(--text-base);
}

.spin {
  animation: spin 1s linear infinite;
  color: var(--color-accent-600);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.vi-report {
  margin-top: var(--space-2);
}

.vi-report :deep(.el-card__header) {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}

.vi-report ul {
  margin: var(--space-2) 0 0;
  padding-left: var(--space-5);
}

.vi-report li {
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
}

.vi-footer {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: var(--border-light);
  background: var(--color-bg);
}

.vi-hint {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.vi-text-input {
  width: 100%;
  margin-top: var(--space-2);
}
</style>
