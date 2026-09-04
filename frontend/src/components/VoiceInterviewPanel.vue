<template>
  <div class="voice-interview-panel">
    <!-- 顶部状态栏 -->
    <div class="vi-header">
      <el-tag :type="stageTagType" size="small">{{ stageLabel }}</el-tag>
      <el-tag v-if="state.connected" type="success" size="small">已连接</el-tag>
      <el-tag v-else type="info" size="small">未连接</el-tag>
    </div>

    <!-- 主内容区 -->
    <div class="vi-body" ref="bodyRef">
      <!-- 空状态 -->
      <div v-if="state.stage === 'idle' && state.chatLog.length === 0" class="vi-empty">
        <el-button type="primary" size="large" @click="handleStart">
          <el-icon><Microphone /></el-icon>
          {{ mode === 'chat' ? '开始语音对话' : '开始面试' }}
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

      <!-- 思考中 -->
      <div v-if="state.stage === 'thinking'" class="vi-thinking">
        <el-icon class="spin"><Loading /></el-icon>
        {{ mode === 'chat' ? 'AI 正在思考...' : '面试官正在思考...' }}
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

      <!-- 面试报告 -->
      <div v-if="state.stage === 'done' && state.report" class="vi-report">
        <el-card>
          <template #header>
            <span>面试报告</span>
          </template>
          <p v-if="state.report.summary">{{ state.report.summary }}</p>
          <p v-if="state.report.overall_score">
            综合评分：<el-tag type="primary">{{ state.report.overall_score }}</el-tag>
          </p>
          <div v-if="(state.report.suggestions as string[])?.length">
            <p class="vi-label">建议：</p>
            <ul>
              <li v-for="(s, i) in (state.report.suggestions as string[])" :key="i">{{ s }}</li>
            </ul>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <div class="vi-footer">
      <!-- 录音中：显示停止/打断按钮 -->
      <template v-if="state.recording">
        <el-button type="warning" circle size="large" @click="handleEndOfSpeech">
          <el-icon><VideoPause /></el-icon>
        </el-button>
        <span class="vi-hint">点击结束回答</span>
      </template>

      <!-- AI 播放中：显示打断按钮 -->
      <template v-else-if="state.playing">
        <el-button type="danger" circle size="large" @click="handleInterrupt">
          <el-icon><CloseBold /></el-icon>
        </el-button>
        <span class="vi-hint">点击打断</span>
      </template>

      <!-- 等待用户说话 -->
      <template v-else-if="state.stage === 'listening' || state.stage === 'idle'">
        <el-button type="primary" circle size="large" @click="handleStartRecording">
          <el-icon><Microphone /></el-icon>
        </el-button>
        <span class="vi-hint">点击开始回答</span>
      </template>

      <!-- 面试结束 -->
      <template v-else-if="state.stage === 'done'">
        <el-button v-if="mode === 'chat'" type="primary" @click="endInterview">
          结束对话
        </el-button>
        <el-button v-else type="primary" @click="handleRestart">
          重新开始
        </el-button>
      </template>

      <!-- 文字输入（调试用） -->
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
import { Microphone, Loading, VideoPause, CloseBold } from '@element-plus/icons-vue'
import { useVoiceChat, type UseVoiceChatOptions } from '../composables/useVoiceChat'
import { useSessionStore } from '../stores/session'

const props = withDefaults(defineProps<{
  wsUrl: string
  mode?: 'interview' | 'chat'
}>(), {
  mode: 'interview',
})

const session = useSessionStore()

const emit = defineEmits<{
  (e: 'complete', report: Record<string, unknown>): void
  (e: 'end'): void
}>()

function endInterview() {
  disconnect()
  emit('end')
}

const startPayload: UseVoiceChatOptions['startPayload'] = {
  jd_analysis: (session.jdAnalysis as unknown as Record<string, unknown>) || {},
  profile: (session.profile as unknown as Record<string, unknown>) || {},
  ...(props.mode === 'interview' ? {
    referenced_questions: (session.interviewQuestions || []).map(q => q.question).slice(0, 20),
    max_turns: 10,
  } : {}),
}

const options: UseVoiceChatOptions = {
  wsUrl: props.wsUrl,
  startPayload,
}

const {
  state,
  connect,
  disconnect,
  startRecording,
  stopRecording,
  endOfSpeech,
  interrupt,
  sendText,
} = useVoiceChat(options)

const textInput = ref('')
const bodyRef = ref<HTMLElement>()

// 自动滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (bodyRef.value) {
      bodyRef.value.scrollTop = bodyRef.value.scrollHeight
    }
  })
}

watch(() => state.chatLog.length, scrollToBottom)
watch(() => state.currentQuestion, scrollToBottom)

// ── 计算属性 ──────────────────────────────────────────

const stageLabel = computed(() => {
  const map: Record<string, string> = {
    idle: '准备中',
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
  state.stage = 'idle'
  state.asrText = ''
  state.currentQuestion = ''
  state.chatLog = []
  state.report = null
  state.errorMessage = ''
  connect()
}

// ── 监听完成 ─────────────────────────────────────────

watch(() => state.report, (report) => {
  if (report) emit('complete', report)
})

// 组件挂载后自动连接 WebSocket 并启动面试
onMounted(() => {
  connect()
})
</script>

<style scoped>
.voice-interview-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  gap: 12px;
}

.vi-header {
  display: flex;
  gap: 8px;
  align-items: center;
}

.vi-body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vi-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.vi-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.vi-text {
  font-size: 15px;
  line-height: 1.6;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

/* 对话历史条目 */
.vi-chat-entry {
  margin-bottom: 12px;
}

.vi-chat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.vi-chat-text {
  font-size: 15px;
  line-height: 1.6;
  padding: 8px 12px;
  border-radius: 8px;
  word-break: break-word;
}

.vi-chat-user .vi-chat-text {
  background: var(--el-color-primary-light-9);
  color: var(--el-text-color-primary);
  margin-left: 40px;
  border-radius: 8px 8px 2px 8px;
}

.vi-chat-ai .vi-chat-text {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
  margin-right: 40px;
  border-radius: 8px 8px 8px 2px;
}

.vi-chat-pending {
  opacity: 0.7;
  font-style: italic;
}

.vi-thinking {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.vi-report {
  margin-top: 8px;
}

.vi-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.vi-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.vi-text-input {
  width: 100%;
  margin-top: 8px;
}
</style>
