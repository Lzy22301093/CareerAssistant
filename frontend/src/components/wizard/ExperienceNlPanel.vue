<template>
  <div class="exp-nl-box">
    <el-input
      :model-value="modelValue"
      type="textarea"
      :rows="4"
      :placeholder="`把你的${targetLabel}粗略描述一下，如：在某某公司做后端实习，负责…`"
      @update:model-value="$emit('update:modelValue', $event)"
    />
    <p v-if="error" class="err">{{ error }}</p>
    <div class="exp-nl-actions">
      <el-button type="primary" :loading="loading" @click="$emit('submit')">结构化</el-button>
      <el-button @click="$emit('cancel')">取消</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: string
  loading: boolean
  error: string
  targetLabel: string
}>()

defineEmits<{
  (e: 'update:modelValue', v: string): void
  (e: 'submit'): void
  (e: 'cancel'): void
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
.exp-nl-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
.err {
  color: var(--color-danger-600);
  font-size: var(--text-sm);
  margin: var(--space-2) 0 0;
}
</style>
