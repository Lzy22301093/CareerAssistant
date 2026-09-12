<template>
  <div class="kb-page">
    <AppNav>
      <div class="seg" role="tablist">
        <button
          class="seg-btn"
          :class="{ active: viewMode === 'list' }"
          @click="viewMode = 'list'"
        >列表</button>
        <button
          class="seg-btn"
          :class="{ active: viewMode === 'graph' }"
          @click="viewMode = 'graph'"
        >节点图</button>
      </div>
      <el-button type="primary" @click="openWizard">
        <Plus :size="16" />完善画像
      </el-button>
    </AppNav>
    <div class="kb-titlebar">
      <div class="kb-titlebar-text">
        <div class="kb-title">个人画像</div>
        <p class="kb-sub">基本信息、教育、实习/项目、技能与目标，沉淀为可复用的画像</p>
      </div>
    </div>

    <div class="kb-body">
      <!-- 列表模式 -->
      <template v-if="viewMode === 'list'">
        <aside class="kb-cats">
          <button
            class="cat"
            :class="{ active: activeCategory === '' && activeStatus !== 'suggested' }"
            @click="selectCategory('')"
          >全部</button>
          <button
            v-for="c in categoryOptions"
            :key="c.value"
            class="cat"
            :class="{ active: activeCategory === c.value }"
            @click="selectCategory(c.value)"
          >
            <span>{{ c.label }}</span>
            <span class="badge">{{ c.count }}</span>
          </button>
          <button
            class="cat suggested"
            :class="{ active: activeStatus === 'suggested' }"
            @click="toggleSuggested"
          >
            <span>待确认更新</span>
            <span class="badge warn">{{ suggestedCount }}</span>
          </button>
        </aside>

        <main class="kb-list">
          <!-- 分类工具条 -->
          <div class="cat-toolbar">
            <div class="cat-toolbar-title">
              {{ activeCategory ? categoryLabel : '全部画像' }}
              <span v-if="store.items.length" class="count">{{ store.items.length }} 条</span>
            </div>
            <div class="cat-toolbar-actions">
              <template v-if="activeCategory === 'target'">
                <el-button size="small" @click="dirDialogOpen = true">
                  <Compass :size="14" style="margin-right: 4px" />AI 推荐方向
                </el-button>
              </template>
              <template v-else-if="activeCategory === 'soft'">
                <el-button size="small" type="primary" @click="softDialogOpen = true">
                  <Sparkles :size="14" style="margin-right: 4px" />编辑软性信息
                </el-button>
              </template>
              <el-button
                v-if="activeCategory && activeCategory !== 'soft' && activeCategory !== 'basic_info' && activeCategory !== 'education'"
                size="small"
                type="primary"
                plain
                @click="quickAddOpen = !quickAddOpen"
              >
                <Plus :size="14" style="margin-right: 4px" />{{ activeCategory === 'skill' || activeCategory === 'target' ? '手动添加' : '添加一条' }}
              </el-button>
              <el-button v-if="!activeCategory" size="small" text type="primary" @click="openWizard">
                完善画像
              </el-button>
            </div>
          </div>

          <!-- 技能 / 目标岗位 快捷添加 -->
          <div v-if="quickAddOpen && (activeCategory === 'skill' || activeCategory === 'target')" class="quick-add">
            <el-input
              v-model="quickAddInput"
              :placeholder="activeCategory === 'skill' ? '输入技能后回车，如：Python、Vue' : '输入目标岗位后回车，如：后端开发工程师'"
              clearable
              @keyup.enter="onQuickAdd"
            />
            <el-button type="primary" :loading="quickAdding" @click="onQuickAdd">添加</el-button>
          </div>
          <div v-else-if="quickAddOpen && activeCategory && activeCategory !== 'soft' && activeCategory !== 'basic_info' && activeCategory !== 'education'" class="quick-add generic">
            <el-input v-model="genericTitle" placeholder="标题（必填）" style="flex: 1; min-width: 160px" />
            <el-input
              v-model="genericContent"
              type="textarea"
              :rows="2"
              placeholder="内容（可选）"
              style="flex: 2; min-width: 200px"
            />
            <el-button type="primary" :loading="quickAdding" @click="onGenericAdd">添加</el-button>
          </div>

          <!-- 技能标签流（技能分类下始终显示） -->
          <div v-if="activeCategory === 'skill' && skillTags.length" class="tag-flow">
            <el-tag
              v-for="s in skillTags"
              :key="s.id"
              closable
              size="large"
              @close="removeSkill(s)"
            >{{ s.title }}</el-tag>
          </div>
          <div v-if="activeCategory === 'target' && targetTags.length" class="tag-flow">
            <el-tag
              v-for="t in targetTags"
              :key="t.id"
              closable
              size="large"
              type="success"
              @close="removeTarget(t)"
            >{{ t.title }}</el-tag>
          </div>

          <!-- loading -->
          <SkeletonLoader v-if="store.loading" variant="card" :lines="4" />

          <!-- error -->
          <div v-else-if="store.error" class="state-error">
            <el-alert type="error" :title="store.error" show-icon :closable="false" />
            <el-button type="primary" plain class="retry" @click="reloadItems">重试</el-button>
          </div>

          <!-- empty -->
          <div v-else-if="!store.items.length" class="empty">
            <Inbox :size="40" class="empty-icon" />
            <p class="empty-title">暂无{{ activeCategory ? categoryLabel : '' }}画像条目</p>
            <p class="empty-sub">
              {{ emptyHint }}
            </p>
            <el-button v-if="activeCategory === 'soft'" type="primary" @click="softDialogOpen = true">
              编辑软性信息
            </el-button>
            <el-button v-else-if="activeCategory === 'target'" type="primary" @click="dirDialogOpen = true">
              AI 推荐方向
            </el-button>
            <el-button
              v-else-if="activeCategory && activeCategory !== 'basic_info' && activeCategory !== 'education'"
              type="primary"
              @click="quickAddOpen = true"
            >添加一条</el-button>
            <el-button v-else type="primary" plain @click="openWizard">完善画像</el-button>
          </div>

          <!-- data（技能/目标已有标签流时卡片可省略重复展示，仍保留可点编辑） -->
          <div v-else class="cards">
            <div
              v-for="item in store.items"
              :key="item.id"
              class="card"
              :class="{ selected: selected?.id === item.id }"
              @click="selectItem(item)"
            >
              <div class="card-top">
                <span class="title">{{ item.title }}</span>
                <el-tag size="small" :type="statusType(item.status)">{{ statusLabel(item.status) }}</el-tag>
              </div>
              <div class="content">{{ item.content || '—' }}</div>
              <div class="meta">
                <span class="cat-label">{{ categoryOf(item) }}</span>
                <span class="ev-count">{{ item.evidences.length }} 条证据</span>
              </div>
            </div>
          </div>
        </main>
      </template>

      <!-- 节点图模式 -->
      <main v-else class="kb-graph">
        <KnowledgeNodeGraph
          :categories="store.categories"
          :active-category="activeCategory"
          :avatar-url="avatarUrl"
          @select="onGraphSelect"
        />
      </main>
    </div>

    <!-- 条目详情抽屉 -->
    <el-drawer v-model="detailOpen" title="画像条目" size="420px" :append-to-body="true">
      <template v-if="selected">
        <div class="d-title">{{ selected.title }}</div>
        <el-tag size="small" :type="statusType(selected.status)">{{ statusLabel(selected.status) }}</el-tag>

        <div class="field-label">标题</div>
        <el-input v-model="editTitle" :disabled="editSaving" />

        <div class="field-label">内容</div>
        <el-input
          v-model="editContent"
          type="textarea"
          :rows="5"
          :disabled="editSaving"
          placeholder="补充或修改这条画像的正文"
        />
        <div class="edit-actions">
          <el-button type="primary" size="small" :loading="editSaving" @click="saveEdit">保存修改</el-button>
        </div>

        <div class="field-label">证据来源</div>
        <div v-if="selected.evidences.length" class="evidences">
          <div v-for="ev in selected.evidences" :key="ev.id" class="ev">
            <span class="ev-src">{{ sourceLabel(ev.source_type) }}</span>
            <span class="ev-quote">{{ ev.quote }}</span>
            <el-tag v-if="ev.verified_by_user" size="small" type="success">已确认</el-tag>
          </div>
        </div>
        <div v-else class="ev-empty">暂无证据</div>

        <div class="field-label">操作</div>
        <div class="d-actions">
          <el-button size="small" @click="changeStatus('confirmed')">设为事实</el-button>
          <el-button size="small" @click="changeStatus('suggested')">设为建议</el-button>
          <el-button size="small" @click="changeStatus('archived')">归档</el-button>
          <el-button size="small" type="danger" @click="removeItem">删除</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 完善画像：分阶段结构化向导 -->
    <ProfileFormWizard v-model="wizardOpen" @saved="onWizardSaved" />

    <!-- 软性信息：AI 生成 + 保存到画像 -->
    <SoftInfoDialog v-model="softDialogOpen" @saved="onSoftSaved" />

    <!-- 投递方向：AI 推荐 + 保存到画像 -->
    <DirectionDialog v-model="dirDialogOpen" @saved="onDirSaved" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Plus, Inbox, Sparkles, Compass } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeBaseStore } from '../stores/knowledgeBase'
