<template>
  <div class="chat-panel">
    <!-- 顶部操作栏 -->
    <div class="chat-header">
      <el-button type="primary" size="small" @click="handleNewSession">
        <el-icon><Plus /></el-icon>新建会话
      </el-button>
      <el-tag v-if="session.sessionId" type="info" size="small">
        {{ stageLabel }}
      </el-tag>
    </div>

    <!-- 消息列表 -->
    <div class="messages" ref="messagesRef">
      <div v-if="session.messages.length === 0" class="empty-hint">
        <el-icon :size="48" color="#c0c4cc"><ChatDotRound /></el-icon>
        <p>开始新的对话</p>
        <p class="hint-text">输入目标岗位 JD 或上传简历文件</p>
      </div>

      <div
        v-for="msg in session.messages"
        :key="msg.id"
        :class="['message', `message-${msg.role}`]"
      >
        <div class="message-bubble">
          <div v-if="msg.role === 'system'" class="system-icon">
            <el-icon><InfoFilled /></el-icon>
          </div>
          <div class="message-text">{{ msg.content }}</div>
        </div>
        <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
      </div>

      <div v-if="session.isLoading" class="message message-assistant">
        <div class="message-bubble">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span style="margin-left: 6px">正在处理...</span>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <div class="input-actions">
        <el-upload
          :show-file-list="false"
          :before-upload="handleFileUpload"
          accept=".txt,.pdf,.doc,.docx,.md"
        >
          <el-button :disabled="!session.sessionId" circle size="small">
            <el-icon><Upload /></el-icon>
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { Plus, ChatDotRound, InfoFilled, Loading, Upload } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useSessionStore } from '../stores/session'
import { sendMessageSSE, uploadFile } from '../api/sessions'

const session = useSessionStore()

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
      ElMessage.error(`发送失败: ${err.message}`)
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
    ElMessage.error('文件上传失败')
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

.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

.empty-hint p {
  margin: 8px 0 0;
}

.hint-text {
  font-size: 13px;
  color: #c0c4cc;
}

.message {
  margin-bottom: 16px;
}

.message-user .message-bubble {
  background: #409eff;
  color: #fff;
  margin-left: 40px;
}

.message-assistant .message-bubble {
  background: #f0f2f5;
  color: #303133;
}

.message-system .message-bubble {
  background: #ecf5ff;
  color: #409eff;
  border: 1px solid #d9ecff;
}

.message-bubble {
  display: flex;
  align-items: flex-start;
  padding: 10px 14px;
  border-radius: 8px;
  line-height: 1.5;
  word-break: break-word;
}

.system-icon {
  margin-right: 6px;
  flex-shrink: 0;
  margin-top: 2px;
}

.message-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
  text-align: right;
}

.message-user .message-time {
  text-align: right;
}

.message-system .message-time {
  text-align: left;
}

.input-area {
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-actions {
  display: flex;
  gap: 8px;
}
</style>
