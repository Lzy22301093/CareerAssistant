<template>
  <div class="page">
    <AppNav>
      <router-link to="/workspace" class="ghost-link">求职分析</router-link>
    </AppNav>

    <div class="ws-tabs">
      <button class="ws-tab" :class="{ active: tab === 'library' }" @click="tab = 'library'">简历库</button>
      <button class="ws-tab" :class="{ active: tab === 'matching' }" @click="tab = 'matching'">匹配</button>
    </div>

    <MatchWorkspace v-if="tab === 'matching'" />

    <div v-else class="layout">
      <!-- 左：文档列表 / 回收站 -->
      <aside class="doc-rail">
        <div class="rail-header">
          <h2 class="rail-title">{{ recycleMode ? '回收站' : '简历库' }}</h2>
          <div class="rail-actions">
            <el-button size="small" :type="recycleMode ? 'default' : 'primary'" @click="toggleRecycle">
              <Trash2 :size="14" style="margin-right: 4px" />回收站
            </el-button>
            <el-button v-if="!recycleMode" size="small" plain type="primary" @click="uploadInput?.click()">
              <Upload :size="14" style="margin-right: 4px" />上传
            </el-button>
            <el-button v-if="!recycleMode" size="small" plain @click="router.push('/resume-generation')">
              <Wand2 :size="14" style="margin-right: 4px" />生成
            </el-button>
            <input ref="uploadInput" type="file" accept=".pdf,.docx,.txt,.md" hidden @change="onUploadFile" />
          </div>
        </div>

        <div v-if="railLoading" class="rail-body">
          <SkeletonLoader v-for="i in 3" :key="i" variant="card" :lines="2" style="margin-bottom: 12px" />
        </div>
        <div v-else-if="errorMessage" class="rail-body">
          <el-alert type="error" :title="errorMessage" :closable="false">
            <el-button size="small" @click="loadDocs">重试</el-button>
          </el-alert>
        </div>
        <div v-else-if="recycleMode" class="rail-body">
          <p v-if="deletedDocs.length === 0" class="empty-hint">回收站为空</p>
          <div v-for="doc in deletedDocs" :key="doc.id" class="doc-card deleted">
            <div class="doc-card-title">{{ doc.title }}</div>
            <div class="doc-card-meta">删除于 {{ formatDate(doc.deleted_at) }}</div>
            <div class="doc-card-actions">
              <el-button size="small" type="primary" link @click="onRestore(doc)">恢复</el-button>
              <el-button size="small" type="danger" link @click="onPurge(doc)">彻底删除</el-button>
            </div>
          </div>
        </div>
        <div v-else-if="docs.length === 0" class="rail-body">
          <div class="empty-guide">
            <Library :size="32" class="empty-icon" />
            <p class="empty-title">还没有简历</p>
            <p class="empty-hint">这里用于修改已有简历。可从求职分析会话导入、上传文件，或走生成向导</p>
            <div class="empty-actions">
              <el-button size="small" type="primary" plain @click="importDialogVisible = true">从会话导入</el-button>
              <el-button size="small" plain @click="uploadInput?.click()">上传</el-button>
              <el-button size="small" plain @click="router.push('/resume-generation')">去生成</el-button>
            </div>
          </div>
        </div>
        <div v-else class="rail-body">
          <div
            v-for="doc in docs"
            :key="doc.id"
            class="doc-card"
            :class="{ active: currentDoc?.id === doc.id }"
            @click="selectDoc(doc.id)"
          >
            <div class="doc-card-title">{{ doc.title }}</div>
            <div class="doc-card-meta">
              <el-tag size="small" :type="sourceTagType(doc.source)" disable-transitions>{{ sourceLabel(doc.source) }}</el-tag>
              <span>{{ doc.version_count }} 版</span>
              <span>{{ formatDate(doc.updated_at) }}</span>
            </div>
          </div>
          <el-button size="small" text style="width: 100%; margin-top: 8px" @click="importDialogVisible = true">
            <Upload :size="14" style="margin-right: 4px" />从会话导入
          </el-button>
        </div>
      </aside>

      <!-- 中：版本 + 区域预览 -->
      <section class="preview-pane">
        <template v-if="currentDoc">
          <div class="doc-header">
            <div class="doc-title-row">
              <h3 class="doc-title">{{ currentDoc.title }}</h3>
              <el-button size="small" text @click="onRename">
                <Pencil :size="13" style="margin-right: 4px" />重命名
              </el-button>
              <el-button size="small" text type="danger" @click="onDeleteDoc">删除</el-button>
            </div>
            <div class="version-row">
              <span class="version-label">版本：</span>
              <el-tag
                v-for="v in versions"
                :key="v.id"
                class="version-chip"
                :type="v.id === viewedVersionId ? 'primary' : 'info'"
                :effect="v.id === currentDoc.current_version_id ? 'dark' : 'plain'"
                size="small"
                @click="viewedVersionId = v.id"
              >
                v{{ v.version }}{{ v.id === currentDoc.current_version_id ? ' · 当前' : '' }}
              </el-tag>
              <el-radio-group
                v-if="viewedVersion"
                size="small"
                class="page-pref"
                :model-value="pagePref"
                @change="onSetPagePreference"
              >
                <el-radio-button value="one_page">1 页</el-radio-button>
                <el-radio-button value="two_pages">2 页</el-radio-button>
              </el-radio-group>
              <el-button
                v-if="viewedVersion && viewedVersion.id !== currentDoc.current_version_id"
                size="small"
                type="warning"
                plain
                @click="onRollback"
              >
                回滚到此版本
              </el-button>
              <el-button
                size="small"
                :type="boxMode ? 'primary' : 'default'"
                plain
                @click="boxMode = !boxMode"
              >
                <SquareDashedMousePointer :size="13" style="margin-right: 4px" />
                {{ boxMode ? '框选模式（开）' : '框选模式' }}
              </el-button>
              <el-dropdown trigger="click" @command="onExportCommand">
                <el-button size="small" plain :loading="exporting !== ''">
                  <Download :size="13" style="margin-right: 4px" />导出
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="layout" :disabled="exporting !== '' || !canLayoutExport">
                      下载 Word（保排版）{{ canLayoutExport ? '' : '· 无原件' }}
                    </el-dropdown-item>
                    <el-dropdown-item command="docx" :disabled="exporting !== ''">下载 Word（统一模板）</el-dropdown-item>
                    <el-dropdown-item command="html" :disabled="exporting !== ''">下载 HTML（统一模板）</el-dropdown-item>
                    <el-dropdown-item command="md" :disabled="exporting !== ''">下载 Markdown</el-dropdown-item>
                    <el-dropdown-item command="print" :disabled="exporting !== ''" divided>打印 / 另存 PDF</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-tag v-if="canLayoutExport" size="small" type="success" effect="plain" disable-transitions style="margin-left: 6px">
                原版式
              </el-tag>
              <el-tag v-else-if="currentDoc?.source === 'upload'" size="small" type="info" effect="plain" disable-transitions style="margin-left: 6px">
                文本重排
              </el-tag>
            </div>
            <p v-if="boxMode" class="box-hint">在下方简历预览里拖拽框选区域 → 自动选中对应板块并记录选框；点选框右上角 × 可清除</p>
            <p v-if="exportError" class="export-err">{{ exportError }}</p>
          </div>

          <div ref="previewRef" class="preview" @mousedown="onPreviewMouseDown" @mousemove="onPreviewMouseMove" @mouseup="onPreviewMouseUp">
            <div
              v-for="(sec, idx) in viewedSections"
              :key="sec.id"
              :data-section-id="sec.id"
              class="section-card"
              :class="{ selected: sec.id === selectedSectionId }"
              :style="{ '--accent': sectionColor(idx) }"
              @click="selectSection(sec)"
            >
              <div class="section-head">
                <span class="dot" :style="{ background: sectionColor(idx) }" />
                <span class="section-title">{{ sec.title || '（无标题）' }}</span>
                <el-tag size="small" type="info" disable-transitions>{{ typeLabel(sec.section_type) }}</el-tag>
                <span class="section-page">P{{ sec.page_number }}</span>
              </div>
              <p class="section-content">{{ sec.content || '（空）' }}</p>
            </div>

            <!-- 已保存选框覆盖层 -->
            <div
              v-for="sec in boxedSections"
              :key="'box-' + sec.id"
              class="box-overlay"
              :style="{
                left: sec.bounding_box!.x + 'px',
                top: sec.bounding_box!.y + 'px',
                width: sec.bounding_box!.width + 'px',
                height: sec.bounding_box!.height + 'px',
                borderColor: sectionColor(viewedSections.findIndex(s => s.id === sec.id)),
              }"
            >
              <span class="box-label" :style="{ background: sectionColor(viewedSections.findIndex(s => s.id === sec.id)) }">
                {{ sec.title || '区域' }}
              </span>
              <button
                type="button"
                class="box-clear"
                title="清除选框"
                aria-label="清除选框"
                @click.stop="onClearBox(sec)"
              >
                <X :size="12" />
              </button>
            </div>

            <!-- 拖拽选框 -->
            <div
              v-if="dragRect"
              class="drag-rect"
              :style="{
                left: dragRect.x + 'px',
                top: dragRect.y + 'px',
                width: dragRect.width + 'px',
                height: dragRect.height + 'px',
              }"
            />
          </div>
        </template>
        <div v-else-if="!railLoading" class="preview-empty">
          <FileText :size="40" class="empty-icon" />
          <p class="empty-title">从左侧选择一份简历</p>
          <p class="empty-hint">支持多版本管理、区域对话与 AI 改写对比</p>
        </div>
      </section>

      <!-- 右：区域对话 + 改写 -->
      <aside class="chat-pane">
        <template v-if="selectedSection">
          <div class="chat-header">
            <span class="dot" :style="{ background: sectionColor(selectedIndex) }" />
            <span class="chat-title">{{ selectedSection.title || '（无标题）' }}</span>
            <span class="chat-meta">v{{ viewedVersion?.version }} · {{ typeLabel(selectedSection.section_type) }}</span>
          </div>

          <div ref="chatListRef" class="chat-list">
            <div v-if="history.length === 0" class="chat-empty">
              <MessagesSquare :size="28" class="empty-icon" />
              <p class="empty-title">开始这段区域对话</p>
              <p class="empty-hint">AI 已读取整份简历与画像作为背景，输入优化意见即可生成改写候选</p>
            </div>
            <div v-for="(msg, idx) in history" :key="idx" class="chat-msg" :class="msg.role">
              <div class="bubble">{{ msg.content }}</div>
            </div>
            <div v-if="rewriting" class="chat-msg assistant">
              <div class="bubble thinking"><span class="dots"><i /><i /><i /></span>正在生成改写候选…</div>
            </div>
          </div>

          <div class="suggestions">
            <el-button v-for="s in suggestions" :key="s" size="small" round plain @click="instruction = s">{{ s }}</el-button>
          </div>
          <div class="input-row">
            <el-input
              v-model="instruction"
              type="textarea"
              :rows="2"
              resize="none"
              placeholder="输入对这个区域的优化意见，AI 会生成改写候选（Enter 发送，Shift+Enter 换行）"
              @keydown.enter.exact.prevent="onRewrite"
            />
            <el-button type="primary" :loading="rewriting" :disabled="!instruction.trim()" @click="onRewrite">发送</el-button>
          </div>
        </template>
        <div v-else class="chat-empty full">
          <div class="chat-empty-badge">区</div>
          <p class="empty-title">从中间选一个区域开始对话</p>
          <p class="empty-hint">每个区域独立对话，改写会生成新版本，旧版本可随时回滚</p>
        </div>
      </aside>
    </div>

    <!-- 改写对比弹窗 -->
    <RewriteCompareDialog
      :visible="compareVisible"
      :result="rewriteResult"
      :section="selectedSection"
      @close="compareVisible = false"
      @adopted="onAdopted"
    />

    <!-- 会话导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="从会话导入简历" width="560px">
      <p class="empty-hint" style="margin-bottom: 12px">
        选择一个已生成简历内容的分析会话，把它的最新简历导入简历库（也可先去
        <router-link to="/workspace" class="inline-link">求职分析</router-link> 生成）。
      </p>
      <div v-if="sessionsLoading" class="import-list"><SkeletonLoader variant="card" :lines="2" /></div>
      <div v-else-if="importableSessions.length === 0" class="import-list">
        <el-empty description="暂无可导入的会话" :image-size="60" />
      </div>
      <div v-else class="import-list">
        <div v-for="s in importableSessions" :key="s.session_id" class="import-row">
          <span class="import-id">{{ s.session_id.slice(0, 8) }}</span>
          <el-tag size="small" type="info" disable-transitions>{{ stageLabel(s.stage) }}</el-tag>
          <el-button size="small" type="primary" plain :loading="importingId === s.session_id" @click="onImport(s.session_id)">导入</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import AppNav from '../components/AppNav.vue'
