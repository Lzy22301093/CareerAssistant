<template>
  <div class="skeleton-loader" :class="[`skeleton-${variant}`]">
    <!-- Text variant: 模拟文本行 -->
    <template v-if="variant === 'text'">
      <div
        v-for="i in lines"
        :key="i"
        class="skeleton-line"
        :style="{ width: i === lines ? '60%' : '100%' }"
      />
    </template>

    <!-- Card variant: 模拟卡片 -->
    <template v-else-if="variant === 'card'">
      <div v-for="i in lines" :key="i" class="skeleton-card">
        <div class="skeleton-card-header">
          <div class="skeleton-line" style="width: 40%" />
          <div class="skeleton-line" style="width: 20%" />
        </div>
        <div class="skeleton-line" style="width: 100%" />
        <div class="skeleton-line" style="width: 80%" />
      </div>
    </template>

    <!-- Table variant: 模拟表格 -->
    <template v-else-if="variant === 'table'">
      <div class="skeleton-table-header">
        <div v-for="c in 3" :key="c" class="skeleton-line skeleton-th" />
      </div>
      <div v-for="r in rows" :key="r" class="skeleton-table-row">
        <div v-for="c in 3" :key="c" class="skeleton-line skeleton-td" />
      </div>
    </template>

    <!-- Chart variant: 模拟图表/进度条 -->
    <template v-else-if="variant === 'chart'">
      <div class="skeleton-chart">
        <div class="skeleton-line" style="width: 30%; height: 20px" />
        <div class="skeleton-bar-track">
          <div class="skeleton-bar-fill" />
        </div>
        <div class="skeleton-chart-labels">
          <div class="skeleton-line" style="width: 50px" />
          <div class="skeleton-line" style="width: 30px" />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'text' | 'card' | 'table' | 'chart'
  lines?: number
  rows?: number
}>(), {
  variant: 'text',
  lines: 3,
  rows: 4,
})
</script>

<style scoped>
.skeleton-loader {
  padding: var(--space-4) 0;
}

/* ── 基础脉动线条 ── */
.skeleton-line {
  height: 14px;
  border-radius: var(--radius-sm);
  background: linear-gradient(
    90deg,
    var(--color-gray-100) 25%,
    var(--color-gray-50) 50%,
    var(--color-gray-100) 75%
  );
  background-size: 400% 100%;
  animation: skeleton-pulse 1.8s infinite ease-in-out;
}

.skeleton-line + .skeleton-line {
  margin-top: var(--space-3);
}

/* ── Card variant ── */
.skeleton-card {
  background: var(--color-gray-50);
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  margin-bottom: var(--space-3);
}

.skeleton-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}

/* ── Table variant ── */
.skeleton-table-header {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: var(--border-light);
}

.skeleton-th {
  height: 10px;
  background: var(--color-gray-200);
}

.skeleton-table-row {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: var(--border-light);
}

.skeleton-td {
  height: 12px;
}

/* ── Chart variant ── */
.skeleton-chart {
  background: var(--color-gray-50);
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.skeleton-bar-track {
  height: 8px;
  background: var(--color-gray-200);
  border-radius: var(--radius-full);
  margin: var(--space-3) 0;
  overflow: hidden;
}

.skeleton-bar-fill {
  height: 100%;
  width: 65%;
  border-radius: var(--radius-full);
  background: linear-gradient(
    90deg,
    var(--color-gray-200) 25%,
    var(--color-gray-100) 50%,
    var(--color-gray-200) 75%
  );
  background-size: 400% 100%;
  animation: skeleton-pulse 1.8s infinite ease-in-out;
}

.skeleton-chart-labels {
  display: flex;
  justify-content: space-between;
}
</style>
