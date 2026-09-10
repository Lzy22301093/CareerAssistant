<template>
  <div class="mi-page">
    <AppNav>
      <el-button text @click="restart">重开面试</el-button>
    </AppNav>
    <div class="mi-titlebar">
      <div class="mi-title">AI 模拟面试</div>
      <p class="mi-sub">准备 → 作答 → 报告，一场结构化面试</p>
    </div>

    <div class="mi-body">
      <!-- 步骤指示器 -->
      <div class="mi-steps">
        <template v-for="(step, i) in steps" :key="step.key">
          <div class="mi-step" :class="{ active: phase === step.key, done: stepIndex > i }">
            <span class="step-dot">
              <Check v-if="stepIndex > i" :size="13" />
              <template v-else>{{ i + 1 }}</template>
            </span>
            <span class="step-label">{{ step.label }}</span>
          </div>
          <div v-if="i < steps.length - 1" class="mi-step-line" :class="{ on: stepIndex > i }" />
        </template>
      </div>

      <Transition name="mi-fade" mode="out-in">
        <!-- 准备页 -->
        <section v-if="phase === 'prepare'" key="prepare" class="mi-panel">
          <h3 class="mi-h3">面试前准备</h3>
          <p class="hint">输入目标岗位，选择轮数，AI 将基于你的画像与简历出题。</p>
          <el-form label-width="88px" style="max-width: 520px">
            <el-form-item label="目标岗位">
              <el-input v-model="position" placeholder="如：后端开发实习生" />
            </el-form-item>
            <el-form-item label="轮数">
              <el-input-number v-model="maxTurns" :min="3" :max="20" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="starting" @click="onStart">
                {{ starting ? '正在生成题目…' : '开始面试' }}
              </el-button>
            </el-form-item>
          </el-form>
          <p v-if="startError" class="err">{{ startError }}</p>
        </section>

        <!-- 进行页 -->
        <section v-else-if="phase === 'conduct'" key="conduct" class="mi-panel">
          <div class="mi-progress">
            <span class="mi-progress-num">第 {{ currentTurn }} / {{ maxTurns }} 轮</span>
            <span class="mi-progress-hint">作答后提交，AI 会逐轮点评并继续追问</span>
          </div>
          <div class="mi-question">{{ currentQuestion || '…' }}</div>
          <el-input
            v-model="answer"
            type="textarea"
            :rows="5"
            placeholder="输入你的回答…"
          />
          <div class="mi-actions">
            <el-button type="primary" :loading="submitting" @click="onAnswer">
              {{ submitting ? '正在分析你的回答…' : '提交回答' }}
            </el-button>
          </div>
          <p v-if="conductError" class="err">{{ conductError }}</p>
        </section>

        <!-- 报告页 -->
        <section v-else key="report" class="mi-panel">
          <div class="mi-phase-head">
            <h3 class="mi-h3">面试报告</h3>
            <el-button type="primary" plain @click="loadProposals">查看画像更新提案</el-button>
          </div>

          <!-- 综合分 -->
          <div v-if="hasReport" class="report-summary">
            <div class="score-badge">
              <div class="score-num">{{ overallScore ?? '—' }}</div>
              <div class="score-label">综合评分</div>
            </div>
            <div v-if="targetPosition || turnCount" class="report-meta">
              <p v-if="targetPosition" class="meta-item">目标岗位：{{ targetPosition }}</p>
              <p v-if="turnCount" class="meta-item">回答轮数：{{ turnCount }}</p>
            </div>
          </div>

          <!-- 无报告 / 评估不可用兜底 -->
          <div v-else class="report-empty">
            <AlertCircle :size="36" class="empty-icon" />
            <p class="empty-text">本场暂无详细评价，可能是评估服务暂不可用。</p>
          </div>

          <div v-if="summary" class="report-block">
            <h4 class="sec">总体评价</h4>
            <p class="report-summary-text">{{ summary }}</p>
          </div>

          <div v-if="dimensionList.length" class="report-block">
            <h4 class="sec">维度得分</h4>
            <div class="dim-list">
              <div v-for="d in dimensionList" :key="d.key" class="dim-item">
                <span class="dim-name">{{ d.key }}</span>
                <span class="dim-bar">
                  <span class="dim-fill" :style="{ width: dimWidth(d.value) }" />
                </span>
                <span class="dim-score">{{ d.value }}</span>
              </div>
            </div>
          </div>

          <div v-if="strengths.length" class="report-block">
            <h4 class="sec">优势</h4>
            <ul class="list">
              <li v-for="(s, i) in strengths" :key="i">{{ s }}</li>
            </ul>
          </div>

          <div v-if="weaknesses.length" class="report-block">
            <h4 class="sec">不足与提升</h4>
            <ul class="list">
              <li v-for="(w, i) in weaknesses" :key="i">{{ w }}</li>
            </ul>
          </div>

          <div v-if="suggestions.length" class="report-block">
            <h4 class="sec">改进建议</h4>
            <ul class="list">
              <li v-for="(sg, i) in suggestions" :key="i">{{ sg }}</li>
            </ul>
          </div>

          <!-- 画像更新提案 -->
          <template v-if="proposals.length">
            <h4 class="sec">待确认画像更新（{{ proposals.length }}）</h4>
            <div v-for="p in proposals" :key="p.id" class="proposal">
              <div class="p-head">
                <el-tag size="small">{{ changeLabel(p.change_type) }}</el-tag>
                <el-tag size="small" :type="statusType(p.status)">{{ statusLabel(p.status) }}</el-tag>
              </div>
              <div class="p-val">{{ p.after_value }}</div>
              <div v-if="p.reason" class="p-reason">{{ p.reason }}</div>
              <div v-if="p.status === 'pending'" class="p-actions">
                <el-button size="small" type="success" @click="act(p.id, 'accept')">采纳</el-button>
                <el-button size="small" @click="act(p.id, 'defer')">稍后</el-button>
                <el-button size="small" type="danger" @click="act(p.id, 'reject')">拒绝</el-button>
              </div>
            </div>
          </template>
          <div v-else-if="loadedProposals" class="empty">本场暂无待确认提案</div>
        </section>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, AlertCircle } from 'lucide-vue-next'