import SkeletonLoader from '../components/SkeletonLoader.vue'
import RewriteCompareDialog from '../components/resume/RewriteCompareDialog.vue'
import MatchWorkspace from '../components/matching/MatchWorkspace.vue'
import {
  deleteResumeDoc,
  getResumeDoc,
  importResumeFromSession,
  listDeletedResumes,
  listResumeDocs,
  restoreResumeDoc,
  rewriteSection,
  rollbackResumeVersion,
  setVersionPagePreference,
  updateResumeDoc,
  updateResumeSection,
  hasLayoutSource,
  exportResumeLayout,
} from '../api/resumeLibrary'
import { listSessions } from '../api/sessions'
import { importUploadResume, exportResume, downloadBlob, getPhotoInfo, type ExportFormat } from '../api/resumeGeneration'
import type {
  ResumeLibraryDoc,
  ResumeLibrarySection,
  ResumeLibraryVersion,
  RewriteResult,
  SessionListItem,
} from '../types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  FileText,
  Library,
  MessagesSquare,
  Pencil,
  SquareDashedMousePointer,
  Trash2,
  Upload,
  Wand2,
  X,
  Download,
} from 'lucide-vue-next'

const SECTION_COLORS = ['#c15f3c', '#b85c6e', '#6f8f5f', '#b57b1f', '#8a5a83', '#4c7f7d', '#9c4a2b', '#7a8b3a']

