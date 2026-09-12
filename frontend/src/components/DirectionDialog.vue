<template>
  <el-dialog
    v-model="visible"
    title="AI 推荐投递方向"
    width="720px"
    :append-to-body="true"
    class="dir-dialog"
  >
    <p class="dialog-hint">
      可手动添加目标岗位，或基于已确认画像 AI 推荐 3~8 个方向、选 1~3 个写入画像。简历生成、经历包装与岗位匹配都会自动复用。
    </p>

    <!-- 手动添加 -->
    <div class="manual-add">
      <el-input
        v-model="manualTitle"
        placeholder="手动添加岗位，如：后端开发工程师"
        clearable
        @keyup.enter="addManual"
      />
      <el-button type="primary" :loading="manualSaving" @click="addManual">添加</el-button>
    </div>

    <!-- 已确认方向 -->
    <div v-if="existing.length" class="existing">
      <div class="existing-label">画像中已确认的方向</div>
      <div class="existing-tags">
        <el-tag v-for="t in existing" :key="t" size="small" type="success" closable @close="removeExisting(t)">
          {{ t }}
        </el-tag>
      </div>
    </div>

    <!-- 初始 / 分析中 -->
    <div v-if="generating" class="gen-block">
      <SkeletonLoader variant="card" :lines="2" />
      <div class="gen-label">
        <Compass :size="16" />
        <span>正在基于你的画像分析投递方向…</span>
      </div>
    </div>

    <div v-else-if="!candidates.length" class="empty-block">
      <p class="empty-text">点击「AI 分析」，基于画像生成岗位方向候选。</p>
    </div>

    <!-- 候选列表 -->
    <div v-else class="dir-grid">
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
          <button class="dir-detail-toggle" type="button" @click.stop="expanded[i] = !expanded[i]">
            {{ expanded[i] ? '收起详情' : '查看详情' }}
            <ChevronUp v-if="expanded[i]" :size="14" />
            <ChevronDown v-else :size="14" />
          </button>
          <div v-if="expanded[i]" class="dir-detail">{{ c.detail || '暂无更多详情' }}</div>
        </div>
      </div>
    </div>

    <el-alert
      v-if="errMsg"
      type="error"
      :title="errMsg"
      show-icon
      :closable="false"
      class="dialog-feedback"
    />
    <el-alert
      v-else-if="okMsg"
      type="success"
      :title="okMsg"
      show-icon
      :closable="false"
      class="dialog-feedback"
    />

    <template #footer>
      <span v-if="candidates.length" class="count-tip">{{ selected.length }} / 3 已选</span>
      <el-button text @click="visible = false">关闭</el-button>
      <el-button :disabled="generating || saving" @click="analyze">
        <Compass :size="14" style="margin-right: 4px" />AI 分析
      </el-button>
      <el-button
        type="primary"
        :loading="saving"
        :disabled="!selected.length || generating"
        @click="save"
      >
        保存到画像 ({{ selected.length }})
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, ChevronDown, ChevronUp, Compass } from 'lucide-vue-next'
import SkeletonLoader from './SkeletonLoader.vue'
import { confirmDirections, listProfileItems, recommendDirections, deleteProfileItem, createProfileItem } from '../api/profile'
import type { DirectionCandidate } from '../types'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'saved'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const candidates = ref<DirectionCandidate[]>([])
const selected = ref<string[]>([])
const expanded = ref<Record<number, boolean>>({})
const existing = ref<string[]>([])
const generating = ref(false)
const saving = ref(false)
const okMsg = ref('')
const errMsg = ref('')
const manualTitle = ref('')
const manualSaving = ref(false)

watch(visible, async (open) => {
  if (!open) return
  okMsg.value = ''
  errMsg.value = ''
  candidates.value = []
  selected.value = []
  expanded.value = {}
  manualTitle.value = ''
  await prefillExisting()
})

