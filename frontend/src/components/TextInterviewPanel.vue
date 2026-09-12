<template>
  <div class="ti-panel">
    <div class="ti-titlebar">
      <div class="ti-title">AI 模拟面试 · 文字版</div>
      <p class="ti-sub">准备 → 作答 → 报告，一场结构化面试</p>
    </div>

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

      <section v-else-if="phase === 'conduct'" key="conduct" class="mi-panel">
        <div class="mi-progress">
          <span class="mi-progress-num">第 {{ currentTurn }} / {{ maxTurns }} 轮</span>
          <span class="mi-progress-hint">作答后提交，AI 会逐轮点评并继续追问</span>
        </div>
        <div class="mi-question">{{ currentQuestion || '…' }}</div>
        <el-input v-model="answer" type="textarea" :rows="5" placeholder="输入你的回答…" />
        <div class="mi-actions">
          <el-button type="primary" :loading="submitting" @click="onAnswer">
            {{ submitting ? '正在分析你的回答…' : '提交回答' }}
          </el-button>
        </div>
        <p v-if="conductError" class="err">{{ conductError }}</p>
      </section>

      <section v-else key="report" class="mi-panel">
        <div class="ti-phase-head">
          <h3 class="mi-h3">面试报告</h3>
          <el-button type="primary" plain @click="loadProposals">查看画像更新提案</el-button>
        </div>

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

        <div class="ti-report-actions">
          <el-button @click="restart">再开一场</el-button>
        </div>
      </section>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, AlertCircle } from 'lucide-vue-next'
import { startInterview, submitInterviewAnswer, getInterviewReport } from '../api/interview'
import { listProposals, actOnProposal } from '../api/profile'
import { listProfileItems } from '../api/profile'
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