const router = useRouter()
const uploadInput = ref<HTMLInputElement | null>(null)

async function onUploadFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  try {
    const { value } = await ElMessageBox.prompt('给这份简历起个名字', '上传简历', {
      inputValue: file.name.replace(/\.[^.]+$/, ''),
      inputPattern: /.+/,
      inputErrorMessage: '名称不能为空',
    })
    await importUploadResume(value.trim(), file)
    ElMessage.success('已解析并导入简历库')
    await loadDocs()
  } catch (err: unknown) {
    if (err !== 'cancel' && !(err as Error | undefined)?.message?.includes('cancel')) {
      ElMessage.error(extractError(err, '上传失败（支持 PDF/DOCX/TXT/MD）'))
    }
  }
}

const tab = ref<'library' | 'matching'>('library')
const SECTION_TYPE_LABELS: Record<string, string> = {
  header: '基本信息',
  summary: '自我评价',
  education: '教育经历',
  experience: '工作经历',
  project: '项目经历',
  skill: '技能',
  certification: '证书',
  custom: '自定义',
}
const SOURCE_LABELS: Record<string, string> = { manual: '手动新建', session: '会话生成', upload: '上传', generation: '生成' }
const STAGE_LABELS: Record<string, string> = {
  init: '初始化',
  has_jd: '已上传 JD',
  has_resume: '已上传简历',
  has_jd_and_resume: 'JD + 简历',
  completed: '已完成',
}
const suggestions = ['表达更精炼有力', '补充量化成果', '突出技术深度', '更贴合目标岗位']