import AppNav from '../components/AppNav.vue'
import { startInterview, submitInterviewAnswer, getInterviewReport } from '../api/interview'
import { listProposals, actOnProposal } from '../api/profile'
import type { ProfileUpdateProposal } from '../types'

const phase = ref<'prepare' | 'conduct' | 'report'>('prepare')
const position = ref('')
const maxTurns = ref(8)
const starting = ref(false)
const startError = ref('')
const interviewId = ref('')
const currentQuestion = ref('')
const turnCount = ref(0)
const answer = ref('')
const submitting = ref(false)
const conductError = ref('')
const report = ref<Record<string, unknown>>({})
const proposals = ref<ProfileUpdateProposal[]>([])
const loadedProposals = ref(false)

const steps = [
  { key: 'prepare', label: '准备' },
  { key: 'conduct', label: '进行' },
  { key: 'report', label: '报告' },
] as const

const stepIndex = computed(() => steps.findIndex((s) => s.key === phase.value))
const currentTurn = computed(() => Math.min(turnCount.value + 1, maxTurns.value))

// ─── 报告结构化字段（可选链容错）───
const overallScore = computed(() => (typeof report.value.overall_score === 'number' ? report.value.overall_score : null))
const summary = computed(() => (typeof report.value.summary === 'string' ? report.value.summary : ''))
const targetPosition = computed(() => (typeof report.value.target_position === 'string' ? report.value.target_position : ''))
const suggestions = computed<string[]>(() => asStringArray(report.value.suggestions))
const strengths = computed<string[]>(() => asStringArray(report.value.strengths))
const weaknesses = computed<string[]>(() => asStringArray(report.value.weaknesses))
const dimensionList = computed(() => {
  const ds = report.value.dimension_scores
  if (typeof ds !== 'object' || ds == null) return []
  return Object.entries(ds as Record<string, unknown>).map(([key, val]) => ({
    key,
    value: typeof val === 'number' ? val : Number(val) || 0,
  }))
})
const hasReport = computed(
  () =>
    overallScore.value != null ||
    !!summary.value ||
    strengths.value.length > 0 ||
    weaknesses.value.length > 0 ||
    suggestions.value.length > 0 ||
    dimensionList.value.length > 0,
)

function asStringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return []
  return v.filter((x): x is string => typeof x === 'string')
}

function dimWidth(v: number) {
  const p = (v / 10) * 100
  return `${Math.min(100, Math.max(0, p)).toFixed(1)}%`
}

function restart() {
  phase.value = 'prepare'
  startError.value = ''
  conductError.value = ''
  answer.value = ''
  report.value = {}
  proposals.value = []
  loadedProposals.value = false
  interviewId.value = ''
  currentQuestion.value = ''
  turnCount.value = 0
}

// 若报告为空，尝试用 getReport 补充（后台评估服务可能晚于响应返回）
async function fetchReport() {
  try {
    const res = await getInterviewReport(interviewId.value)
    const fetched = res.data || {}
    if (Object.keys(fetched).length) report.value = fetched
  } catch {
    /* 静默：已有 report 或兜底展示 */
  }
}

async function onStart() {
  if (!position.value.trim()) {
    startError.value = '请填写目标岗位'
    return
  }
  starting.value = true
  startError.value = ''
  try {
    const res = await startInterview({
      jd_analysis: { job_title: position.value, summary: position.value, requirements: [], nice_to_have: [] },
      profile: {},
      max_turns: maxTurns.value,
    })
    interviewId.value = res.data.interview_id
    currentQuestion.value = res.data.question
    turnCount.value = 0
    phase.value = 'conduct'
  } catch {
    startError.value = '无法开始面试，请确认后端已启动'
  } finally {
    starting.value = false
  }
}

async function onAnswer() {
  if (!answer.value.trim()) return
  submitting.value = true
  conductError.value = ''
  try {
    const res = await submitInterviewAnswer(interviewId.value, answer.value)
    turnCount.value += 1
    answer.value = ''
    if (res.data.is_complete) {
      report.value = (res.data.report || {}) as Record<string, unknown>
      phase.value = 'report'
      if (!hasReport.value) await fetchReport()
    } else if (res.data.question) {
      currentQuestion.value = res.data.question
    }
  } catch {
    conductError.value = '提交失败，请重试'
  } finally {
    submitting.value = false
  }
}

async function loadProposals() {
  loadedProposals.value = true
  try {
    const res = await listProposals(interviewId.value)
    proposals.value = res.data
  } catch {
    proposals.value = []
  }
}

async function act(id: number, action: string) {
  await actOnProposal(id, action)
  const p = proposals.value.find((x) => x.id === id)
  if (p) p.status = action === 'accept' ? 'accepted' : action === 'defer' ? 'deferred' : 'rejected'
  ElMessage.success('已更新')
}

function changeLabel(c: string) {
  return ({ add: '新增', update: '更新', add_evidence: '补充证据', feedback: '表达反馈' } as const)[c] || c
}
function statusLabel(s: string) {
  return ({ pending: '待确认', accepted: '已采纳', rejected: '已拒绝', deferred: '已暂缓' } as const)[s] || s
}
function statusType(s: string) {
  return ({ pending: 'warning', accepted: 'success', rejected: 'info', deferred: 'info' } as const)[s] || 'info'
}
</script>

<style scoped>
.mi-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-page);
}
.mi-titlebar {
  padding: var(--space-6) var(--space-8) var(--space-4);
  border-bottom: var(--border-light);
  background: color-mix(in srgb, var(--color-bg) 92%, white);
}
.mi-title {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: var(--weight-semibold);
  letter-spacing: -0.01em;
  color: var(--color-text-primary);
}
.mi-sub {
  margin: var(--space-1) 0 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.mi-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-8);
}