function changeLabel(t: string) {
  const map: Record<string, string> = {
    add: '新增',
    update: '更新',
    strengthen: '强化',
    feedback: '反馈',
  }
  return map[t] || t
}
function statusLabel(s: string) {
  const map: Record<string, string> = {
    pending: '待确认',
    accepted: '已采纳',
    rejected: '已拒绝',
    deferred: '稍后',
  }
  return map[s] || s
}
function statusType(s: string): 'success' | 'info' | 'warning' | 'danger' {
  if (s === 'accepted') return 'success'
  if (s === 'rejected') return 'danger'
  if (s === 'deferred') return 'warning'
  return 'info'
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

async function loadConfirmedProfile(): Promise<Record<string, unknown>> {
  try {
    const res = await listProfileItems(undefined, 'confirmed')
    const items = res.data || []
    const profile: Record<string, unknown> = {
      skills: [] as string[],
      experience: [] as { title: string; content: string }[],
      education: [] as string[],
      summary: '',
      target_roles: [] as string[],
    }
    for (const it of items) {
      const content = it.content || ''
      if (it.category === 'skill') {
        ;(profile.skills as string[]).push(content || it.title || '')
      } else if (it.category === 'experience') {
        ;(profile.experience as { title: string; content: string }[]).push({
          title: it.title || '',
          content,
        })
      } else if (it.category === 'education') {
        ;(profile.education as string[]).push(`${it.title || ''}: ${content}`.replace(/^: /, ''))
      } else if (it.category === 'soft' && content) {
        profile.summary = content
      } else if (it.category === 'target') {
        ;(profile.target_roles as string[]).push(content || it.title || '')
      } else if (it.category === 'basic_info' && it.title === '姓名') {
        profile.name = content
      }
    }
    return profile
  } catch {
    return {}
  }
}

async function fetchReport() {
  try {
    const res = await getInterviewReport(interviewId.value)
    const fetched = res.data || {}
    if (Object.keys(fetched).length) report.value = fetched
  } catch {
    /* 静默 */
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
    const profile = await loadConfirmedProfile()
    const res = await startInterview({
      jd_analysis: {
        job_title: position.value,
        company: '',
        summary: position.value,
        requirements: [],
        nice_to_have: [],
      },
      profile,
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
      report.value = res.data.report || {}
      phase.value = 'report'
      if (!Object.keys(report.value).length) await fetchReport()
      loadProposals()
    } else {
      currentQuestion.value = res.data.question || '请继续。'
    }
  } catch (e: any) {
    conductError.value = e?.response?.data?.detail || '提交失败，请重试'
  } finally {
    submitting.value = false
  }
}

async function loadProposals() {
  if (!interviewId.value) return
  try {
    const res = await listProposals(interviewId.value)
    proposals.value = res.data || []
    loadedProposals.value = true
  } catch {
    proposals.value = []
    loadedProposals.value = true
  }
}

async function act(id: number, action: string) {
  try {
    await actOnProposal(id, action)
    ElMessage.success(
      action === 'accept' ? '已采纳，画像已更新' : action === 'reject' ? '已拒绝，画像不变' : '已标记稍后处理',
    )
    loadProposals()
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}
</script>

<style scoped>
.ti-panel { display: flex; flex-direction: column; gap: var(--space-4); }
.ti-titlebar { margin-bottom: var(--space-1); }
.ti-title { font-family: var(--font-display); font-size: var(--text-lg); color: var(--color-text-primary); }
.ti-sub { margin: 4px 0 0; color: var(--color-text-secondary); font-size: var(--text-sm); }
.ti-phase-head { display: flex; align-items: center; justify-content: space-between; }
.ti-report-actions { margin-top: var(--space-4); }

.mi-steps { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.mi-step { display: inline-flex; align-items: center; gap: 6px; font-size: var(--text-xs); color: var(--color-text-secondary); }
.mi-step.active { color: var(--color-accent-600); font-weight: 600; }
.step-dot {
  width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center;
  border: 1px solid var(--color-border); font-size: 11px;
}
.mi-step.active .step-dot { border-color: var(--color-accent-600); background: var(--color-accent-50); color: var(--color-accent-600); }
.mi-step.done .step-dot { background: var(--color-accent-600); border-color: var(--color-accent-600); color: #fff; }
.mi-step-line { width: 24px; height: 1px; background: var(--color-border); }
.mi-step-line.on { background: var(--color-accent-400); }

.mi-panel {
  background: var(--color-bg-elevated); border: var(--border-light);
  border-radius: var(--radius-xl); padding: var(--space-5);
}
.mi-h3 { font-family: var(--font-display); margin: 0 0 var(--space-2); }
.hint { color: var(--color-text-secondary); font-size: var(--text-sm); margin: 0 0 var(--space-4); }
.err { color: var(--color-danger-600); font-size: var(--text-sm); }
.mi-progress { display: flex; justify-content: space-between; margin-bottom: var(--space-3); font-size: var(--text-sm); color: var(--color-text-secondary); }
.mi-progress-num { font-weight: 600; color: var(--color-text-primary); }
.mi-question {
  font-size: var(--text-base); line-height: 1.7; padding: var(--space-3);
  background: var(--color-bg-page); border-radius: var(--radius-md); margin-bottom: var(--space-3);
}
.mi-actions { margin-top: var(--space-3); }

.report-summary { display: flex; gap: var(--space-5); align-items: center; margin-bottom: var(--space-4); }
.score-badge {
  width: 88px; height: 88px; border-radius: 50%; display: grid; place-items: center;
  background: var(--color-accent-50); border: 2px solid var(--color-accent-200);
}
.score-num { font-size: var(--text-xl); font-weight: 700; color: var(--color-accent-600); }
.score-label { font-size: 11px; color: var(--color-text-secondary); }
.report-meta .meta-item { margin: 0 0 4px; font-size: var(--text-sm); color: var(--color-text-secondary); }
.report-empty { text-align: center; color: var(--color-text-secondary); padding: var(--space-5); }
.empty-icon { color: var(--color-text-tertiary); }
.empty-text { margin-top: var(--space-2); }
.report-block { margin-bottom: var(--space-4); }
.report-block .sec { margin: 0 0 var(--space-2); font-size: var(--text-sm); font-weight: 600; }
.report-summary-text { margin: 0; color: var(--color-text-secondary); line-height: 1.7; }
.dim-list { display: flex; flex-direction: column; gap: 8px; }
.dim-item { display: grid; grid-template-columns: 72px 1fr 40px; gap: 8px; align-items: center; font-size: var(--text-sm); }
.dim-bar { height: 6px; background: var(--color-gray-100); border-radius: 99px; overflow: hidden; }
.dim-fill { display: block; height: 100%; background: var(--color-accent-500); border-radius: 99px; }
.list { margin: 0; padding-left: 1.2em; color: var(--color-text-secondary); }
.proposal {
  border: var(--border-light); border-radius: var(--radius-md);
  padding: var(--space-3); margin-bottom: var(--space-2);
}
.p-head { display: flex; gap: 6px; margin-bottom: 6px; }
.p-val { font-size: var(--text-sm); color: var(--color-text-primary); }
.p-reason { font-size: var(--text-xs); color: var(--color-text-secondary); margin-top: 4px; }
.p-actions { margin-top: 8px; display: flex; gap: 6px; }
.empty { color: var(--color-text-secondary); font-size: var(--text-sm); }

.mi-fade-enter-active, .mi-fade-leave-active { transition: opacity .2s ease; }
.mi-fade-enter-from, .mi-fade-leave-to { opacity: 0; }
</style>