const docs = ref<ResumeLibraryDoc[]>([])
const deletedDocs = ref<ResumeLibraryDoc[]>([])
const currentDoc = ref<ResumeLibraryDoc | null>(null)
const railLoading = ref(false)
const errorMessage = ref('')
const recycleMode = ref(false)

const viewedVersionId = ref<number | null>(null)
const selectedSectionId = ref<number | null>(null)
const histories = reactive<Record<number, { role: string; content: string }[]>>({})

const instruction = ref('')
const rewriting = ref(false)
const compareVisible = ref(false)
const rewriteResult = ref<RewriteResult | null>(null)

const importDialogVisible = ref(false)
const sessionsLoading = ref(false)
const importableSessions = ref<SessionListItem[]>([])
const importingId = ref('')

const boxMode = ref(false)
const previewRef = ref<HTMLElement | null>(null)
const chatListRef = ref<HTMLElement | null>(null)
const dragRect = ref<{ x: number; y: number; width: number; height: number } | null>(null)
let dragStart: { x: number; y: number } | null = null

const versions = computed<ResumeLibraryVersion[]>(() => currentDoc.value?.versions ?? [])
const viewedVersion = computed<ResumeLibraryVersion | null>(
  () => versions.value.find((v) => v.id === viewedVersionId.value) ?? null
)
const viewedSections = computed<ResumeLibrarySection[]>(() => viewedVersion.value?.sections ?? [])
const pagePref = computed<'one_page' | 'two_pages'>(
  () => (viewedVersion.value?.render_config?.page_preference === 'two_pages' ? 'two_pages' : 'one_page'),
)
async function onSetPagePreference(val: string | number | boolean | undefined) {
  if (!viewedVersion.value) return
  const pref: 'one_page' | 'two_pages' = val === 'two_pages' ? 'two_pages' : 'one_page'
  const updated = await setVersionPagePreference(viewedVersion.value.id, pref)
  if (currentDoc.value?.versions) {
    const idx = currentDoc.value.versions.findIndex((v) => v.id === updated.id)
    if (idx >= 0) currentDoc.value.versions[idx] = updated
  }
}
const selectedSection = computed<ResumeLibrarySection | null>(
  () => viewedSections.value.find((s) => s.id === selectedSectionId.value) ?? null
)
const selectedIndex = computed(() => viewedSections.value.findIndex((s) => s.id === selectedSectionId.value))
const boxedSections = computed(() => viewedSections.value.filter((s) => s.bounding_box))
const history = computed(() => (selectedSectionId.value ? histories[selectedSectionId.value] ?? [] : []))

function sectionColor(idx: number) {
  return SECTION_COLORS[((idx % SECTION_COLORS.length) + SECTION_COLORS.length) % SECTION_COLORS.length]
}
function typeLabel(t: string) {
  return SECTION_TYPE_LABELS[t] ?? t
}
function sourceLabel(s: string) {
  return SOURCE_LABELS[s] ?? s
}
function sourceTagType(s: string): 'primary' | 'success' | 'warning' {
  return s === 'session' ? 'success' : s === 'upload' ? 'warning' : 'primary'
}
function stageLabel(stage: string) {
  return STAGE_LABELS[stage] ?? stage
}
function formatDate(value: string | null) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadDocs() {
  railLoading.value = true
  errorMessage.value = ''
  try {
    docs.value = await listResumeDocs()
    if (currentDoc.value) {
      const still = docs.value.find((d) => d.id === currentDoc.value?.id)
      if (still) await refreshCurrent()
      else resetCurrent()
    }
  } catch (err: unknown) {
    errorMessage.value = extractError(err, '加载简历库失败')
  } finally {
    railLoading.value = false
  }
}

async function refreshCurrent() {
  if (!currentDoc.value) return
  currentDoc.value = await getResumeDoc(currentDoc.value.id)
  if (!viewedVersionId.value || !versions.value.some((v) => v.id === viewedVersionId.value)) {
    viewedVersionId.value = currentDoc.value.current_version_id ?? versions.value[0]?.id ?? null
  }
  void refreshLayoutSource()
}

