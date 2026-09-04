<template>
  <div class="mi-page">
    <AppNav>
      <el-button text @click="phase = 'prepare'">重开面试</el-button>
    </AppNav>
    <div class="mi-titlebar"><div class="mi-title">AI 模拟面试</div></div>

    <div class="mi-body">
      <!-- 准备页 -->
      <section v-if="phase === 'prepare'" class="mi-panel">
        <h3>面试前准备</h3>
        <p class="hint">输入目标岗位，选择轮数，AI 将基于你的画像与简历出题。</p>
        <el-form label-width="88px" style="max-width: 520px">
          <el-form-item label="目标岗位">
            <el-input v-model="position" placeholder="如：后端开发实习生" />
          </el-form-item>
          <el-form-item label="轮数">
            <el-input-number v-model="maxTurns" :min="3" :max="20" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="starting" @click="onStart">开始面试</el-button>
          </el-form-item>
        </el-form>
        <p v-if="startError" class="err">{{ startError }}</p>
      </section>

      <!-- 进行页 -->
      <section v-else-if="phase === 'conduct'" class="mi-panel">
        <div class="mi-progress">第 {{ turnCount }} / {{ maxTurns }} 轮</div>
        <div class="mi-question">{{ currentQuestion }}</div>
        <el-input
          v-model="answer"
          type="textarea"
          :rows="5"
          placeholder="输入你的回答…"
        />
        <div class="mi-actions">
          <el-button type="primary" :loading="submitting" @click="onAnswer">提交回答</el-button>
        </div>
        <p v-if="conductError" class="err">{{ conductError }}</p>
      </section>

      <!-- 报告页 -->
      <section v-else class="mi-panel">
        <h3>面试报告</h3>
        <el-button type="primary" @click="loadProposals">查看画像更新提案</el-button>
        <div class="report-block">
          <pre class="report-json">{{ reportText }}</pre>
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
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppNav from '../components/AppNav.vue'
import { startInterview, submitInterviewAnswer } from '../api/interview'
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
const reportText = computed(() => JSON.stringify(report.value, null, 2))
const report = ref<Record<string, unknown>>({})
const proposals = ref<ProfileUpdateProposal[]>([])
const loadedProposals = ref(false)

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
  } catch (e) {
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
    } else if (res.data.question) {
      currentQuestion.value = res.data.question
    }
  } catch (e) {
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
  padding: var(--space-4) var(--space-6);
  border-bottom: var(--border-light);
  background: var(--color-bg);
}
.mi-title {
  font-size: var(--text-lg, 16px);
  font-weight: var(--weight-semibold);
}
.mi-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-8);
}
.mi-panel {
  max-width: 720px;
  margin: 0 auto;
  background: var(--color-bg);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: var(--space-6);
}
.hint {
  color: var(--color-text-secondary);
  font-size: 13px;
  margin-top: 4px;
}
.mi-progress {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}
.mi-question {
  font-size: 16px;
  font-weight: var(--weight-semibold);
  margin-bottom: 12px;
  line-height: 1.5;
}
.mi-actions {
  margin-top: 12px;
}
.err {
  color: var(--color-danger, #dc2626);
  font-size: 13px;
  margin-top: 8px;
}
.report-block {
  margin-top: 16px;
}
.report-json {
  background: var(--color-gray-50, #f9fafb);
  border-radius: 8px;
  padding: 12px;
  white-space: pre-wrap;
  font-family: var(--font-mono, monospace);
  font-size: 12px;
}
.sec {
  margin-top: 24px;
}
.proposal {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
}
.p-head {
  display: flex;
  gap: 6px;
}
.p-val {
  margin-top: 6px;
  font-size: 14px;
}
.p-reason {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.p-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
.empty {
  margin-top: 12px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
</style>
