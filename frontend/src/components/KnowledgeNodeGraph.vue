<template>
  <div class="graph-wrap">
    <svg :viewBox="`0 0 ${W} ${H}`" class="graph-svg" :style="{ maxHeight: `${H}px` }">
      <!-- center node -->
      <circle :cx="cx" :cy="cy" r="34" class="center-ring" />
      <circle :cx="cx" :cy="cy" r="30" class="center-fill" />
      <text :x="cx" :y="cy + 6" text-anchor="middle" class="center-label">个人</text>

      <!-- spokes + category nodes -->
      <g v-for="node in nodes" :key="node.category">
        <line
          :x1="cx"
          :y1="cy"
          :x2="node.x"
          :y2="node.y"
          class="spoke"
          :class="{ active: node.category === activeCategory }"
        />
        <g
          class="cat-node"
          :class="{ active: node.category === activeCategory }"
          @click="$emit('select', node.category)"
        >
          <circle :cx="node.x" :cy="node.y" :r="node.r" class="cat-circle" />
          <text :x="node.x" :y="node.y - 4" text-anchor="middle" class="cat-count">
            {{ node.count }}
          </text>
          <text :x="node.x" :y="node.y + (node.r > 18 ? 18 : 12)" text-anchor="middle" class="cat-name">
            {{ node.label }}
          </text>
        </g>
      </g>
    </svg>
    <div v-if="!categories.length" class="graph-empty">
      <p>知识库还是空的</p>
      <p class="sub">点击「补充知识库」，开始建立你的个人画像</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CategorySummary, ProfileCategory } from '../types'

const props = defineProps<{
  categories: CategorySummary[]
  activeCategory?: string
}>()

const emit = defineEmits<{
  (e: 'select', category: string): void
}>()

const W = 720
const H = 480
const cx = W / 2
const cy = H / 2

const CATEGORY_LABELS: Record<ProfileCategory, string> = {
  basic_info: '基本信息',
  education: '教育经历',
  experience: '项目经历',
  skill: '专业技能',
  target: '目标岗位',
  soft: '自我评价',
  interview_feedback: '面试反馈',
}

const nodes = computed(() => {
  const list = props.categories
  if (!list.length) return []
  const radius = Math.min(W, H) / 2 - 70
  const startAngle = -Math.PI / 2
  const angleStep = (2 * Math.PI) / list.length
  return list.map((c, i) => {
    const angle = startAngle + i * angleStep
    const x = cx + radius * Math.cos(angle)
    const y = cy + radius * Math.sin(angle)
    return {
      category: c.category,
      label: CATEGORY_LABELS[c.category] || c.category,
      count: c.count,
      x,
      y,
      // 节点大小随数量略变
      r: Math.max(14, 14 + Math.min(8, c.count)),
    }
  })
})
</script>

<style scoped>
.graph-wrap {
  position: relative;
  width: 100%;
  min-height: 420px;
  display: flex;
  justify-content: center;
  align-items: center;
}
.graph-svg {
  width: 100%;
}
.center-ring {
  fill: none;
  stroke: var(--el-color-primary-light-5, #93c5fd);
  stroke-width: 2;
  stroke-dasharray: 4 4;
}
.center-fill {
  fill: var(--el-color-primary-light-8, #eff6ff);
  stroke: var(--el-color-primary);
  stroke-width: 1.5;
}
.center-label {
  font-size: 14px;
  font-weight: var(--weight-semibold);
  fill: var(--color-text-primary, #1f2937);
}
.spoke {
  stroke: var(--color-gray-300, #d1d5db);
  stroke-width: 1.5;
  stroke-dasharray: 5 4;
}
.spoke.active {
  stroke: var(--el-color-primary);
}
.cat-node {
  cursor: pointer;
}
.cat-circle {
  fill: var(--color-bg, #fff);
  stroke: var(--color-gray-400, #9ca3af);
  stroke-width: 1.5;
}
.cat-node.active .cat-circle {
  stroke: var(--el-color-primary);
  fill: var(--el-color-primary-light-8, #eff6ff);
}
.cat-count {
  font-size: 13px;
  font-weight: var(--weight-semibold);
  fill: var(--color-text-primary, #1f2937);
}
.cat-name {
  font-size: 11px;
  fill: var(--color-text-secondary, #6b7280);
}
.graph-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--color-text-secondary);
}
.graph-empty .sub {
  font-size: 12px;
  opacity: 0.8;
}
</style>