function resetCurrent() {
  currentDoc.value = null
  viewedVersionId.value = null
  selectedSectionId.value = null
}

async function selectDoc(id: number) {
  try {
    currentDoc.value = await getResumeDoc(id)
    viewedVersionId.value = currentDoc.value.current_version_id ?? versions.value[0]?.id ?? null
    selectedSectionId.value = null
    void refreshLayoutSource()
  } catch (err: unknown) {
    ElMessage.error(extractError(err, '打开简历失败'))
  }
}

function selectSection(sec: ResumeLibrarySection) {
  selectedSectionId.value = sec.id
  if (!histories[sec.id]) histories[sec.id] = []
}

async function onRename() {
  if (!currentDoc.value) return
  try {
    const { value } = await ElMessageBox.prompt('新的简历名称', '重命名', {
      inputValue: currentDoc.value.title,
      inputPattern: /.+/,
      inputErrorMessage: '名称不能为空',
    })
    await updateResumeDoc(currentDoc.value.id, { title: value.trim() })
    ElMessage.success('已重命名')
    await loadDocs()
  } catch {
    /* 用户取消 */
  }
}

async function onDeleteDoc() {
  if (!currentDoc.value) return
  try {
    await ElMessageBox.confirm('移入回收站后可随时恢复，确认删除？', '删除简历', { type: 'warning' })
  } catch {
    return
  }
  await deleteResumeDoc(currentDoc.value.id)
  ElMessage.success('已移入回收站')
  resetCurrent()
  await loadDocs()
}

async function onRestore(doc: ResumeLibraryDoc) {
  await restoreResumeDoc(doc.id)
  ElMessage.success('已恢复')
  await loadDocs()
}

async function onPurge(doc: ResumeLibraryDoc) {
  try {
    await ElMessageBox.confirm('彻底删除后不可恢复（含全部版本），确认？', '彻底删除', { type: 'error' })
  } catch {
    return
  }
  await deleteResumeDoc(doc.id, true)
  ElMessage.success('已彻底删除')
  await loadRecycle()
}

function toggleRecycle() {
  recycleMode.value = !recycleMode.value
  if (recycleMode.value) void loadRecycle()
}

async function loadRecycle() {
  railLoading.value = true
  try {
    deletedDocs.value = await listDeletedResumes()
  } catch (err: unknown) {
    ElMessage.error(extractError(err, '回收站加载失败'))
  } finally {
    railLoading.value = false
  }
}

async function onRollback() {
  if (!viewedVersion.value) return
  try {
    await ElMessageBox.confirm(
      `回滚到 v${viewedVersion.value.version}（当前版本指针切换，历史保留），确认？`,
      '版本回滚',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await rollbackResumeVersion(viewedVersion.value.id)
    ElMessage.success('已回滚')
    await refreshCurrent()
  } catch (err: unknown) {
    ElMessage.error(extractError(err, '回滚失败'))
  }
}

async function onRewrite() {
  const sec = selectedSection.value
  if (!sec || !instruction.value.trim() || rewriting.value) return
  const text = instruction.value.trim()
  histories[sec.id] = histories[sec.id] ?? []
  histories[sec.id].push({ role: 'user', content: text })
  instruction.value = ''
  rewriting.value = true
  await scrollChat()
  try {
    rewriteResult.value = await rewriteSection(sec.id, {
      instruction: text,
      conversation_history: histories[sec.id].slice(0, -1),
    })
    histories[sec.id].push({
      role: 'assistant',
      content: `已生成 ${rewriteResult.value.candidates.length} 条改写候选${
        rewriteResult.value.needs_source_confirmation ? '（含需核对来源的内容）' : ''
      }，请在对比弹窗中查看`,
    })
    compareVisible.value = true
  } catch (err: unknown) {
    const detail = extractError(err, '改写生成失败，请稍后重试')
    histories[sec.id].push({ role: 'assistant', content: `⚠️ ${detail}` })
    ElMessage.error(detail)
  } finally {
    rewriting.value = false
    await scrollChat()
  }
}

async function onAdopted(versionNumber: number) {
  const sec = selectedSection.value
  if (sec) {
    histories[sec.id] = histories[sec.id] ?? []
    histories[sec.id].push({ role: 'assistant', content: `✅ 已采纳改写，生成新版本 v${versionNumber}` })
  }
  compareVisible.value = false
  await refreshCurrent()
  viewedVersionId.value = currentDoc.value?.current_version_id ?? viewedVersionId.value
  await loadDocs()
}

async function openImportDialog() {
  importDialogVisible.value = true
  sessionsLoading.value = true
  try {
    const { data } = await listSessions()
    importableSessions.value = data.filter((s) => s.stage === 'completed' || s.stage === 'has_jd_and_resume')
  } catch (err: unknown) {
    ElMessage.error(extractError(err, '会话列表加载失败'))
  } finally {
    sessionsLoading.value = false
  }
}

async function onImport(sessionId: string) {
  importingId.value = sessionId
  try {
    const doc = await importResumeFromSession(sessionId)
    ElMessage.success(`已导入「${doc.title}」`)
    importDialogVisible.value = false
    await loadDocs()
    await selectDoc(doc.id)
  } catch (err: unknown) {
    ElMessage.error(extractError(err, '导入失败：该会话可能还没有简历内容'))
  } finally {
    importingId.value = ''
  }
}

async function scrollChat() {
  await nextTick()
  chatListRef.value?.scrollTo({ top: chatListRef.value.scrollHeight, behavior: 'smooth' })
}

function extractError(err: unknown, fallback: string): string {
  const anyErr = err as {
    response?: { data?: { detail?: string | { msg?: string }[] } }
    message?: string
  }
  const detail = anyErr?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => d?.msg || '').filter(Boolean).join('; ') || fallback
  }
  if (anyErr?.message && /timeout|Network Error/i.test(anyErr.message)) {
    return anyErr.message.includes('timeout')
      ? '请求超时（改写生成较慢），请稍后重试或简化指令'
      : '网络异常，请检查后端服务是否可用'
  }
  return fallback
}

