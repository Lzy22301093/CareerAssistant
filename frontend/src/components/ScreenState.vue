<template>
  <div class="screen-state" :class="`screen-state--${type}`">
    <!-- 加载态：统一的骨架屏 -->
    <template v-if="type === 'loading'">
      <SkeletonLoader :variant="skeleton" :lines="lines" :rows="rows" />
    </template>

    <!-- 空态 / 错误态：图标 + 标题 + 描述 + 操作 -->
    <template v-else>
      <div class="state-icon" :class="{ 'is-error': type === 'error' }">
        <component :is="iconComp" :size="26" />
      </div>
      <p class="state-title">{{ title }}</p>
      <p v-if="desc" class="state-desc">{{ desc }}</p>
      <div v-if="$slots.default" class="state-action">
        <slot />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Inbox, AlertTriangle } from 'lucide-vue-next'
import SkeletonLoader from './SkeletonLoader.vue'

const props = withDefaults(
  defineProps<{
    type?: 'loading' | 'empty' | 'error'
    title?: string
    desc?: string
    icon?: any
    skeleton?: 'text' | 'card' | 'table' | 'chart'
    lines?: number
    rows?: number
  }>(),
  {
    type: 'empty',
    icon: undefined,
    skeleton: 'text',
    lines: 4,
    rows: 3,
  },
)

const iconComp = computed(() => {
  if (props.icon) return props.icon
  return props.type === 'error' ? AlertTriangle : Inbox
})
</script>

<style scoped>
.screen-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--space-8) var(--space-6);
  min-height: 200px;
  width: 100%;
}

.state-icon {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--color-accent-600) 12%, white);
  border-radius: var(--radius-lg);
  color: var(--color-accent-600);
  margin-bottom: var(--space-4);
}
.state-icon.is-error {
  background: color-mix(in srgb, var(--color-danger-600) 12%, white);
  color: var(--color-danger-600);
}

.state-title {
  margin: 0 0 var(--space-2);
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}

.state-desc {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
  max-width: 320px;
}

.state-action {
  margin-top: var(--space-5);
}
</style>