import AppNav from '../components/AppNav.vue'
import KnowledgeNodeGraph from '../components/KnowledgeNodeGraph.vue'
import ProfileFormWizard from '../components/ProfileFormWizard.vue'
import SoftInfoDialog from '../components/SoftInfoDialog.vue'
import DirectionDialog from '../components/DirectionDialog.vue'
import SkeletonLoader from '../components/SkeletonLoader.vue'
import { getPhotoInfo } from '../api/resumeGeneration'
import type { ProfileCategory, ProfileItem, ProfileStatus } from '../types'

const store = useKnowledgeBaseStore()

const viewMode = ref<'list' | 'graph'>('list')
const activeCategory = ref<ProfileCategory | ''>('')
const activeStatus = ref<ProfileStatus | ''>('')
const selected = ref<ProfileItem | null>(null)
const detailOpen = ref(false)
const wizardOpen = ref(false)
const softDialogOpen = ref(false)
const dirDialogOpen = ref(false)
const avatarUrl = ref('')

// 详情编辑
const editTitle = ref('')
const editContent = ref('')
const editSaving = ref(false)

// 分类快捷添加
const quickAddOpen = ref(false)
const quickAddInput = ref('')
const quickAdding = ref(false)
const genericTitle = ref('')
const genericContent = ref('')

