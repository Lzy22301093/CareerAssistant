<template>
  <div class="app-page">
    <AppNav>
      <el-button type="primary" @click="openCreate">
        <Plus :size="16" />新增投递
      </el-button>
    </AppNav>
    <div class="app-titlebar">
      <div class="app-title">投递记录册</div>
      <p class="app-sub">跟进每一份投递的进展与结果</p>
    </div>

    <div class="app-body">
      <section class="app-panel">
        <!-- 汇总卡 -->
        <div class="app-summary">
          <template v-if="summaryLoading">
            <SkeletonLoader variant="text" :lines="1" />
          </template>
          <template v-else>
            <span class="sum-item"><b>{{ summary.total }}</b> 条记录</span>
            <span class="sum-item"><b class="congo">{{ summary.by_result?.ongoing ?? 0 }}</b> 进行中</span>
            <span class="sum-item"><b class="cpass">{{ summary.by_result?.passed ?? 0 }}</b> 通过</span>
            <span class="sum-item"><b class="cfail">{{ summary.by_result?.failed ?? 0 }}</b> 未通过</span>
            <span v-if="(summary.by_result?.ongoing ?? 0) > 0" class="remind">
              <Clock :size="14" />有 {{ summary.by_result?.ongoing ?? 0 }} 个投递仍在进行中，记得及时更新状态
            </span>
          </template>
        </div>

        <!-- 搜索 + 筛选 -->
        <div class="app-filters">
          <el-input v-model="q" placeholder="按公司或岗位模糊搜索" clearable style="max-width: 300px" @change="reload">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
        <div class="app-filter-row">
          <span class="flabel">状态</span>
          <el-check-tag
            v-for="st in statusOptions"
            :key="st.value"
            :checked="statusFilter === st.value"
            @change="setStatus(st.value)"
          >{{ st.label }}</el-check-tag>
        </div>
        <div class="app-filter-row">
          <span class="flabel">结果</span>
          <el-check-tag
            v-for="rt in resultOptions"
            :key="rt.value"
            :checked="resultFilter === rt.value"
            @change="setResult(rt.value)"
          >{{ rt.label }}</el-check-tag>
        </div>

        <!-- 列表 -->
        <SkeletonLoader v-if="listLoading" variant="table" :rows="5" />
        <el-table v-else :data="items" class="app-table">
          <template #empty>
            <div class="table-empty">
              <Inbox :size="36" class="empty-icon" />
              <p class="empty-text">暂无投递记录，点击右上角「新增投递」记录一条</p>
            </div>
          </template>
          <el-table-column prop="company" label="公司" min-width="140" />
          <el-table-column prop="job_title" label="岗位" min-width="160" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="结果" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="resultTagType(row.result)">{{ resultLabel(row.result) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="投递时间" width="180">
            <template #default="{ row }">{{ formatDate(row.applied_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130" align="right">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" text type="danger" @click="onDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </div>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑投递记录' : '新增投递记录'" width="480px">
      <el-form label-width="80px">
        <el-form-item label="公司" required>
          <el-input v-model="form.company" placeholder="如：字节跳动" />
        </el-form-item>
        <el-form-item label="岗位" required>
          <el-input v-model="form.job_title" placeholder="如：后端开发工程师" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option v-for="st in statusOptions.filter((o) => o.value !== '')" :key="st.value" :label="st.label" :value="st.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Clock, Inbox } from 'lucide-vue-next'
import AppNav from '../components/AppNav.vue'
import SkeletonLoader from '../components/SkeletonLoader.vue'
import {
  createApplication,
  deleteApplication,
  getApplicationSummary,
  listApplications,
  updateApplication,
} from '../api/applications'
import type {
  JobApplication,
  JobApplicationStatus,
  JobApplicationSummary,
} from '../types'

const items = ref<JobApplication[]>([])
const summary = ref<JobApplicationSummary>({ total: 0, by_status: {}, by_result: { ongoing: 0, passed: 0, failed: 0 } })
const listLoading = ref(false)
const summaryLoading = ref(false)
const q = ref('')
const statusFilter = ref('')
const resultFilter = ref('')

const statusOptions = [
  { label: '全部', value: '' },
  { label: '已投递', value: 'applied' },
  { label: '笔试中', value: 'written_test' },
  { label: '面试中', value: 'interview' },
  { label: '通过', value: 'offer' },
  { label: '未通过', value: 'rejected' },
]
const resultOptions = [
  { label: '全部', value: '' },
  { label: '进行中', value: 'ongoing' },
  { label: '通过', value: 'passed' },
  { label: '未通过', value: 'failed' },
]

const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref<JobApplication | null>(null)
const form = reactive({ company: '', job_title: '', status: 'applied' as JobApplicationStatus, notes: '' })

async function loadList() {
  listLoading.value = true
  try {
    const res = await listApplications(q.value.trim() || undefined, statusFilter.value || undefined, resultFilter.value || undefined)
    items.value = res.data
  } catch {
    items.value = []
    ElMessage.error('投递记录加载失败，请重试')
  } finally {
    listLoading.value = false
  }
}

async function loadSummary() {
  summaryLoading.value = true
  try {
    const res = await getApplicationSummary()
    summary.value = res.data
  } catch {
    summary.value = { total: 0, by_status: {}, by_result: { ongoing: 0, passed: 0, failed: 0 } }
  } finally {
    summaryLoading.value = false
  }
}

// 列表与汇总各自持有 loading 态；互不阻塞
function reload() {
  loadList()
  loadSummary()
}

function setStatus(v: string) {
  statusFilter.value = v
  reload()
}
function setResult(v: string) {
  resultFilter.value = v
  reload()
}

function openCreate() {
  editing.value = null
  form.company = ''
  form.job_title = ''
  form.status = 'applied'
  form.notes = ''
  dialogVisible.value = true
}

function openEdit(row: JobApplication) {
  editing.value = row
  form.company = row.company ?? ''
  form.job_title = row.job_title ?? ''
  form.status = row.status
  form.notes = row.notes ?? ''
  dialogVisible.value = true
}

async function onSave() {
  if (!form.company.trim() || !form.job_title.trim()) {
    ElMessage.warning('请填写公司与岗位')
    return
  }
  saving.value = true
  const payload = { company: form.company.trim(), job_title: form.job_title.trim(), status: form.status, notes: form.notes }
  try {
    if (editing.value) {
      await updateApplication(editing.value.id, payload)
      ElMessage.success('已更新')
    } else {
      await createApplication(payload)
      ElMessage.success('已新增投递')
    }
    dialogVisible.value = false
    await reload()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    saving.value = false
  }
}

async function onDelete(row: JobApplication) {
  try {
    await ElMessageBox.confirm(`删除「${row.company} · ${row.job_title}」这条投递记录？`, '确认删除', { type: 'warning' })
  } catch {
    // 用户取消
    return
  }
  try {
    await deleteApplication(row.id)
    ElMessage.success('已删除')
    await reload()
  } catch {
    ElMessage.error('删除失败，请重试')
  }
}

function statusLabel(s: string) {
  return (statusOptions.find((o) => o.value === s)?.label) ?? s
}
function resultLabel(r: string) {
  return (resultOptions.find((o) => o.value === r)?.label) ?? r
}
function statusTagType(s: string) {
  return ({ applied: 'info', written_test: 'warning', interview: 'primary', offer: 'success', rejected: 'danger' } as const)[s] ?? 'info'
}
function resultTagType(r: string) {
  return ({ ongoing: 'warning', passed: 'success', failed: 'danger' } as const)[r] ?? 'info'
}
function formatDate(s?: string | null) {
  if (!s) return '-'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

onMounted(reload)
</script>

<style scoped>
.app-page { min-height: 100vh; display: flex; flex-direction: column; background: var(--color-bg-page); }
.app-titlebar {
  padding: var(--space-6) var(--space-8) var(--space-4);
  border-bottom: var(--border-light);
  background: color-mix(in srgb, var(--color-bg) 92%, white);
}
.app-title {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: var(--weight-semibold);
  letter-spacing: -0.01em;
  color: var(--color-text-primary);
}
.app-sub {
  margin: var(--space-1) 0 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.app-body { flex: 1; overflow-y: auto; padding: var(--space-8); }
.app-panel {
  max-width: 900px;
  margin: 0 auto;
  background: var(--color-bg);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-6);
}

/* 汇总卡 */
.app-summary {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
  padding: var(--space-4) var(--space-5);
  background: var(--color-gray-50);
  border: var(--border-light);
  border-radius: var(--radius-md);
}
.sum-item { color: var(--color-text-secondary); font-size: var(--text-sm); }
.sum-item b { margin-right: 2px; color: var(--color-text-primary); font-weight: var(--weight-semibold); }
.congo { color: var(--color-warning-600); }
.cpass { color: var(--color-success-600); }
.cfail { color: var(--color-danger-600); }
.remind {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--text-xs);
  color: var(--color-warning-600);
}

/* 筛选 */
.app-filters { display: flex; margin-bottom: var(--space-3); }
.app-filter-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  flex-wrap: wrap;
}
.flabel { width: 40px; color: var(--color-text-secondary); font-size: var(--text-sm); }

/* 表格（呼吸感行距） */
.app-table { width: 100%; }
.app-table :deep(.el-table__cell) {
  padding: var(--space-3) 0;
}
.table-empty {
  padding: var(--space-8) 0;
  text-align: center;
  color: var(--color-text-secondary);
}
.table-empty .empty-icon {
  color: var(--color-gray-400);
  margin-bottom: var(--space-2);
}
.table-empty .empty-text {
  margin: 0;
  font-size: var(--text-sm);
}
</style>
