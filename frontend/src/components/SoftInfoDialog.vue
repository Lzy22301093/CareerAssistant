<template>
  <el-dialog
    v-model="visible"
    title="编辑软性信息"
    width="660px"
    :append-to-body="true"
    class="soft-dialog"
  >
    <p class="dialog-hint">
      手动填写，或用 AI 辅助生成后修改。内容写入个人画像（分类：软性信息），简历生成、岗位匹配与模拟面试会自动复用。
    </p>

    <el-form label-width="104px" @submit.prevent>
      <el-form-item label="性格特点">
        <el-input v-model="form.personality" placeholder="如：沉稳、有责任心" />
      </el-form-item>
      <el-form-item label="职业愿景">
        <el-input v-model="form.vision" placeholder="如：3 年内成长为能独立负责模块的后端工程师" />
      </el-form-item>
      <el-form-item label="不感兴趣方向">
        <el-input v-model="form.disinterested" placeholder="如：纯销售岗、频繁出差" />
      </el-form-item>
      <el-form-item label="自我评价">
        <el-input
          v-model="form.self_eval"
          type="textarea"
          :rows="4"
          placeholder="一段真诚的自我评价，或点下方「AI 生成」"
        />
      </el-form-item>
    </el-form>

    <!-- 生成中 -->
    <div v-if="generating" class="gen-block">
      <SkeletonLoader variant="text" :lines="3" />
      <div class="gen-label">
        <Sparkles :size="16" />
        <span>正在基于你的画像生成软性信息…</span>
      </div>
    </div>

    <!-- 单条反馈 -->
    <el-alert
      v-else-if="okMsg"
      type="success"
      :title="okMsg"
      show-icon
      :closable="false"
      class="dialog-feedback"
    />
    <el-alert
      v-else-if="errMsg"
      type="error"
      :title="errMsg"
      show-icon
      :closable="false"
      class="dialog-feedback"
    />

    <template #footer>
      <el-button text @click="visible = false">取消</el-button>
      <el-button :disabled="generating || saving" @click="generate">
        <Sparkles :size="14" style="margin-right: 4px" />AI 生成
      </el-button>
      <el-button type="primary" :loading="saving" :disabled="!hasAnyForm || generating" @click="save">
        保存到画像
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Sparkles } from 'lucide-vue-next'
import SkeletonLoader from './SkeletonLoader.vue'
import { generateSoftInfo, saveSoftInfo, listProfileItems } from '../api/profile'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'saved'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const form = reactive({ personality: '', vision: '', disinterested: '', self_eval: '' })
const generating = ref(false)
const saving = ref(false)
const okMsg = ref('')
const errMsg = ref('')

const hasAnyForm = computed(() => Object.values(form).some((v) => (v || '').trim().length > 0))

/** 后端保存用的字段标题 → 表单字段（与 soft_info_service.FIELD_TO_LABEL 一致） */
const TITLE_TO_FIELD: Record<string, keyof typeof form> = {
  性格特点: 'personality',
  职业愿景: 'vision',
  '不感兴趣的方向': 'disinterested',
  自我评价: 'self_eval',
}

watch(visible, async (open) => {
  if (!open) return
  okMsg.value = ''
  errMsg.value = ''
  await prefill()
})

/** 回填画像中已有的软性信息，便于在此基础上修改 */
async function prefill() {
  try {
    const res = await listProfileItems('soft')
    for (const item of res.data) {
      const field = TITLE_TO_FIELD[item.title]
      if (field && item.content) form[field] = item.content
    }
  } catch {
    // 回填失败不阻塞使用
  }
}

async function generate() {
  generating.value = true
  errMsg.value = ''
  okMsg.value = ''
  try {
    const res = await generateSoftInfo()
    form.personality = res.data.personality || form.personality
    form.vision = res.data.vision || form.vision
    form.disinterested = res.data.disinterested || form.disinterested
    form.self_eval = res.data.self_eval || form.self_eval
    okMsg.value = '已生成，可在此基础上修改，然后保存到画像。'
  } catch (e) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    errMsg.value = typeof detail === 'string' && detail ? detail : '软性信息生成失败，请稍后重试'
  } finally {
    generating.value = false
  }
}

async function save() {
  if (!hasAnyForm.value) return
  saving.value = true
  errMsg.value = ''
  okMsg.value = ''
  try {
    const res = await saveSoftInfo({
      personality: form.personality.trim(),
      vision: form.vision.trim(),
      disinterested: form.disinterested.trim(),
      self_eval: form.self_eval.trim(),
    })
    ElMessage.success(`已保存 ${res.data.length} 项软性信息到个人画像`)
    emit('saved')
    visible.value = false
  } catch (e) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    errMsg.value = typeof detail === 'string' && detail ? detail : '保存失败，请重试'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.dialog-hint {
  margin: 0 0 var(--space-5);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}
.gen-block {
  margin-top: var(--space-4);
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
.dialog-feedback {
  margin-top: var(--space-4);
  border-radius: var(--radius-md);
}
</style>
