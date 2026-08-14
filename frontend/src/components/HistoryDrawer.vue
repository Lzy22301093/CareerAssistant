<template>
  <el-drawer :model-value="modelValue" title="历史会话" @close="$emit('update:modelValue', false)" size="350px">
    <div v-if="loading" v-loading="true" style="height: 200px" />

    <div v-else-if="sessions.length === 0" class="empty">
      <el-empty description="暂无历史会话" :image-size="80" />
    </div>

    <div v-else class="session-list">
      <div
        v-for="s in sessions"
        :key="s.session_id"
        :class="['session-item', { active: s.session_id === session.sessionId }]"
        @click="handleLoad(s.session_id)"
      >
        <div class="session-info">
          <span class="session-id">{{ s.session_id.slice(0, 8) }}...</span>
          <el-tag size="small">{{ s.stage }}</el-tag>
        </div>
        <div class="session-meta">
          <span>消息: {{ s.message_count }}</span>
          <el-button
            type="danger"
            size="small"
            text
            @click.stop="handleDelete(s.session_id)"
          >
            删除
          </el-button>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSessionStore } from '../stores/session'
import { getSessionStatus } from '../api/sessions'
import type { SessionStatus } from '../types'

const props = defineProps<{ modelValue: boolean }>()
defineEmits<{ 'update:modelValue': [val: boolean] }>()

const session = useSessionStore()
const loading = ref(false)
const sessions = ref<SessionStatus[]>([])

// 后端没有 list sessions 接口，这里用一个 workaround：
// 维护一个本地 session id 列表
const savedIds = ref<string[]>(JSON.parse(localStorage.getItem('session_ids') || '[]'))

watch(() => props.modelValue, async (val) => {
  if (!val) return
  await refresh()
})

async function refresh() {
  loading.value = true
  const results: SessionStatus[] = []

  // 同时更新本地列表：把当前 session 加进去
  if (session.sessionId && !savedIds.value.includes(session.sessionId)) {
    savedIds.value.unshift(session.sessionId)
    localStorage.setItem('session_ids', JSON.stringify(savedIds.value))
  }

  for (const id of savedIds.value) {
    try {
      const res = await getSessionStatus(id)
      results.push(res.data)
    } catch {
      // 会话已过期，移除
      savedIds.value = savedIds.value.filter((i) => i !== id)
    }
  }
  localStorage.setItem('session_ids', JSON.stringify(savedIds.value))
  sessions.value = results
  loading.value = false
}

async function handleLoad(id: string) {
  try {
    await session.loadSession(id)
    ElMessage.success('会话已加载')
  } catch {
    ElMessage.error('加载失败')
  }
}

async function handleDelete(id: string) {
  await ElMessageBox.confirm('确定删除此会话？', '确认')
  try {
    await session.deleteSession(id)
    savedIds.value = savedIds.value.filter((i) => i !== id)
    localStorage.setItem('session_ids', JSON.stringify(savedIds.value))
    sessions.value = sessions.value.filter((s) => s.session_id !== id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}
</script>

<style scoped>
.empty {
  display: flex;
  justify-content: center;
  padding-top: 40px;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.session-item {
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.session-item:hover {
  border-color: #409eff;
}

.session-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.session-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.session-id {
  font-family: monospace;
  color: #606266;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
