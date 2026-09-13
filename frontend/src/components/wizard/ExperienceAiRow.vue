<template>
  <div class="exp-ai-row">
    <button type="button" class="exp-chip" :class="{ on: importOpen }" @click="$emit('import')">
      <span class="chip-num">①</span>
      <span>{{ importing ? '正在读取画像…' : '从画像导入经历' }}</span>
    </button>
    <button type="button" class="exp-chip" :class="{ on: nlOpen }" @click="$emit('nl', target)">
      <span class="chip-num">②</span>
      <span>帮我包装经历</span>
    </button>
    <button type="button" class="exp-chip" :disabled="generating" @click="$emit('generate')">
      <span class="chip-num">③</span>
      <span>{{ generating ? '正在生成…' : '没有经历，AI 生成' }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  importOpen: boolean
  importing: boolean
  nlOpen: boolean
  generating: boolean
  target: 'internship' | 'project'
}>()

defineEmits<{
  (e: 'import'): void
  (e: 'nl', target: 'internship' | 'project'): void
  (e: 'generate'): void
}>()
</script>

<style scoped>
.exp-ai-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.exp-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text-primary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
}
.exp-chip:hover:not(:disabled) {
  border-color: var(--color-accent-400);
  background: var(--color-accent-50);
}
.exp-chip.on {
  border-color: var(--color-accent-600);
  background: var(--color-accent-50);
  color: var(--color-accent-600);
}
.exp-chip:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
.chip-num {
  display: inline-grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--color-accent-600) 12%, white);
  color: var(--color-accent-600);
  font-size: 11px;
  font-weight: 700;
}
</style>