async function addManual() {
  const title = manualTitle.value.trim()
  if (!title) return
  if (existing.value.includes(title)) {
    errMsg.value = `「${title}」已在画像中`
    return
  }
  manualSaving.value = true
  errMsg.value = ''
  try {
    await createProfileItem({
      category: 'target',
      title,
      content: '',
      status: 'confirmed',
      item_type: 'fact',
    })
    manualTitle.value = ''
    okMsg.value = `已添加目标岗位「${title}」`
    await prefillExisting()
    emit('saved')
  } catch {
    errMsg.value = '添加失败，请重试'
  } finally {
    manualSaving.value = false
  }
}

/** 回填画像中已确认的目标岗位 */
async function prefillExisting() {
  try {
    const res = await listProfileItems('target', 'confirmed')
    existing.value = res.data.map((i) => i.title).filter(Boolean)
  } catch {
    existing.value = []
  }
}

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

async function analyze() {
  generating.value = true
  errMsg.value = ''
  okMsg.value = ''
  candidates.value = []
  selected.value = []
  expanded.value = {}
  try {
    const res = await recommendDirections()
    candidates.value = res.data || []
    if (!candidates.value.length) errMsg.value = '画像分析未生成有效方向，请完善画像后重试'
  } catch (e) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    errMsg.value = typeof detail === 'string' && detail ? detail : '画像方向推荐失败，请稍后重试'
  } finally {
    generating.value = false
  }
}

async function save() {
  if (!selected.value.length) return
  saving.value = true
  errMsg.value = ''
  okMsg.value = ''
  try {
    const chosen = candidates.value.filter((c) => selected.value.includes(c.title))
    const res = await confirmDirections(chosen)
    ElMessage.success(`已保存 ${res.data.length} 个投递方向到个人画像`)
    emit('saved')
    visible.value = false
  } catch (e) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    errMsg.value = typeof detail === 'string' && detail ? detail : '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

async function removeExisting(title: string) {
  try {
    await ElMessageBox.confirm(`从画像中移除目标方向「${title}」？`, '移除方向', {
      confirmButtonText: '移除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    const res = await listProfileItems('target', 'confirmed')
    const item = res.data.find((i) => i.title === title)
    if (!item) {
      await prefillExisting()
      return
    }
    await deleteProfileItem(item.id)
    existing.value = existing.value.filter((t) => t !== title)
    ElMessage.success('已从画像移除')
    emit('saved')
  } catch {
    ElMessage.error('移除失败，请重试')
  }
}
</script>

<style scoped>
.dialog-hint {
  margin: 0 0 var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}
.manual-add {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}
.existing {
  margin-bottom: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border: var(--border-light);
  border-radius: var(--radius-md);
  background: var(--color-accent-50);
}
.existing-label {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}
.existing-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.gen-block {
  padding: var(--space-4);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--color-accent-50);
}
.gen-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
  color: var(--color-accent-600);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
}
.empty-block {
  padding: var(--space-6) 0;
  text-align: center;
}
.empty-text {
  margin: 0;
  color: var(--color-text-disabled);
  font-size: var(--text-sm);
}
.dir-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-3);
  max-height: 360px;
  overflow-y: auto;
}
.dir-card {
  position: relative;
  display: flex;
  gap: var(--space-3);
  padding: var(--space-4);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-default),
    box-shadow var(--duration-normal) var(--ease-default);
}
.dir-card:hover {
  border-color: var(--color-accent-400);
  box-shadow: var(--shadow-md);
}
.dir-card.selected {
  border-color: var(--color-accent-600);
  box-shadow: 0 0 0 1px var(--color-accent-600) inset;
  background: var(--color-accent-50);
}
.dir-radio {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  border: 1.5px solid var(--color-gray-300);
  display: grid;
  place-items: center;
  color: var(--color-bg-elevated);
  margin-top: 2px;
}
.dir-radio.on {
  background: var(--color-accent-600);
  border-color: var(--color-accent-600);
}
.dir-card-title {
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}
.dir-card-reason {
  margin-top: var(--space-1);
  font-size: var(--text-xs);
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
  font-size: var(--text-xs);
  color: var(--color-accent-600);
  cursor: pointer;
}
.dir-detail {
  margin-top: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}
.dialog-feedback {
  margin-top: var(--space-4);
  border-radius: var(--radius-md);
}
.count-tip {
  float: left;
  line-height: 32px;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-right: var(--space-3);
}
</style>