/* 步骤指示器 */
.mi-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  margin-bottom: var(--space-8);
}
.mi-step {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-secondary);
}
.step-dot {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  border: 1.5px solid var(--color-gray-300);
  background: var(--color-bg);
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  transition: background var(--duration-normal) var(--ease-default),
    border-color var(--duration-normal) var(--ease-default),
    color var(--duration-normal) var(--ease-default);
}
.step-label {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
}
.mi-step.active {
  color: var(--color-accent-600);
}
.mi-step.active .step-dot {
  background: var(--color-accent-600);
  border-color: var(--color-accent-600);
  color: var(--color-bg-elevated);
}
.mi-step.done {
  color: var(--color-accent-600);
}
.mi-step.done .step-dot {
  background: var(--color-accent-50);
  border-color: var(--color-accent-400);
  color: var(--color-accent-600);
}
.mi-step-line {
  width: 44px;
  height: 1.5px;
  background: var(--color-gray-200);
  border-radius: var(--radius-full);
}
.mi-step-line.on {
  background: var(--color-accent-400);
}

.mi-panel {
  max-width: 720px;
  margin: 0 auto;
  background: var(--color-bg);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-6);
}
.mi-h3 {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--space-2);
}
.mi-phase-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
  flex-wrap: wrap;
}
.hint {
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  margin-top: var(--space-1);
}
.mi-progress {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.mi-progress-num {
  font-weight: var(--weight-semibold);
  color: var(--color-accent-600);
}
.mi-progress-hint {
  font-size: var(--text-xs);
  color: var(--color-text-disabled);
}
.mi-question {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  margin-bottom: var(--space-4);
  line-height: var(--leading-relaxed);
  color: var(--color-text-primary);
}
.mi-actions {
  margin-top: var(--space-4);
}
.err {
  color: var(--color-danger-600);
  font-size: var(--text-sm);
  margin-top: var(--space-2);
}

/* 报告：综合分卡 */
.report-summary {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  margin-top: var(--space-4);
  padding: var(--space-5);
  background: var(--color-accent-50);
  border: var(--border-light);
  border-radius: var(--radius-md);
  flex-wrap: wrap;
}
.score-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 84px;
  height: 84px;
  border-radius: var(--radius-full);
  background: var(--color-accent-600);
  color: var(--color-bg-elevated);
}
.score-num {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: var(--weight-semibold);
  line-height: 1;
  letter-spacing: -0.02em;
}
.score-label {
  font-size: var(--text-xs);
  margin-top: var(--space-1);
  opacity: 0.9;
}
.report-meta {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.meta-item {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

/* 报告：空态 */
.report-empty {
  margin-top: var(--space-5);
  padding: var(--space-6);
  text-align: center;
  color: var(--color-text-secondary);
}
.report-empty .empty-icon {
  color: var(--color-gray-400);
  margin-bottom: var(--space-2);
}
.report-empty .empty-text {
  margin: 0;
  font-size: var(--text-sm);
}

/* 报告：区块 */
.report-block {
  margin-top: var(--space-5);
}
.sec {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--space-2);
}
.report-summary-text {
  margin: 0;
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  color: var(--color-text-secondary);
}
.dim-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.dim-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-sm);
}
.dim-name {
  width: 96px;
  flex-shrink: 0;
  color: var(--color-text-secondary);
}
.dim-bar {
  flex: 1;
  height: 8px;
  background: var(--color-gray-100);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.dim-fill {
  display: block;
  height: 100%;
  border-radius: var(--radius-full);
  background: var(--color-accent-500);
}
.dim-score {
  width: 36px;
  flex-shrink: 0;
  text-align: right;
  color: var(--color-text-primary);
  font-weight: var(--weight-semibold);
}
.list {
  margin: 0;
  padding-left: var(--space-5);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}
.list li {
  margin-bottom: var(--space-1);
}

/* 提案 */
.proposal {
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  margin-bottom: var(--space-3);
  background: var(--color-bg);
}
.p-head {
  display: flex;
  gap: var(--space-1);
}
.p-val {
  margin-top: var(--space-2);
  font-size: var(--text-base);
  color: var(--color-text-primary);
}
.p-reason {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-top: var(--space-1);
  line-height: var(--leading-relaxed);
}
.p-actions {
  margin-top: var(--space-3);
  display: flex;
  gap: var(--space-2);
}
.empty {
  margin-top: var(--space-3);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
}

/* 转场 */
.mi-fade-enter-active,
.mi-fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-default),
    transform var(--duration-normal) var(--ease-default);
}
.mi-fade-enter-from,
.mi-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
