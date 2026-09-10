<template>
  <div class="dir-page">
    <AppNav>
      <el-button text @click="goKnowledgeBase">去完善画像</el-button>
    </AppNav>
    <div class="dir-titlebar">
      <div class="dir-title">画像与投递方向</div>
      <p class="dir-sub">基于你的已确认画像，推荐值得投递的方向</p>
    </div>

    <div class="dir-body">
      <section class="dir-panel">
        <p class="hint">AI 根据你的教育背景与主修课程，分析适合的投递方向。选 1~3 个你感兴趣的方向。</p>

        <!-- 分析中 -->
        <div v-if="loading" class="dir-loading">
          <SkeletonLoader variant="card" :lines="2" />
          <p class="loading-label">正在分析你的画像…</p>
        </div>

        <!-- 错误（无画像 / 失败） -->
        <div v-else-if="errMsg" class="state-error">
          <el-alert type="error" :title="errMsg" show-icon :closable="false" />
          <div class="error-actions">
            <el-button type="primary" plain @click="goKnowledgeBase">去完善画像</el-button>
            <el-button text @click="reset">重新分析</el-button>
          </div>
        </div>

        <!-- 结果 -->
        <div v-else-if="hasAnalyzed && candidates.length" class="dir-result">
          <div class="dir-note">基于你的已确认画像（技能 / 经历 / 教育 / 目标）为你推荐以下投递方向：</div>

          <div class="dir-grid">
            <div
              v-for="(c, i) in candidates"
              :key="c.title"
              class="dir-card"
              :class="{ selected: selected.includes(c.title) }"
              @click="toggle(c.title)"
            >
              <span class="dir-radio" :class="{ on: selected.includes(c.title) }" aria-hidden="true">
                <Check v-if="selected.includes(c.title)" :size="14" />
              </span>
              <div class="dir-card-body">
                <div class="dir-card-title">{{ c.title }}</div>
                <div class="dir-card-reason">{{ c.reason }}</div>
                <button class="dir-detail-toggle" type="button" @click.stop="toggleDetail(i)">
                  {{ expanded[i] ? '收起详情' : '查看详情' }}
                  <ChevronUp v-if="expanded[i]" :size="14" />
                  <ChevronDown v-else :size="14" />
                </button>
                <div v-if="expanded[i]" class="dir-detail">{{ c.detail || '暂无更多详情' }}</div>
              </div>
            </div>
          </div>

          <div class="dir-actions">
            <span class="dir-count">{{ selected.length }} / 3 已选</span>
            <el-button
              type="primary"
              :disabled="selected.length === 0"
              :loading="saving"
              @click="save"
            >保存所选方向 ({{ selected.length }})</el-button>
          </div>
          <p v-if="saveErr" class="err">{{ saveErr }}</p>
        </div>

        <!-- 空态（已分析但无候选项） -->
        <div v-else-if="hasAnalyzed" class="state-empty">
          <Compass :size="40" class="empty-icon" />
          <p class="empty-title">暂未找到合适的投递方向</p>
          <p class="empty-sub">先到个人知识库完善并确认基础事实、技能与经历，推荐会更准。</p>
          <el-button type="primary" @click="goKnowledgeBase">去完善画像</el-button>
        </div>

        <!-- 初始态 -->
        <div v-else class="dir-start">
          <el-button type="primary" size="large" @click="analyze">分析我的画像</el-button>
          <p class="start-tip">先到个人知识库完善并确认基础事实、技能与经历，推荐会更准。</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check, ChevronDown, ChevronUp, Compass } from 'lucide-vue-next'
import AppNav from '../components/AppNav.vue'
import SkeletonLoader from '../components/SkeletonLoader.vue'
import { confirmDirections, recommendDirections } from '../api/profile'
import type { DirectionCandidate } from '../types'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const hasAnalyzed = ref(false)
const candidates = ref<DirectionCandidate[]>([])
const selected = ref<string[]>([])
const expanded = ref<Record<number, boolean>>({})
const errMsg = ref('')
const saveErr = ref('')

function toggle(title: string) {
  const idx = selected.value.indexOf(title)
  if (idx >= 0) {
    selected.value.splice(idx, 1)
  } else if (selected.value.length < 3) {
    selected.value.push(title)
  } else {
    ElMessage.warning('最多选择 3 个方向')
  }
}

function toggleDetail(i: number) {
  expanded.value[i] = !expanded.value[i]
}