// ---- 框选模式：拖拽画框 → 命中区域卡片 → 记录 bounding_box ----

function previewPoint(e: MouseEvent) {
  const rect = previewRef.value!.getBoundingClientRect()
  return { x: e.clientX - rect.left, y: e.clientY - rect.top }
}

function onPreviewMouseDown(e: MouseEvent) {
  if (!boxMode.value || !previewRef.value) return
  e.preventDefault()
  const p = previewPoint(e)
  dragStart = p
  dragRect.value = { x: p.x, y: p.y, width: 0, height: 0 }
}

function onPreviewMouseMove(e: MouseEvent) {
  if (!boxMode.value || !dragStart || !dragRect.value) return
  const p = previewPoint(e)
  dragRect.value = {
    x: Math.min(dragStart.x, p.x),
    y: Math.min(dragStart.y, p.y),
    width: Math.abs(p.x - dragStart.x),
    height: Math.abs(p.y - dragStart.y),
  }
}

async function onPreviewMouseUp() {
  if (!boxMode.value || !dragStart || !dragRect.value || !previewRef.value) {
    dragStart = null
    dragRect.value = null
    return
  }
  const rect = dragRect.value
  dragStart = null
  dragRect.value = null
  if (rect.width < 8 || rect.height < 8) return

  // 命中测试：与拖拽框重叠面积最大的区域卡片
  let best: { id: number; el: HTMLElement; overlap: number } | null = null
  previewRef.value.querySelectorAll<HTMLElement>('[data-section-id]').forEach((el) => {
    const r = el.getBoundingClientRect()
    const base = previewRef.value!.getBoundingClientRect()
    const box = { x: r.left - base.left, y: r.top - base.top, w: r.width, h: r.height }
    const overlapX = Math.max(0, Math.min(rect.x + rect.width, box.x + box.w) - Math.max(rect.x, box.x))
    const overlapY = Math.max(0, Math.min(rect.y + rect.height, box.y + box.h) - Math.max(rect.y, box.y))
    const overlap = overlapX * overlapY
    if (overlap > 0 && (!best || overlap > best.overlap)) best = { id: Number(el.dataset.sectionId), el, overlap }
  })
  if (!best) {
    ElMessage.warning('框选范围内没有区域，请框住某个板块')
    return
  }
  const target = viewedSections.value.find((s) => s.id === (best as { id: number }).id)
  if (!target) return
  try {
    await updateResumeSection(target.id, {
      bounding_box: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height), page: 1 },
    } as Partial<ResumeLibrarySection>)
    ElMessage.success(`已为「${target.title || '区域'}」记录选框`)
    await refreshCurrent()
    selectSection(target)
  } catch (err: unknown) {
    ElMessage.error(extractError(err, '记录选框失败'))
  }
}

/** 清除某区域已保存的选框（bounding_box=null） */
async function onClearBox(sec: ResumeLibrarySection) {
  try {
    await updateResumeSection(sec.id, {
      bounding_box: null,
    } as unknown as Partial<ResumeLibrarySection>)
    await refreshCurrent()
    ElMessage.success(`已清除「${sec.title || '区域'}」的选框`)
  } catch (err: unknown) {
    ElMessage.error(extractError(err, '清除选框失败'))
  }
}

// ---- 导出当前预览版本 ----
const exporting = ref<'' | ExportFormat | 'print' | 'layout'>('')
const exportError = ref('')
const canLayoutExport = ref(false)

async function refreshLayoutSource() {
  canLayoutExport.value = false
  if (!currentDoc.value) return
  try {
    const info = await hasLayoutSource(currentDoc.value.id)
    canLayoutExport.value = !!(info.has_source && info.is_docx)
  } catch {
    canLayoutExport.value = false
  }
}

function buildExportContent() {
  const sections = viewedSections.value
    .filter((s) => ((s.title || '') + (s.content || '')).trim())
    .map((s) => ({ title: s.title || '模块', content: s.content || '' }))
  const raw_text = sections.map((s) => `${s.title}\n${s.content}`).join('\n\n')
  return { sections, raw_text }
}

