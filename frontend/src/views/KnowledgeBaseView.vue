<template>
  <div class="kb-page">
    <AppNav>
      <div class="kb-actions">
        <el-button :type="viewMode === 'list' ? 'primary' : 'default'" text @click="viewMode = 'list'">
          列表
        </el-button>
        <el-button :type="viewMode === 'graph' ? 'primary' : 'default'" text @click="viewMode = 'graph'">
          节点图
        </el-button>
        <el-button type="primary" @click="openAdd">
          <Plus :size="16" />补充知识库
        </el-button>
      </div>
    </AppNav>
    <div class="kb-titlebar"><div class="kb-title">个人知识库</div></div>

    <div class="kb-body">
      <!-- 列表模式 -->
      <template v-if="viewMode === 'list'">
        <aside class="kb-cats">
          <button
            class="cat"
            :class="{ active: activeCategory === '' }"
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
          >待确认更新</button>
        </aside>

        <main class="kb-list">
          <div v-if="store.loading" class="loading">加载中…</div>
          <div v-else-if="!store.items.length" class="empty">
            <p>暂无{{ activeCategory ? categoryLabel : '' }}画像条目</p>
            <p class="sub">点击「补充知识库」添加，或从简历 / 面试报告导入</p>
          </div>
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
                <span>{{ categoryLabel }}</span>
                <span class="ev-count">{{ item.evidences.length }} 条证据</span>
              </div>
            </div>
          </div>
        </main>
      </template>

      <!-- 节点图模式 -->
      <main v-else class="kb-graph">
        <KnowledgeNodeGraph :categories="store.categories" :active-category="activeCategory" @select="onGraphSelect" />
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

    <!-- 补充知识库对话框 -->
    <el-dialog v-model="addOpen" title="补充知识库" width="520px" :append-to-body="true">
      <el-form label-width="88px">
        <el-form-item label="分类">
          <el-select v-model="form.category" placeholder="选择分类">
            <el-option v-for="o in categoryOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" placeholder="如：arXiv 论文问答系统" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="form.content" type="textarea" :rows="4" placeholder="具体事实 / 经历描述" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.item_type">
            <el-radio label="fact">事实</el-radio>
            <el-radio label="suggestion">建议</el-radio>
            <el-radio label="feedback">反馈</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitAdd">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Plus } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { useKnowledgeBaseStore } from '../stores/knowledgeBase'
import AppNav from '../components/AppNav.vue'
import KnowledgeNodeGraph from '../components/KnowledgeNodeGraph.vue'
import type { ProfileCategory, ProfileItem, ProfileStatus } from '../types'

const store = useKnowledgeBaseStore()

const viewMode = ref<'list' | 'graph'>('list')
const activeCategory = ref<ProfileCategory | ''>('')
const activeStatus = ref<ProfileStatus | ''>('')
const selected = ref<ProfileItem | null>(null)
const detailOpen = ref(false)
const addOpen = ref(false)
const saving = ref(false)
const form = ref({
  category: 'experience' as ProfileCategory,
  title: '',
  content: '',
  item_type: 'fact' as 'fact' | 'suggestion' | 'feedback',
})

const categoryLabel = computed(() =>
  activeCategory.value ? store.CATEGORY_LABELS[activeCategory.value] : '',
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
})

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
  await store.remove(selected.value.id)
  detailOpen.value = false
  selected.value = null
  ElMessage.success('已删除')
}

function openAdd() {
  form.value = { category: activeCategory.value || 'experience', title: '', content: '', item_type: 'fact' }
  addOpen.value = true
}

async function submitAdd() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  saving.value = true
  try {
    await store.add({ ...form.value })
    addOpen.value = false
    ElMessage.success('已添加到知识库')
  } finally {
    saving.value = false
  }
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
  padding: var(--space-4) var(--space-6);
  border-bottom: var(--border-light);
  background: var(--color-bg);
}
.kb-title {
  font-size: var(--text-lg, 16px);
  font-weight: var(--weight-semibold);
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
  padding: 8px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  color: var(--color-text-secondary);
  text-align: left;
}
.cat:hover {
  background: var(--color-gray-50, #f9fafb);
}
.cat.active {
  background: var(--el-color-primary-light-8, #eff6ff);
  color: var(--el-color-primary);
  font-weight: var(--weight-medium);
}
.cat.suggested {
  margin-top: auto;
  border-top: var(--border-light);
  padding-top: 14px;
}
.badge {
  font-size: 11px;
  opacity: 0.7;
}
.kb-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6);
}
.loading,
.empty {
  text-align: center;
  padding: var(--space-10);
  color: var(--color-text-secondary);
}
.empty .sub {
  font-size: 12px;
  opacity: 0.7;
  margin-top: 6px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
}
.card {
  background: var(--color-bg);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: var(--space-4);
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.card:hover,
.card.selected {
  border-color: var(--el-color-primary);
}
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.title {
  font-weight: var(--weight-semibold);
}
.content {
  margin: 8px 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--color-text-tertiary, #9ca3af);
}
.kb-graph {
  flex: 1;
}
.d-title {
  font-size: 16px;
  font-weight: var(--weight-semibold);
  margin-bottom: 8px;
}
.field-label {
  margin: 16px 0 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: var(--weight-medium);
}
.d-content {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
}
.evidences {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ev {
  border-left: 3px solid var(--el-color-primary-light-5, #93c5fd);
  padding: 6px 10px;
  background: var(--color-gray-50, #f9fafb);
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ev-src {
  font-size: 11px;
  color: var(--el-color-primary);
}
.ev-quote {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.ev-empty {
  font-size: 12px;
  color: var(--color-text-tertiary, #9ca3af);
}
.d-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