function goKnowledgeBase() {
  router.push('/knowledge-base')
}

function reset() {
  errMsg.value = ''
  saveErr.value = ''
  candidates.value = []
  selected.value = []
  expanded.value = {}
  hasAnalyzed.value = false
}

async function analyze() {
  loading.value = true
  hasAnalyzed.value = true
  errMsg.value = ''
  saveErr.value = ''
  candidates.value = []
  try {
    const res = await recommendDirections()
    candidates.value = res.data
    selected.value = []
  } catch (e) {
    const detail = (e as any)?.response?.data?.detail
    errMsg.value =
      typeof detail === 'string' && detail ? detail : '画像方向推荐失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function save() {
  const chosen = candidates.value.filter((c) => selected.value.includes(c.title))
  if (!chosen.length) return
  saveErr.value = ''
  saving.value = true
  try {
    await confirmDirections(chosen)
    ElMessage.success(`已保存 ${chosen.length} 个投递方向，可在个人知识库查看`)
    reset()
    router.push('/knowledge-base')
  } catch {
    saveErr.value = '保存失败，请重试'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.dir-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-page);
}
.dir-titlebar {
  padding: var(--space-6) var(--space-8) var(--space-4);
  border-bottom: var(--border-light);
  background: color-mix(in srgb, var(--color-bg) 92%, white);
}
.dir-title {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: var(--weight-semibold);
  letter-spacing: -0.01em;
  color: var(--color-text-primary);
}
.dir-sub {
  margin: var(--space-1) 0 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.dir-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-8);
}
.dir-panel {
  max-width: 760px;
  margin: 0 auto;
  background: var(--color-bg);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-6);
}
.hint {
  margin: 0 0 var(--space-5);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}

/* loading */
.dir-loading {
  padding: var(--space-4) 0;
}
.loading-label {
  margin-top: var(--space-4);
  text-align: center;
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
}

/* error / empty / start 统一居中空态 */
.state-error,
.state-empty,
.dir-start {
  padding: var(--space-8) 0;
  text-align: center;
}
.state-error .error-actions {
  margin-top: var(--space-4);
  display: flex;
  justify-content: center;
  gap: var(--space-2);
}
.state-empty .empty-icon {
  color: var(--color-gray-400);
  margin-bottom: var(--space-3);
}
.state-empty .empty-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--weight-medium);
  color: var(--color-text-primary);
  margin: 0;
}
.state-empty .empty-sub,
.start-tip {
  font-size: var(--text-sm);
  color: var(--color-text-disabled);
  margin-top: var(--space-2);
  line-height: var(--leading-relaxed);
}
.state-empty .el-button,
.dir-start .el-button {
  margin-top: var(--space-5);
}

/* 结果 */
.dir-note {
  margin-bottom: var(--space-5);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
}
.dir-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-4);
}
.dir-card {
  position: relative;
  display: flex;
  gap: var(--space-3);
  padding: var(--space-5);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-default),
    box-shadow var(--duration-normal) var(--ease-default),
    transform var(--duration-normal) var(--ease-default);
}
.dir-card:hover {
  border-color: var(--color-accent-400);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
.dir-card.selected {
  border-color: var(--color-accent-600);
  box-shadow: 0 0 0 1px var(--color-accent-600) inset;
  background: var(--color-accent-50);
}
.dir-radio {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  border: 1.5px solid var(--color-gray-300);
  display: grid;
  place-items: center;
  color: var(--color-bg-elevated);
  margin-top: 2px;
  transition: border-color var(--duration-fast) var(--ease-default),
    background var(--duration-fast) var(--ease-default);
}
.dir-radio.on {
  background: var(--color-accent-600);
  border-color: var(--color-accent-600);
  color: var(--color-bg-elevated);
}
.dir-card-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}
.dir-card-reason {
  margin-top: var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}
.dir-detail-toggle {
  margin-top: var(--space-2);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  border: none;
  background: transparent;
  font-size: var(--text-sm);
  color: var(--color-accent-600);
  cursor: pointer;
}
.dir-detail-toggle:hover {
  color: var(--color-accent-500);
}
.dir-detail {
  margin-top: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}
.dir-actions {
  margin-top: var(--space-6);
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.dir-count {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.err {
  margin-top: var(--space-3);
  color: var(--color-danger-600);
  font-size: var(--text-sm);
}
</style>
