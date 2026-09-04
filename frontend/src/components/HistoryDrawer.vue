<template>
  <el-drawer :model-value="modelValue" title="历史会话" @close="$emit('update:modelValue', false)" size="350px">
    <div v-if="loading" v-loading="true" style="height: 200px" />

    <div v-else-if="sessions.length === 0" class="empty">
      <div class="empty-icon">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
      </div>
      <p class="empty-text">暂无历史会话</p>
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
import { listSessions } from '../api/sessions'
import type { SessionListItem } from '../types'

const props = defineProps<{ modelValue: boolean }>()
defineEmits<{ 'update:modelValue': [val: boolean] }>()

const session = useSessionStore()
const loading = ref(false)
const sessions = ref<SessionListItem[]>([])

// 历史列表由后端 GET /sessions/ 提供（替代原来的 localStorage workaround，
// 避免刷新/清缓存后历史丢失）
watch(() => props.modelValue, async (val) => {
  if (!val) return
  await refresh()
})

async function refresh() {
  loading.value = true
  try {
    const res = await listSessions()
    // 当前会话始终展示在最前
    const current = session.sessionId
    sessions.value = [...res.data].sort((a, b) => {
      if (a.session_id === current) return -1
      if (b.session_id === current) return 1
      return 0
    })
  } catch {
    sessions.value = []
  } finally {
    loading.value = false
  }
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
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-top: var(--space-10);
  color: var(--color-text-disabled);
}

.empty-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-gray-100);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-3);
}

.empty-text {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.session-item {
  padding: var(--space-3);
  border: var(--border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-default);
}

.session-item:hover {
  border-color: var(--color-accent-600);
}

.session-item.active {
  border-color: var(--color-accent-600);
  background: var(--color-accent-50);
}

.session-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.session-id {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.session-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-disabled);
}
</style>
