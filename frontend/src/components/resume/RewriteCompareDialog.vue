<template>
  <el-dialog
    :model-value="visible"
    title="AI 改写建议对比"
    width="860px"
    :close-on-click-modal="false"
    @update:model-value="emit('close')"
  >
    <div v-if="result && section" class="compare">
      <!-- 顶部：改写思路 + 来源核对警告 -->
      <div class="approach-banner">
        <span class="approach-label">{{ candidate.approach || '改写候选' }}</span>
        <span v-if="candidate.changes.length" class="approach-changes">{{ candidate.changes.join('；') }}</span>
      </div>
      <el-alert
        v-if="result.needs_source_confirmation"
        type="warning"
        :closable="false"
        class="source-alert"
        title="改写引入了画像与原文中没有的内容，采纳前请核对来源"
      >
        <template #default>
          <div v-if="result.new_numbers.length" class="confirm-list">新增数字：{{ result.new_numbers.join('、') }}</div>
          <div v-if="result.new_claims.length" class="confirm-list">新增陈述：{{ result.new_claims.join('；') }}</div>
        </template>
      </el-alert>

      <!-- 候选切换 -->
      <div class="candidate-bar">
        <div class="candidate-info">
          <span class="candidate-name">候选 {{ candIndex + 1 }} / {{ result.candidates.length }}</span>
          <span class="candidate-approach">{{ candidate.approach }}</span>
        </div>
        <el-button size="small" :disabled="result.candidates.length < 2" @click="nextCandidate">
          <RefreshCw :size="14" style="margin-right: 4px" />换个版本
        </el-button>
      </div>

      <!-- 左红删 / 右绿增 双栏 diff -->
      <div class="diff-head">
        <div class="diff-col-title">原文<span class="legend red">红=删除</span></div>
        <div class="diff-col-title">改写后<span class="legend green">绿=新增</span></div>
      </div>
      <div class="diff-body">
        <div class="diff-col">
          <template v-for="(row, idx) in rows" :key="'l' + idx">
            <p v-if="row.oldText !== null" class="diff-line" :class="{ del: row.type === 'del' }">
              {{ row.oldText }}
            </p>
          </template>
        </div>
        <div class="diff-col">
          <template v-for="(row, idx) in rows" :key="'r' + idx">
            <p v-if="row.newText !== null" class="diff-line" :class="{ ins: row.type === 'ins' }">
              {{ row.newText }}
            </p>
          </template>
        </div>
      </div>
      <div v-if="result.advice" class="advice">
        <Lightbulb :size="14" class="advice-icon" />{{ result.advice }}
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" :loading="adopting" @click="onAdopt">采纳并应用</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Lightbulb, RefreshCw } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import type { RewriteResult, ResumeLibrarySection } from '../../types'
import { diffLines } from '../../utils/diff'
import { adoptSectionRewrite } from '../../api/resumeLibrary'

const props = defineProps<{
  visible: boolean
  result: RewriteResult | null
  section: ResumeLibrarySection | null
}>()

const emit = defineEmits<{ (e: 'close'): void; (e: 'adopted', version: number): void }>()

const candIndex = ref(0)
const adopting = ref(false)

const candidate = computed(() => props.result?.candidates[candIndex.value] ?? { rewrite: '', approach: '', changes: [], new_numbers: [] })

const rows = computed(() => {
  if (!props.section || !props.result) return []
  return diffLines(props.section.content ?? '', candidate.value.rewrite)
})

watch(
  () => props.visible,
  (v) => {
    if (v) candIndex.value = 0
  }
)

function nextCandidate() {
  if (!props.result) return
  candIndex.value = (candIndex.value + 1) % props.result.candidates.length
}

async function onAdopt() {
  if (!props.result || !props.section) return
  adopting.value = true
  try {
    const version = await adoptSectionRewrite(props.result.version_id, props.section.id, candidate.value.rewrite)
    ElMessage.success(`已采纳并生成新版本 v${version.version}，旧版本保留可回滚`)
    emit('adopted', version.version)
    emit('close')
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '采纳失败，请重试')
  } finally {
    adopting.value = false
  }
}
</script>

<style scoped>
.compare {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.approach-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding: var(--space-2) var(--space-3);
  background: var(--color-accent-50);
  border-left: 3px solid var(--color-accent-600);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}
.approach-label {
  font-weight: var(--weight-semibold);
  color: var(--color-accent-700);
  flex-shrink: 0;
}
.approach-changes {
  color: var(--color-text-secondary);
}
.source-alert {
  border-radius: var(--radius-sm);
}
.confirm-list {
  font-size: var(--text-sm);
  line-height: 1.6;
}
.candidate-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border: var(--border-light);
  border-radius: var(--radius-md);
  background: var(--color-gray-50);
}
.candidate-info {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}
.candidate-name {
  font-weight: var(--weight-semibold);
  color: var(--color-accent-600);
  font-size: var(--text-sm);
}
.candidate-approach {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.diff-head {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}
.diff-col-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.legend {
  font-size: var(--text-2xs);
  padding: 1px 6px;
  border-radius: var(--radius-full);
}
.legend.red {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}
.legend.green {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}
.diff-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
  max-height: 46vh;
  overflow: auto;
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-2);
}
.diff-col {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.diff-line {
  margin: 0;
  padding: 1px 6px;
  font-size: var(--text-sm);
  line-height: 1.7;
  border-radius: var(--radius-sm);
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--color-text-primary);
}
.diff-line.del {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
  text-decoration: line-through;
}
.diff-line.ins {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}
.advice {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.advice-icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--color-accent-600);
}
</style>