function exportTitle(): string {
  const ver = viewedVersion.value?.version
  const base = (currentDoc.value?.title || '简历').trim() || '简历'
  return ver ? `${base}_v${ver}` : base
}

async function loadExportPhotoId(): Promise<number | null> {
  try {
    const res = await getPhotoInfo()
    return res.data?.id ?? null
  } catch {
    return null
  }
}

async function onExport(format: ExportFormat) {
  if (!viewedSections.value.length) {
    ElMessage.warning('当前版本没有可导出的内容')
    return
  }
  exporting.value = format
  exportError.value = ''
  try {
    const photoId = await loadExportPhotoId()
    const blob = await exportResume(buildExportContent(), exportTitle(), format, photoId)
    downloadBlob(blob, `${exportTitle()}.${format === 'md' ? 'md' : format}`)
    ElMessage.success(`已导出 ${format === 'docx' ? 'Word' : format.toUpperCase()}`)
  } catch (err: unknown) {
    exportError.value = extractError(err, '导出失败，请重试')
    ElMessage.error(exportError.value)
  } finally {
    exporting.value = ''
  }
}

async function onPrintPdf() {
  if (!viewedSections.value.length) {
    ElMessage.warning('当前版本没有可导出的内容')
    return
  }
  exporting.value = 'print'
  exportError.value = ''
  try {
    const photoId = await loadExportPhotoId()
    const title = exportTitle()
    const blob = await exportResume(buildExportContent(), title, 'html', photoId)
    const url = URL.createObjectURL(blob)
    const win = window.open(url, '_blank')
    if (win) setTimeout(() => win.print(), 400)
    else downloadBlob(blob, `${title}.html`)
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch (err: unknown) {
    exportError.value = extractError(err, '导出失败，请重试')
    ElMessage.error(exportError.value)
  } finally {
    exporting.value = ''
  }
}

function onExportCommand(cmd: string | number | object) {
  if (cmd === 'print') {
    void onPrintPdf()
    return
  }
  if (cmd === 'layout') {
    void onExportLayout()
    return
  }
  if (cmd === 'docx' || cmd === 'html' || cmd === 'md') {
    void onExport(cmd)
  }
}

/** 保排版导出；失败时由用户选择是否改用统一模板 */
async function onExportLayout() {
  if (!currentDoc.value) return
  exporting.value = 'layout'
  exportError.value = ''
  try {
    const blob = await exportResumeLayout(currentDoc.value.id, viewedVersionId.value)
    downloadBlob(blob, `${exportTitle()}_保排版.docx`)
    ElMessage.success('已按原 Word 版式导出')
  } catch (err: unknown) {
    const msg = extractError(err, '保排版导出失败')
    exportError.value = msg
    const useTpl = await ElMessageBox.confirm(
      `${msg}。是否改用「统一模板」导出 Word？`,
      '保排版导出失败',
      { confirmButtonText: '用统一模板', cancelButtonText: '取消', type: 'warning' },
    ).then(() => true).catch(() => false)
    if (useTpl) void onExport('docx')
  } finally {
    exporting.value = ''
  }
}

onMounted(() => {
  void loadDocs()
})

defineExpose({ openImportDialog })
</script>

<style scoped>
.page {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.ws-tabs {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-6);
  background: var(--color-bg);
  border-bottom: var(--border-light);
}
.ws-tab {
  padding: 6px 18px;
  border: var(--border-light);
  border-radius: var(--radius-full);
  background: var(--color-bg);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
}
.ws-tab:hover {
  color: var(--color-text-primary);
}
.ws-tab.active {
  background: var(--el-color-primary);
  border-color: var(--el-color-primary);
  color: #fff;
  font-weight: var(--weight-medium);
}
.ghost-link {
  font-size: 13px;
  color: var(--color-text-secondary);
  text-decoration: none;
  padding: 6px 10px;
  border-radius: 6px;
}
.ghost-link:hover {
  color: var(--color-text-primary);
  background: var(--color-gray-50, #f9fafb);
}
.layout {
  flex: 1;
  display: grid;
  grid-template-columns: 280px 1fr 380px;
  min-height: 0;
}

/* 左栏 */
.doc-rail {
  border-right: var(--border-light);
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--color-bg);
}
.rail-header {
  padding: var(--space-4);
  border-bottom: var(--border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.rail-title {
  margin: 0;
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
}
.rail-actions {
  display: flex;
  gap: var(--space-1);
}
.rail-body {
  flex: 1;
  overflow: auto;
  padding: var(--space-3);
}
.doc-card {
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  margin-bottom: var(--space-2);
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default);
  background: var(--color-bg);
}
.doc-card:hover {
  border-color: var(--color-accent-400, #60a5fa);
}
.doc-card.active {
  border-color: var(--color-accent-600, #2563eb);
  box-shadow: 0 0 0 1px var(--color-accent-600, #2563eb) inset;
}
.doc-card.deleted {
  cursor: default;
}
.doc-card-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--color-text-primary);
  margin-bottom: var(--space-1);
}
.doc-card-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-2xs, 11px);
  color: var(--color-text-secondary);
}
.doc-card-actions {
  margin-top: var(--space-1);
  display: flex;
  gap: var(--space-2);
}
.empty-guide,
.preview-empty,
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: var(--space-2);
  padding: var(--space-6);
}
.empty-icon {
  color: var(--color-text-disabled);
}
.empty-title {
  margin: 0;
  font-weight: var(--weight-medium);
  color: var(--color-text-primary);
}
.empty-hint {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: 1.6;
}
.empty-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

