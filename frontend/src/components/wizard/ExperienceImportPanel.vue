<template>
  <div class="exp-nl-box">
    <p v-if="loading" class="hint">正在读取个人画像中的经历…</p>
    <p v-else-if="!items.length" class="hint">
      个人画像中暂无「项目/经历」条目。可先到
      <el-button text type="primary" size="small" @click="$emit('go-knowledge')">个人画像</el-button>
      补充，或使用 AI 包装 / 生成。
    </p>
    <template v-else>
      <p class="hint">勾选要写入本份简历的经历（来自已确认画像，可再编辑）：</p>
      <div v-for="pe in items" :key="pe.id" class="import-item">
        <el-checkbox v-model="pe.checked">
          <span class="import-title">{{ pe.title || '未命名经历' }}</span>
        </el-checkbox>
        <div class="import-preview">{{ pe.content.slice(0, 120) }}{{ pe.content.length > 120 ? '…' : '' }}</div>
      </div>
      <div class="exp-nl-actions">
        <el-button type="primary" @click="$emit('apply')">
          导入所选（{{ items.filter((p) => p.checked).length }}）
        </el-button>
        <el-button @click="$emit('close')">收起</el-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  loading: boolean
  items: { id: number; title: string; content: string; checked: boolean }[]
}>()

defineEmits<{
  (e: 'apply'): void
  (e: 'close'): void
  (e: 'go-knowledge'): void
}>()
</script>

<style scoped>
.exp-nl-box {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  background: var(--color-bg-elevated);
}
.hint {
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  line-height: 1.6;
  margin: 0 0 var(--space-3);
}
.import-item {
  padding: var(--space-2) 0;
  border-bottom: var(--border-light);
}
.import-item:last-of-type {
  border-bottom: none;
}
.import-title {
  font-weight: 600;
  color: var(--color-text-primary);
}
.import-preview {
  margin-left: 24px;
  margin-top: 2px;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  line-height: 1.5;
}
.exp-nl-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
</style>
