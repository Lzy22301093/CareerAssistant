<template>
  <el-drawer :model-value="modelValue" title="历史会话" @close="$emit('update:modelValue', false)" size="360px">
    <!-- 加载 -->
    <div v-if="loading">
      <SkeletonLoader variant="card" :lines="3" />
    </div>

    <!-- 空态 -->
    <div v-else-if="sessions.length === 0" class="empty">
      <div class="empty-icon">
        <History :size="26" />
      </div>
      <p class="empty-text">暂无历史会话</p>
      <p class="empty-hint">开始一段新对话，进度会自动保存于此。</p>
    </div>

    <!-- 列表 -->
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
import { History } from 'lucide-vue-next'
import { useSessionStore } from '../stores/session'
import { listSessions } from '../api/sessions'
import type { SessionListItem } from '../types'
import SkeletonLoader from './SkeletonLoader.vue'

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
/* 抽屉标题：衬线体 */
:deep(.el-drawer__header) {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: 0;
  padding-bottom: var(--space-4);
  border-bottom: var(--border-light);
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-12) var(--space-6);
  text-align: center;
}

.empty-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--color-accent-600) 12%, var(--color-bg));
  color: var(--color-accent-600);
  border-radius: var(--radius-md);
  border: var(--border-light);
  margin-bottom: var(--space-4);
}

.empty-text {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.empty-hint {
  margin: var(--space-2) 0 0;
  font-size: var(--text-xs);
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
  background: var(--color-bg-elevated);
  cursor: pointer;
  transition:
    border-color var(--duration-fast) var(--ease-default),
    box-shadow var(--duration-fast) var(--ease-default),
    transform var(--duration-fast) var(--ease-default);
}

.session-item:hover {
  border-color: var(--color-accent-600);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
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