const categoryLabel = computed(() =>
  activeCategory.value ? store.CATEGORY_LABELS[activeCategory.value] : '',
)

const suggestedCount = computed(() =>
  store.categories.reduce((sum, c) => sum + (c.suggested || 0), 0),
)

const categoryOptions = computed(() =>
  (Object.keys(store.CATEGORY_LABELS) as ProfileCategory[]).map((value) => ({
    value,
    label: store.CATEGORY_LABELS[value],
    count: store.categories.find((c) => c.category === value)?.count ?? 0,
  })),
)

const skillTags = computed(() =>
  activeCategory.value === 'skill'
    ? store.items.filter((i) => i.category === 'skill' && i.status !== 'archived')
    : [],
)
const targetTags = computed(() =>
  activeCategory.value === 'target'
    ? store.items.filter((i) => i.category === 'target' && i.status !== 'archived')
    : [],
)

const emptyHint = computed(() => {
  if (activeCategory.value === 'skill') return '添加你掌握的技能，简历生成与岗位匹配会自动复用'
  if (activeCategory.value === 'target') return '手动添加目标岗位，或用 AI 基于画像推荐方向'
  if (activeCategory.value === 'soft') return '填写性格、愿景与自我评价，可 AI 辅助生成'
  if (activeCategory.value === 'experience') return '补充项目/实习经历，便于包装简历'
  if (activeCategory.value === 'interview_feedback') return '记录面试反馈，反哺长期画像'
  return '点击「完善画像」用分阶段表单填写，或在分类里添加条目'
})

watch(activeCategory, () => {
  quickAddOpen.value = false
  quickAddInput.value = ''
  genericTitle.value = ''
  genericContent.value = ''
})

onMounted(async () => {
  await store.fetchCategories()
  await reloadItems()
  await loadAvatar()
})

async function loadAvatar() {
  try {
    // 头像接口需鉴权，用 blob 避免 img 裂图
    const { fetchPhotoBlob } = await import('../api/resumeGeneration')
    const info = await getPhotoInfo()
    if (info.data?.id) {
      const blob = await fetchPhotoBlob(info.data.id)
      if (avatarUrl.value.startsWith('blob:')) URL.revokeObjectURL(avatarUrl.value)
      avatarUrl.value = URL.createObjectURL(blob)
    } else {
      avatarUrl.value = ''
    }
  } catch {
    avatarUrl.value = ''
  }
}

async function reloadItems() {
  await store.fetchItems(activeCategory.value || undefined, activeStatus.value || undefined)
}

async function refreshAll() {
  await Promise.all([store.fetchCategories(), reloadItems()])
}

function selectCategory(cat: ProfileCategory | '') {
  activeCategory.value = cat
  activeStatus.value = ''
  reloadItems()
}

