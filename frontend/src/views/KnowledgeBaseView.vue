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
        <Plus :size="16" />补充知识库
      </el-button>
    </AppNav>
    <div class="kb-titlebar">
      <div class="kb-title">个人知识库</div>
      <p class="kb-sub">把学历、项目、技能与目标沉淀为可复用的画像</p>
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
            <p class="empty-sub">点击「补充知识库」用分阶段表单完善你的个人画像，或从简历 / 面试报告导入</p>
            <el-button type="primary" plain @click="openWizard">补充知识库</el-button>
          </div>

          <!-- data -->
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

        <div class="field-label">内容</div>
        <p class="d-content">{{ selected.content || '暂无内容' }}</p>

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

    <!-- 补充知识库：分阶段结构化向导 -->
    <ProfileFormWizard v-model="wizardOpen" @saved="onWizardSaved" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Plus, Inbox } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeBaseStore } from '../stores/knowledgeBase'
import AppNav from '../components/AppNav.vue'
import KnowledgeNodeGraph from '../components/KnowledgeNodeGraph.vue'
import ProfileFormWizard from '../components/ProfileFormWizard.vue'
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
const avatarUrl = ref('')

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

onMounted(async () => {
  await store.fetchCategories()
  await reloadItems()
  await loadAvatar()
})

async function loadAvatar() {
  try {
    const res = await getPhotoInfo()
    avatarUrl.value = res.data ? `${res.data.url}?t=${Date.now()}` : ''
  } catch {
    avatarUrl.value = ''
  }
}

async function reloadItems() {
  await store.fetchItems(activeCategory.value || undefined, activeStatus.value || undefined)
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
  detailOpen.value = true
}

async function changeStatus(status: ProfileStatus) {
  if (!selected.value) return
  await store.setStatus(selected.value.id, status)
  selected.value = { ...selected.value, status }
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
    // 用户取消
    return
  }
  await store.remove(selected.value.id)
  detailOpen.value = false
  selected.value = null
  ElMessage.success('已删除')
}

function openWizard() {
  wizardOpen.value = true
}

async function onWizardSaved() {
  await Promise.all([store.fetchCategories(), reloadItems()])
  await loadAvatar()
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
  padding: var(--space-6) var(--space-8) var(--space-4);
  border-bottom: var(--border-light);
  background: color-mix(in srgb, var(--color-bg) 92%, white);
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
