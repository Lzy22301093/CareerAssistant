<template>
  <div class="match-layout">
    <!-- 左：匹配历史 -->
    <aside class="history-rail">
      <div class="history-header">
        <h3 class="history-title">匹配历史</h3>
        <el-tag v-if="tasks.length" size="small" type="info" disable-transitions>{{ tasks.length }}</el-tag>
      </div>
      <button class="new-match-btn" @click="openCreate">
        <Plus :size="16" />
        新建匹配
      </button>
      <div class="history-body">
        <div v-if="loading" class="pad">
          <SkeletonLoader v-for="i in 2" :key="i" variant="card" :lines="2" style="margin-bottom: 12px" />
        </div>
        <div v-else-if="tasks.length === 0" class="history-empty">
          <p class="empty-title">暂无匹配记录</p>
          <p class="empty-hint">在右侧粘贴岗位 JD，开始第一次匹配分析。</p>
        </div>
        <div
          v-for="t in tasks"
          :key="t.id"
          class="history-item"
          :class="{ active: currentTask?.id === t.id }"
          @click="selectTask(t)"
        >
          <div class="history-item-title">{{ t.company }} · {{ t.posting_title }}</div>
          <div class="history-item-meta">
            <span>{{ formatDate(t.updated_at) }}</span>
            <span class="score-num" :class="scoreClass(t.score)">{{ t.score ?? '—' }}</span>
            <el-button size="small" link type="primary" @click.stop="selectTask(t)">详情</el-button>
            <el-button size="small" link type="danger" @click.stop="onDelete(t)">删除</el-button>
          </div>
        </div>
      </div>
    </aside>

    <!-- 右：新建 / 结果 -->
    <section class="match-main">
      <!-- 空态 -->
      <div v-if="!currentTask" class="match-empty">
        <button class="upload-card" @click="openCreate">
          <div class="upload-badge"><Plus :size="22" /></div>
          <p class="upload-title">上传岗位 JD</p>
          <p class="empty-hint">开始一次新的匹配分析</p>
        </button>
      </div>

      <!-- 结果 -->
      <template v-else>
        <div class="result-header">
          <span class="dot" />
          <h3 class="result-title">{{ currentTask.company }} · {{ currentTask.posting_title }}</h3>
          <el-tag size="small" :type="stageTagType" disable-transitions>{{ stageLabel }}</el-tag>
          <el-tag v-if="currentTask.score !== null" size="small" type="warning" disable-transitions>
            SCORE {{ currentTask.score }}
          </el-tag>
        </div>

        <div class="result-body">
          <el-alert
            v-if="currentTask.stage === 'failed'"
            type="error"
            :closable="false"
            :title="currentTask.summary?.error || '匹配分析失败'"
          >
            <el-button size="small" type="primary" plain :loading="running" @click="run">重新分析</el-button>
          </el-alert>

          <template v-if="summary">
            <!-- 总评分数 -->
            <div class="score-panel">
              <div class="score-big" :class="scoreClass(currentTask.score)">{{ currentTask.score ?? '—' }}<span class="score-unit">/100</span></div>
              <div class="score-explain">
                <p class="score-line">匹配分数越高代表简历与岗位要求越接近；下方按缺口类别解释分数构成。</p>
              </div>
            </div>

            <!-- 阶段历史 -->
            <div class="stage-row">
              <div v-for="(s, i) in summary.stage_history ?? []" :key="i" class="stage-step" :class="s.status">
                <span class="stage-idx">{{ String(i + 1).padStart(2, '0') }}</span>
                <span class="stage-name">{{ s.step }}</span>
                <span class="stage-status">{{ s.status === 'done' ? '✓' : s.status === 'failed' ? '✕' : '…' }}</span>
              </div>
            </div>

            <!-- 优势 -->
            <div v-if="summary.strengths?.length" class="block">
              <h4 class="block-title success">核心优势</h4>
              <ul class="plain-list">
                <li v-for="(s, i) in summary.strengths" :key="i">{{ s }}</li>
              </ul>
            </div>

            <!-- 缺口（分数维度解释） -->
            <div v-if="summary.gaps?.length" class="block">
              <h4 class="block-title danger">差距与维度解释</h4>
              <el-table :data="summary.gaps" size="small">
                <el-table-column prop="category" label="维度" width="110" />
                <el-table-column prop="requirement" label="岗位要求" min-width="160" />
                <el-table-column prop="gap_severity" label="严重度" width="90">
                  <template #default="{ row }">
                    <el-tag size="small" :type="row.gap_severity === 'critical' ? 'danger' : row.gap_severity === 'major' ? 'warning' : 'info'" disable-transitions>
                      {{ row.gap_severity === 'critical' ? '严重' : row.gap_severity === 'major' ? '较大' : '轻微' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="suggestion" label="补强建议" min-width="180" />
              </el-table>
            </div>

            <!-- 建议 -->
            <div v-if="summary.recommendations?.length" class="block">
              <h4 class="block-title">行动建议</h4>
              <ul class="plain-list">
                <li v-for="(r, i) in summary.recommendations" :key="i">{{ r }}</li>
              </ul>
            </div>

            <!-- 定向简历草稿 -->
            <div v-if="summary.draft" class="block">
              <div class="draft-head">
                <h4 class="block-title">定向简历草稿</h4>
                <el-button size="small" type="primary" plain :loading="exporting" @click="onExportDraft">
                  导入简历库
                </el-button>
              </div>
              <div class="draft-preview">
                <div v-for="(sec, i) in summary.draft.sections ?? []" :key="i" class="draft-section">
                  <p class="draft-section-title">{{ sec.title }}</p>
                  <p class="draft-section-content">{{ sec.content }}</p>
                </div>
              </div>
            </div>
          </template>
        </div>
      </template>
    </section>

    <!-- 新建匹配弹窗（对照参考图 02） -->
    <el-dialog v-model="createVisible" title="岗位匹配 · 新建" width="640px" :close-on-click-modal="false">
      <p class="empty-hint" style="margin-bottom: 16px">填写岗位信息，AI 将基于岗位 JD 与你的已确认画像做匹配分析</p>
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="公司名称" required>
            <el-input v-model="form.company" placeholder="如：tiktok" maxlength="100" />
          </el-form-item>
          <el-form-item label="岗位名称" required>
            <el-input v-model="form.title" placeholder="如：agent开发" maxlength="100" />
          </el-form-item>
        </div>
        <el-form-item label="岗位 JD 原文" required>
          <el-input v-model="form.jdText" type="textarea" :rows="8" placeholder="粘贴完整 JD（职责、任职要求等），内容越完整分析越准确" />
        </el-form-item>
        <el-form-item label="简历页数偏好">
          <div class="pref-grid">
            <button class="pref-card" :class="{ active: form.pagePreference === 'one_page' }" type="button" @click="form.pagePreference = 'one_page'">
              <span class="pref-name">1 页简历（推荐）</span>
              <span class="pref-desc">自动压缩到 1 页；排版压缩 → 内容精简 → 降级到标准模板</span>
            </button>
            <button class="pref-card" :class="{ active: form.pagePreference === 'two_pages' }" type="button" @click="form.pagePreference = 'two_pages'">
              <span class="pref-name">可接受 2 页</span>
              <span class="pref-desc">保留原模板与完整内容</span>
            </button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="running" :disabled="!formValid" @click="onCreateAndRun">
          {{ running ? '分析中…（约 1-3 分钟）' : '开始匹配分析' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Plus } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import SkeletonLoader from '../SkeletonLoader.vue'
import { createMatchTask, createPosting, deleteMatchTask, exportMatchDraft, listMatchTasks, runMatching } from '../../api/matching'
import type { MatchTaskVO } from '../../types'

const router = useRouter()

const tasks = ref<MatchTaskVO[]>([])
const currentTask = ref<MatchTaskVO | null>(null)
const loading = ref(false)
const running = ref(false)
const exporting = ref(false)
const createVisible = ref(false)

const form = reactive({ company: '', title: '', jdText: '', pagePreference: 'one_page' as 'one_page' | 'two_pages' })

const formValid = computed(() => form.company.trim() && form.title.trim() && form.jdText.trim())
const summary = computed(() => currentTask.value?.summary ?? null)
const stageLabel = computed(() => {
  const map: Record<string, string> = { created: '待分析', analyzing: '分析中', done: '已完成', failed: '失败' }
  return map[currentTask.value?.stage ?? ''] ?? currentTask.value?.stage
})
const stageTagType = computed(() => {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    done: 'success',
    analyzing: 'warning',
    failed: 'danger',
    created: 'info',
  }
  return map[currentTask.value?.stage ?? ''] ?? 'info'
})

function scoreClass(score: number | null) {
  if (score === null || score === undefined) return ''
  if (score >= 75) return 'high'
  if (score >= 50) return 'mid'
  return 'low'
}

function formatDate(value: string | null) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function load() {
  loading.value = true
  try {
    tasks.value = await listMatchTasks()
    if (currentTask.value) {
      const fresh = tasks.value.find((t) => t.id === currentTask.value?.id)
      if (fresh) currentTask.value = fresh
      else currentTask.value = null
    }
  } catch (err: unknown) {
    ElMessage.error(extractError(err, '匹配历史加载失败'))
  } finally {
    loading.value = false
  }
}

function selectTask(t: MatchTaskVO) {
  currentTask.value = t
}

function openCreate() {
  form.company = ''
  form.title = ''
  form.jdText = ''
  form.pagePreference = 'one_page'
  createVisible.value = true
}

async function onCreateAndRun() {
  if (!formValid.value || running.value) return
  running.value = true
  try {
    const posting = await createPosting({ company: form.company.trim(), title: form.title.trim(), jd_text: form.jdText.trim() })
    const task = await createMatchTask({ job_posting_id: posting.id, page_preference: form.pagePreference })
    createVisible.value = false
    currentTask.value = task
    await run()
  } catch (err: unknown) {
    ElMessage.error(extractError(err, '创建匹配任务失败'))
  } finally {
    running.value = false
  }
}

async function run() {
  if (!currentTask.value || running.value) return
  running.value = true
  try {
    currentTask.value = await runMatching(currentTask.value.id)
    await load()
    ElMessage.success(`匹配完成，得分 ${currentTask.value.score ?? '—'}`)
  } catch (err: unknown) {
    ElMessage.error(extractError(err, '匹配分析失败'))
    await load()
  } finally {
    running.value = false
  }
}

async function onDelete(t: MatchTaskVO) {
  try {
    await ElMessageBox.confirm('删除该匹配记录？岗位 JD 资产保留。', '删除匹配', { type: 'warning' })
  } catch {
    return
  }
  await deleteMatchTask(t.id)
  if (currentTask.value?.id === t.id) currentTask.value = null
  await load()
}

async function onExportDraft() {
  if (!currentTask.value) return
  exporting.value = true
  try {
    const doc = await exportMatchDraft(currentTask.value.id)
    ElMessage.success(`已导入简历库「${doc.title}」，可继续区域改写`)
    void router.push('/resume-library')
  } catch (err: unknown) {
    ElMessage.error(extractError(err, '导入简历库失败'))
  } finally {
    exporting.value = false
  }
}

function extractError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail || fallback
}

onMounted(load)
</script>

<style scoped>
.match-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  height: 100%;
  min-height: 0;
}
.history-rail {
  border-right: var(--border-light);
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--color-bg);
}
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  border-bottom: var(--border-light);
}
.history-title {
  margin: 0;
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
}
.new-match-btn {
  margin: var(--space-3) var(--space-4) 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: 10px;
  border: 1px dashed var(--el-color-primary);
  border-radius: var(--radius-md);
  background: var(--el-color-primary-light-9, #eff6ff);
  color: var(--el-color-primary);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  cursor: pointer;
}
.new-match-btn:hover {
  filter: brightness(0.98);
}
.history-body {
  flex: 1;
  overflow: auto;
  padding: var(--space-3) var(--space-4);
}
.history-empty {
  text-align: center;
  padding: var(--space-6) 0;
}
.history-item {
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-2);
  cursor: pointer;
}
.history-item:hover {
  border-color: var(--color-accent-400, #60a5fa);
}
.history-item.active {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary) inset;
}
.history-item-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  margin-bottom: var(--space-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-item-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-2xs, 11px);
  color: var(--color-text-secondary);
}
.score-num {
  font-family: var(--font-mono);
  font-weight: var(--weight-semibold);
}
.score-num.high {
  color: var(--el-color-success);
}
.score-num.mid {
  color: var(--el-color-warning);
}
.score-num.low {
  color: var(--el-color-danger);
}
.match-main {
  min-height: 0;
  overflow: auto;
  background: var(--color-bg-page, #f8fafc);
}
.match-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.upload-card {
  border: 2px dashed var(--color-gray-300, #d1d5db);
  border-radius: var(--radius-lg, 8px);
  background: var(--color-bg);
  padding: var(--space-8) var(--space-10);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
}
.upload-card:hover {
  border-color: var(--el-color-primary);
}
.upload-badge {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-full);
  background: var(--color-text-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.upload-title {
  margin: 0;
  font-weight: var(--weight-semibold);
}
.result-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--color-bg);
  border-bottom: 2px solid var(--el-color-primary);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--el-color-primary);
}
.result-title {
  margin: 0;
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
}
.result-body {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 920px;
}
.score-panel {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  background: var(--color-bg);
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}
.score-big {
  font-size: 40px;
  font-family: var(--font-mono);
  font-weight: var(--weight-semibold);
  line-height: 1;
}
.score-big.high {
  color: var(--el-color-success);
}
.score-big.mid {
  color: var(--el-color-warning);
}
.score-big.low {
  color: var(--el-color-danger);
}
.score-unit {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.score-line {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: 1.7;
}
.stage-row {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.stage-step {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 4px 10px;
  border-radius: var(--radius-full);
  border: var(--border-light);
  background: var(--color-bg);
  font-size: var(--text-sm);
}
.stage-step.done {
  border-color: var(--el-color-success);
  color: var(--el-color-success);
}
.stage-step.failed {
  border-color: var(--el-color-danger);
  color: var(--el-color-danger);
}
.stage-step.running {
  border-color: var(--el-color-warning);
  color: var(--el-color-warning);
}
.stage-idx {
  font-family: var(--font-mono);
  font-size: var(--text-2xs, 11px);
}
.block {
  background: var(--color-bg);
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}
.block-title {
  margin: 0 0 var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
}
.block-title.success {
  color: var(--el-color-success);
}
.block-title.danger {
  color: var(--el-color-danger);
}
.plain-list {
  margin: 0;
  padding-left: 18px;
  font-size: var(--text-sm);
  line-height: 1.9;
  color: var(--color-text-primary);
}
.draft-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.draft-preview {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.draft-section-title {
  margin: 0 0 var(--space-1);
  font-weight: var(--weight-semibold);
  font-size: var(--text-sm);
}
.draft-section-content {
  margin: 0;
  font-size: var(--text-sm);
  line-height: 1.8;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}
.pref-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  width: 100%;
}
.pref-card {
  border: var(--border-medium, 1px solid var(--color-border-strong, #d1d5db));
  border-radius: var(--radius-md);
  padding: var(--space-3);
  text-align: left;
  background: var(--color-bg);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.pref-card.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9, #eff6ff);
}
.pref-name {
  font-weight: var(--weight-semibold);
  font-size: var(--text-sm);
}
.pref-desc {
  font-size: var(--text-2xs, 11px);
  color: var(--color-text-secondary);
  line-height: 1.5;
}
.pad {
  padding: var(--space-2);
}
</style>