function toggleSuggested() {
  activeStatus.value = activeStatus.value === 'suggested' ? '' : 'suggested'
  activeCategory.value = ''
  reloadItems()
}

function onGraphSelect(cat: string) {
  activeCategory.value = cat as ProfileCategory
  activeStatus.value = ''
  viewMode.value = 'list'
  reloadItems()
}

function selectItem(item: ProfileItem) {
  selected.value = item
  editTitle.value = item.title
  editContent.value = item.content || ''
  detailOpen.value = true
}

async function saveEdit() {
  if (!selected.value) return
  const title = editTitle.value.trim()
  if (!title) {
    ElMessage.warning('标题不能为空')
    return
  }
  editSaving.value = true
  try {
    const updated = await store.update(selected.value.id, {
      title,
      content: editContent.value,
    })
    selected.value = { ...selected.value, ...updated }
    await refreshAll()
    ElMessage.success('已保存')
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    editSaving.value = false
  }
}

async function changeStatus(status: ProfileStatus) {
  if (!selected.value) return
  await store.setStatus(selected.value.id, status)
  selected.value = { ...selected.value, status }
  await refreshAll()
  ElMessage.success('状态已更新')
}

async function removeItem() {
  if (!selected.value) return
  try {
    await ElMessageBox.confirm(
      `删除「${selected.value.title}」这条画像条目？`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await store.remove(selected.value.id)
  await refreshAll()
  detailOpen.value = false
  selected.value = null
  ElMessage.success('已删除')
}

async function onQuickAdd() {
  const title = quickAddInput.value.trim()
  if (!title) return
  if (!activeCategory.value) return
  // 技能/岗位：一技能/一岗位一条，title 即名称
  const exists = store.items.some((i) => i.title === title)
  if (exists) {
    ElMessage.warning(`「${title}」已存在`)
    return
  }
  quickAdding.value = true
  try {
    await store.add({
      category: activeCategory.value,
      title,
      content: '',
      status: 'confirmed',
      item_type: 'fact',
    })
    quickAddInput.value = ''
    await refreshAll()
    ElMessage.success('已添加')
  } catch {
    ElMessage.error('添加失败')
  } finally {
    quickAdding.value = false
  }
}

async function onGenericAdd() {
  const title = genericTitle.value.trim()
  if (!title || !activeCategory.value) {
    ElMessage.warning('请填写标题')
    return
  }
  quickAdding.value = true
  try {
    await store.add({
      category: activeCategory.value,
      title,
      content: genericContent.value.trim(),
      status: 'confirmed',
      item_type: 'fact',
    })
    genericTitle.value = ''
    genericContent.value = ''
    await refreshAll()
    ElMessage.success('已添加')
  } catch {
    ElMessage.error('添加失败')
  } finally {
    quickAdding.value = false
  }
}

async function removeSkill(item: ProfileItem) {
  try {
    await ElMessageBox.confirm(`移除技能「${item.title}」？`, '确认', { type: 'warning' })
  } catch {
    return
  }
  await store.remove(item.id)
  await refreshAll()
}

async function removeTarget(item: ProfileItem) {
  try {
    await ElMessageBox.confirm(`移除目标岗位「${item.title}」？`, '确认', { type: 'warning' })
  } catch {
    return
  }
  await store.remove(item.id)
  await refreshAll()
}

function openWizard() {
  wizardOpen.value = true
}

async function onWizardSaved() {
  await refreshAll()
  await loadAvatar()
}

async function onSoftSaved() {
  if (!activeCategory.value) activeCategory.value = 'soft'
  await refreshAll()
}

async function onDirSaved() {
  if (!activeCategory.value) activeCategory.value = 'target'
  await refreshAll()
}

function categoryOf(item: ProfileItem) {
  return store.CATEGORY_LABELS[item.category] || item.category
}

function statusLabel(s: ProfileStatus) {
  return { confirmed: '事实', suggested: '待确认', rejected: '已拒绝', archived: '已归档' }[s]
}
function statusType(s: ProfileStatus) {
  return ({ confirmed: 'success', suggested: 'warning', rejected: 'info', archived: 'info' } as const)[s]
}
function sourceLabel(t: string) {
  return ({ user_input: '用户填写', resume: '简历导入', interview_report: '面试报告' } as const)[t] || t
}
</script>

<style scoped>
.kb-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-page);
}
.kb-titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-6) var(--space-8) var(--space-4);
  border-bottom: var(--border-light);
  background: color-mix(in srgb, var(--color-bg) 92%, white);
}
.kb-titlebar-text {
  min-width: 0;
}
.btn-icon {
  margin-right: 5px;
}
.kb-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  justify-content: flex-end;
}
.kb-title {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: var(--weight-semibold);
  letter-spacing: -0.01em;
  color: var(--color-text-primary);
}
.kb-sub {
  margin: var(--space-1) 0 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

/* 分段切换 */
.seg {
  display: inline-flex;
  padding: 3px;
  gap: 2px;
  background: var(--color-gray-100);
  border: var(--border-light);
  border-radius: var(--radius-md);
}
.seg-btn {
  padding: 6px 12px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default);
}
.seg-btn:hover {
  color: var(--color-text-primary);
}
.seg-btn:focus-visible {
  outline: 2px solid var(--color-accent-200);
  outline-offset: 1px;
}
.seg-btn.active {
  background: var(--color-bg-elevated);
  color: var(--color-accent-600);
  box-shadow: var(--shadow-sm);
}

