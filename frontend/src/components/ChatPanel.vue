<template>
  <div class="chat-panel">
    <!-- 顶部操作栏 -->
    <div class="chat-header">
      <el-button type="primary" size="small" @click="handleNewSession">
        <Plus :size="16" />新建会话
      </el-button>
      <el-tag v-if="session.sessionId" type="info" size="small">
        {{ stageLabel }}
      </el-tag>
    </div>

    <!-- 消息列表 -->
    <div class="messages" ref="messagesRef">
      <!-- 空状态 -->
      <div v-if="session.messages.length === 0" class="empty-hint">
        <div class="empty-icon">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <p class="empty-title">开始新的对话</p>
        <p class="empty-desc">点击「新建会话」开始，然后输入目标岗位 JD 或上传简历文件</p>
      </div>

      <!-- 消息列表 -->
      <div
        v-for="msg in session.messages"
        :key="msg.id"
        :class="['message', `message-${msg.role}`]"
      >
        <!-- 系统消息：左边框横条式 -->
        <div
          v-if="msg.role === 'system'"
          :class="['system-bar', { 'system-bar--error': msg.eventType === 'error' }]"
        >
          <div class="system-bar-icon">
            <!-- 错误图标 -->
            <svg v-if="msg.eventType === 'error'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="15" y1="9" x2="9" y2="15"/>
              <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            <!-- 信息图标 -->
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="16" x2="12" y2="12"/>
              <line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
          </div>
          <div class="system-bar-text">{{ msg.content }}</div>
        </div>

        <!-- 用户/助手消息：气泡式 -->
        <template v-else>
          <div class="message-bubble">
            <div class="message-text">{{ msg.content }}</div>
          </div>
          <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
        </template>
      </div>

      <!-- 加载状态：脉动点 -->
      <div v-if="session.isLoading" class="message message-assistant">
        <div class="message-bubble loading-bubble">
          <span class="dot-pulse">
            <span></span><span></span><span></span>
          </span>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <!-- 面试进行中：提示使用语音面板 -->
      <div v-if="session.interviewActive" class="interview-active-hint">
        🎤 面试进行中，请使用右侧语音面板进行回答
      </div>
      <template v-else>
        <div class="input-actions">
          <el-upload
            :show-file-list="false"
            :before-upload="handleFileUpload"
            accept=".txt,.pdf,.doc,.docx,.md"
          >
            <el-button :disabled="!session.sessionId" circle size="small">
              <Upload :size="16" />
            </el-button>
          </el-upload>
        </div>
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          :placeholder="inputPlaceholder"
          :disabled="!session.sessionId || session.isLoading"
          resize="none"
          @keydown.enter.exact.prevent="handleSend"
        />
        <el-button
          type="primary"
          :disabled="!canSend"
          :loading="session.isLoading"
          @click="handleSend"
        >
          发送
        </el-button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { Plus, Upload } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { useSessionStore } from '../stores/session'
import { sendMessageSSE, uploadFile } from '../api/sessions'

const session = useSessionStore()

// 页面加载时自动恢复上次的会话
onMounted(async () => {
  if (!session.sessionId) {
    await session.restoreSession()
  }
})

const inputText = ref('')
const messagesRef = ref<HTMLElement>()

const stageLabel = computed(() => {
  const map: Record<string, string> = {
    init: '初始',
    has_jd: '已分析JD',
    has_resume: '已有简历',
    has_jd_and_resume: '就绪',
    completed: '已完成',
  }
  return map[session.stage] || session.stage
})

const inputPlaceholder = computed(() => {
  if (!session.sessionId) return '请先新建会话'
  if (session.isLoading) return '正在处理中...'
  return '输入 JD 内容、简历文本，或描述您的需求...'
})

const canSend = computed(() => {
  return session.sessionId && !session.isLoading && inputText.value.trim().length > 0
})

// 自动滚动到底部
watch(() => session.messages.length, () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
})