/* 中栏 */
.preview-pane {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: var(--border-light);
  background: var(--color-bg-page, #f8fafc);
}
.doc-header {
  padding: var(--space-3) var(--space-4);
  border-bottom: var(--border-light);
  background: var(--color-bg);
}
.doc-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.doc-title {
  margin: 0;
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
}
.version-row {
  margin-top: var(--space-2);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-1);
}
.version-label {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.version-chip {
  cursor: pointer;
}
.box-hint {
  margin: var(--space-2) 0 0;
  font-size: var(--text-sm);
  color: var(--el-color-primary);
}
.preview {
  position: relative;
  flex: 1;
  overflow: auto;
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  background-image: radial-gradient(var(--color-gray-200, #e5e7eb) 1px, transparent 1px);
  background-size: 18px 18px;
}
.section-card {
  position: relative;
  background: var(--color-bg);
  border: var(--border-light);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  cursor: pointer;
  transition: box-shadow var(--duration-fast) var(--ease-default);
}
.section-card:hover {
  box-shadow: var(--shadow-sm);
}
.section-card.selected {
  box-shadow: 0 0 0 2px var(--accent);
}
.section-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}
.section-title {
  font-weight: var(--weight-semibold);
  font-size: var(--text-sm);
}
.section-page {
  margin-left: auto;
  font-size: var(--text-2xs, 11px);
  color: var(--color-text-disabled);
}
.section-content {
  margin: 0;
  font-size: var(--text-sm);
  line-height: 1.8;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
.box-overlay {
  position: absolute;
  border: 2px dashed;
  border-radius: var(--radius-sm);
  pointer-events: none;
}
.box-label {
  position: absolute;
  top: -10px;
  left: 8px;
  color: #fff;
  font-size: var(--text-2xs, 11px);
  padding: 0 6px;
  border-radius: var(--radius-full);
  line-height: 18px;
}
.box-clear {
  pointer-events: auto;
  position: absolute;
  top: -10px;
  right: -10px;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: var(--color-bg-elevated, #fff);
  color: var(--color-text-secondary);
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0, 0, 0, 0.12));
  display: grid;
  place-items: center;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}
.box-clear:hover {
  color: var(--color-danger-600, #b91c1c);
  background: var(--color-danger-50, #fef2f2);
}
.export-err {
  margin: 4px 0 0;
  font-size: var(--text-xs);
  color: var(--color-danger-600, #b91c1c);
}
.drag-rect {
  position: absolute;
  border: 2px dashed var(--color-accent-600, #2563eb);
  background: rgba(37, 99, 235, 0.08);
  pointer-events: none;
}

/* 右栏 */
.chat-pane {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--color-bg);
}
.chat-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: var(--border-light);
}
.chat-title {
  font-weight: var(--weight-semibold);
  font-size: var(--text-sm);
}
.chat-meta {
  margin-left: auto;
  font-size: var(--text-2xs, 11px);
  color: var(--color-text-secondary);
}
.chat-list {
  flex: 1;
  overflow: auto;
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.chat-empty.full {
  flex: 1;
}
.chat-empty-badge {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-full);
  background: var(--color-text-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--weight-semibold);
}
.chat-msg {
  display: flex;
}
.chat-msg.user {
  justify-content: flex-end;
}
.chat-msg .bubble {
  max-width: 85%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.chat-msg.user .bubble {
  background: var(--color-accent-600, #2563eb);
  color: #fff;
  border-bottom-right-radius: var(--radius-sm);
}
.chat-msg.assistant .bubble {
  background: var(--color-gray-50, #f9fafb);
  border: var(--border-light);
  color: var(--color-text-primary);
  border-bottom-left-radius: var(--radius-sm);
}
.thinking {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-secondary);
}
.dots {
  display: inline-flex;
  gap: 3px;
}
.dots i {
  width: 5px;
  height: 5px;
  border-radius: var(--radius-full);
  background: var(--color-text-disabled);
  animation: dot-pulse 1.2s infinite ease-in-out;
}
.dots i:nth-child(2) {
  animation-delay: 0.2s;
}
.dots i:nth-child(3) {
  animation-delay: 0.4s;
}
.suggestions {
  padding: var(--space-2) var(--space-3);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  border-top: var(--border-light);
}
.input-row {
  padding: var(--space-3);
  border-top: var(--border-light);
  display: flex;
  gap: var(--space-2);
  align-items: flex-end;
}

/* 导入弹窗 */
.import-list {
  max-height: 320px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.import-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
}
.import-id {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}
.inline-link {
  color: var(--el-color-primary);
}
</style>
