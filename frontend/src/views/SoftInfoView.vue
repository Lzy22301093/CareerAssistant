<template>
  <div class="soft-page">
    <AppNav>
      <el-button text @click="goKnowledgeBase">去完善画像</el-button>
    </AppNav>
    <div class="soft-titlebar">
      <div class="soft-title">软性信息</div>
      <p class="soft-sub">补充性格、愿景与自我评价，让画像更有温度</p>
    </div>

    <div class="soft-body">
      <section class="soft-panel">
        <p class="hint">补充你的性格、职业愿景与自我评价，让简历更有温度。也可以让 AI 根据你的画像帮你生成。</p>

        <el-form label-width="92px" style="max-width: 640px">
          <el-form-item label="性格特点">
            <el-input v-model="form.personality" placeholder="如：沉稳、有责任心" />
          </el-form-item>
          <el-form-item label="职业愿景">
            <el-input v-model="form.vision" placeholder="如：希望在 3 年内成长为能独立负责模块的后端工程师" />
          </el-form-item>
          <el-form-item label="不感兴趣方向">
            <el-input v-model="form.disinterested" placeholder="如：纯销售岗、频繁出差" />
          </el-form-item>
          <el-form-item label="自我评价">
            <div class="self-eval-wrap">
              <div class="self-eval-tools">
                <span class="self-eval-label">可手动填写，或让 AI 根据画像生成</span>
                <el-button size="small" text type="primary" :disabled="generating" @click="generate">
                  <Sparkles :size="14" /> AI 生成
                </el-button>
              </div>
              <el-input v-model="form.self_eval" type="textarea" :rows="4" placeholder="一段真诚的自我评价，或点上方让 AI 生成" />
            </div>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="saving" :disabled="!hasAnyForm" @click="save">
              保存为画像条目
            </el-button>
            <el-button text @click="reset">清空</el-button>
          </el-form-item>
        </el-form>

        <!-- 生成中块（重排：清晰的状态区而非底部突兀 loading） -->
        <div v-if="generating" class="gen-block">
          <SkeletonLoader variant="text" :lines="3" />
          <div class="gen-label">
            <Sparkles :size="16" />
            <span>正在基于你的画像生成软性信息…</span>
          </div>
        </div>

        <!-- 统一单条反馈：成功 / 错误只显示一条 -->
        <el-alert
          v-else-if="okMsg"
          class="soft-feedback"
          type="success"
          :title="okMsg"
          show-icon
          :closable="false"
        />
        <el-alert
          v-else-if="errMsg"
          class="soft-feedback"
          type="error"
          :title="errMsg"
          show-icon
          :closable="false"
        />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Sparkles } from 'lucide-vue-next'
import AppNav from '../components/AppNav.vue'
import SkeletonLoader from '../components/SkeletonLoader.vue'
import { generateSoftInfo, saveSoftInfo } from '../api/profile'

const router = useRouter()
const form = reactive({ personality: '', vision: '', disinterested: '', self_eval: '' })
const generating = ref(false)
const saving = ref(false)
const errMsg = ref('')
const okMsg = ref('')

const hasAnyForm = computed(() =>
  Object.values(form).some((v) => (v || '').trim().length > 0),
)

function goKnowledgeBase() {
  router.push('/knowledge-base')
}

function reset() {
  form.personality = ''
  form.vision = ''
  form.disinterested = ''
  form.self_eval = ''
  okMsg.value = ''
  errMsg.value = ''
}

async function generate() {
  generating.value = true
  errMsg.value = ''
  okMsg.value = ''
  try {
    const res = await generateSoftInfo()
    form.personality = res.data.personality || ''
    form.vision = res.data.vision || ''
    form.disinterested = res.data.disinterested || ''
    form.self_eval = res.data.self_eval || ''
    okMsg.value = '已生成，可在此基础上修改，然后保存。'
  } catch (e) {
    const detail = (e as any)?.response?.data?.detail
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
  const data = {
    personality: form.personality.trim(),
    vision: form.vision.trim(),
    disinterested: form.disinterested.trim(),
    self_eval: form.self_eval.trim(),
  }
  try {
    const res = await saveSoftInfo(data)
    okMsg.value = `已保存 ${res.data.length} 项软性信息到个人知识库（分类：软性信息）。`
    ElMessage.success('软性信息已保存')
  } catch {
    errMsg.value = '保存失败，请重试'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.soft-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-page);
}
.soft-titlebar {
  padding: var(--space-6) var(--space-8) var(--space-4);
  border-bottom: var(--border-light);
  background: color-mix(in srgb, var(--color-bg) 92%, white);
}
.soft-title {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: var(--weight-semibold);
  letter-spacing: -0.01em;
  color: var(--color-text-primary);
}
.soft-sub {
  margin: var(--space-1) 0 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.soft-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-8);
}
.soft-panel {
  max-width: 720px;
  margin: 0 auto;
  background: var(--color-bg);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-6);
}
.hint {
  margin: 0 0 var(--space-5);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}
.self-eval-wrap {
  width: 100%;
}
.self-eval-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}
.self-eval-label {
  font-size: var(--text-xs);
  color: var(--color-text-disabled);
}

/* 生成中块 */
.gen-block {
  margin-top: var(--space-5);
  padding: var(--space-5);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--color-accent-50);
}
.gen-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-accent-600);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
}

/* 统一单条反馈 */
.soft-feedback {
  margin-top: var(--space-5);
  border-radius: var(--radius-md);
}
</style>