function formatTime(ts: string) {
  try {
    return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

async function handleNewSession() {
  try {
    await session.createSession()
  } catch {
    ElMessage.error('创建会话失败')
  }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || !session.sessionId) return

  // 添加用户消息到列表
  session.addMessage({
    role: 'user',
    content: text,
    timestamp: new Date().toISOString(),
  })
  inputText.value = ''
  session.isLoading = true

  // 发送 SSE 请求
  session.sseController = sendMessageSSE(
    session.sessionId,
    text,
    (event, data) => session.handleSSEEvent(event, data),
    (err) => {
      session.addMessage({
        role: 'system',
        content: `❌ 发送失败: ${err.message}`,
        timestamp: new Date().toISOString(),
        eventType: 'error',
      })
      session.isLoading = false
    },
    () => {
      session.isLoading = false
    },
  )
}

async function handleFileUpload(file: File) {
  if (!session.sessionId) return false

  try {
    const res = await uploadFile(session.sessionId, file)
    session.addMessage({
      role: 'system',
      content: `📎 ${res.data.message}: ${file.name}`,
      timestamp: new Date().toISOString(),
    })
    ElMessage.success(res.data.hint)
  } catch {
    session.addMessage({
      role: 'system',
      content: '❌ 文件上传失败，请重试',
      timestamp: new Date().toISOString(),
      eventType: 'error',
    })
  }
  return false // 阻止 el-upload 默认上传
}
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* ── 头部 ── */
.chat-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: var(--border-light);
}

/* ── 根容器：撑满父 flex 区域 ── */
.chat-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
  overflow: hidden;
}

/* ── 消息列表 ── */
.messages {
  flex: 1;
  height: 0;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-4);
}

/* ── 空状态 ── */
.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  padding: var(--space-8);
}

.empty-icon {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-gray-100);
  border-radius: var(--radius-lg);
  color: var(--color-gray-400);
  margin-bottom: var(--space-4);
}

.empty-title {
  margin: 0 0 var(--space-2);
  font-size: var(--text-base);
  font-weight: var(--weight-medium);
  color: var(--color-text-primary);
}

.empty-desc {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  max-width: 240px;
  line-height: var(--leading-relaxed);
}

/* ── 消息基础 ── */
.message {
  margin-bottom: var(--space-4);
}

.message-bubble {
  display: flex;
  align-items: flex-start;
  padding: var(--space-3) var(--space-4);
  line-height: var(--leading-relaxed);
  word-break: break-word;
}

.message-text {
  flex: 1;
}

.message-time {
  font-size: var(--text-2xs);
  color: var(--color-text-disabled);
  margin-top: var(--space-1);
  text-align: right;
}

/* ── 用户消息 ── */
.message-user .message-bubble {
  background: var(--color-accent-600);
  color: var(--color-white);
  margin-left: 40px;
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg);
}

.message-user .message-time {
  text-align: right;
}

/* ── 助手消息 ── */
.message-assistant .message-bubble {
  background: var(--color-gray-100);
  color: var(--color-text-primary);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm);
}

.message-assistant .message-time {
  text-align: left;
}

/* ── 系统消息：左边框横条式 ── */
.message-system {
  margin-bottom: var(--space-3);
}

.system-bar {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-left: 3px solid var(--color-accent-600);
  background: var(--color-accent-50);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}

.system-bar--error {
  border-left-color: var(--color-danger);
  background: var(--color-danger-light);
  color: var(--color-danger);
}

.system-bar-icon {
  flex-shrink: 0;
  color: var(--color-accent-600);
  margin-top: 1px;
}

.system-bar-text {
  flex: 1;
}

/* ── 加载状态：脉动点 ── */
.loading-bubble {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.dot-pulse {
  display: inline-flex;
  gap: 4px;
  align-items: center;
}

.dot-pulse span {
  width: 6px;
  height: 6px;
  background: var(--color-gray-400);
  border-radius: var(--radius-full);
  animation: dot-pulse 1.4s infinite ease-in-out both;
}

.dot-pulse span:nth-child(1) { animation-delay: 0s; }
.dot-pulse span:nth-child(2) { animation-delay: 0.16s; }
.dot-pulse span:nth-child(3) { animation-delay: 0.32s; }

.loading-step {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

/* ── 输入区域 ── */
.input-area {
  padding: var(--space-3) var(--space-4);
  border-top: var(--border-light);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.input-actions {
  display: flex;
  gap: var(--space-2);
}

.interview-active-hint {
  text-align: center;
  padding: var(--space-3);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  background: var(--color-bg-hover);
  border-radius: var(--radius-md);
}
</style>