.kb-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.kb-body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.kb-cats {
  width: 200px;
  flex-shrink: 0;
  border-right: var(--border-light);
  background: var(--color-bg);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
  padding: 8px 10px;
  border: var(--border-light);
  border-radius: var(--radius-md);
  background: transparent;
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  text-align: left;
  transition: background var(--duration-fast) var(--ease-default),
    border-color var(--duration-fast) var(--ease-default),
    color var(--duration-fast) var(--ease-default);
}
.cat:hover {
  background: var(--color-gray-100);
  color: var(--color-text-primary);
}
.cat:focus-visible {
  outline: 2px solid var(--color-accent-200);
  outline-offset: 1px;
}
.cat.active {
  background: var(--color-accent-50);
  border-color: var(--color-accent-200);
  color: var(--color-accent-600);
  font-weight: var(--weight-medium);
}
.cat.suggested {
  margin-top: auto;
  border-top: var(--border-light);
  padding-top: 12px;
}
.badge {
  font-size: var(--text-2xs);
  color: var(--color-text-disabled);
  background: var(--color-gray-100);
  border-radius: var(--radius-full);
  padding: 1px 7px;
  min-width: 18px;
  text-align: center;
}
.badge.warn {
  color: var(--color-warning-600);
  background: var(--color-warning-50);
}
.kb-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.cat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.cat-toolbar-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}
.cat-toolbar-title .count {
  margin-left: 8px;
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  font-weight: var(--weight-regular);
  color: var(--color-text-tertiary);
}
.cat-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.quick-add {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
  padding: var(--space-3);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-elevated);
}
.quick-add.generic {
  flex-wrap: wrap;
}
.tag-flow {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.edit-actions {
  margin-top: var(--space-2);
}

/* 空态 & 错误态（token 化） */
.empty {
  text-align: center;
  padding: var(--space-12) var(--space-8);
  color: var(--color-text-secondary);
}
.empty-icon {
  color: var(--color-gray-400);
  margin-bottom: var(--space-3);
}
.empty-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--weight-medium);
  color: var(--color-text-primary);
  margin: 0;
}
.empty-sub {
  font-size: var(--text-sm);
  opacity: 0.85;
  margin: var(--space-2) 0 var(--space-5);
}
.state-error {
  padding: var(--space-8);
}
.state-error .retry {
  margin-top: var(--space-3);
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
}
.card {
  background: var(--color-bg);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-5);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-default),
    box-shadow var(--duration-normal) var(--ease-default),
    transform var(--duration-normal) var(--ease-default);
}
.card:hover,
.card.selected {
  border-color: var(--color-accent-400);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
}
.card .title {
  font-family: var(--font-display);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}
.content {
  margin: var(--space-2) 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.meta {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  font-size: var(--text-2xs);
  color: var(--color-text-disabled);
}
.kb-graph {
  flex: 1;
}
.d-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  margin-bottom: var(--space-2);
  color: var(--color-text-primary);
}
.field-label {
  margin: var(--space-5) 0 var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  font-weight: var(--weight-medium);
}
.d-content {
  margin: 0;
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  color: var(--color-text-primary);
}
.evidences {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.ev {
  border-left: 3px solid var(--color-accent-400);
  padding: var(--space-2) var(--space-3);
  background: var(--color-accent-50);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.ev-src {
  font-size: var(--text-2xs);
  color: var(--color-accent-600);
  font-weight: var(--weight-medium);
}
.ev-quote {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}
.ev-empty {
  font-size: var(--text-sm);
  color: var(--color-text-disabled);
}
.d-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>
