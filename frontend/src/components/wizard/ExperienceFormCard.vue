<template>
  <div class="exp-card">
    <div class="exp-card-head">
      <span class="exp-no">{{ label }} {{ index + 1 }}</span>
      <span class="exp-spacer" />
      <el-button size="small" text @click="$emit('toggle-star')">
        <Wand2 :size="13" style="margin-right: 3px" />{{ starOpen ? '收起 STAR' : 'STAR（可选）' }}
      </el-button>
      <el-button size="small" text @click="$emit('move', -1)"><ArrowUp :size="13" /></el-button>
      <el-button size="small" text @click="$emit('move', 1)"><ArrowDown :size="13" /></el-button>
      <el-button size="small" text type="danger" @click="$emit('remove')"><Trash2 :size="13" /></el-button>
    </div>
    <el-form label-width="88px" class="gen-form">
      <div class="form-grid">
        <el-form-item :label="nameLabel">
          <el-input v-model="model.company" :placeholder="namePlaceholder" />
        </el-form-item>
        <el-form-item :label="titleLabel">
          <el-input v-model="model.title" :placeholder="titlePlaceholder" />
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="model.start"
            type="month"
            value-format="YYYY-MM"
            placeholder="如 2024-06"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <div class="period-end">
            <el-checkbox v-model="model.current">至今</el-checkbox>
            <el-date-picker
              v-model="model.end"
              type="month"
              value-format="YYYY-MM"
              placeholder="如 2024-09"
              :disabled="model.current"
              style="flex: 1"
            />
          </div>
        </el-form-item>
        <el-form-item v-if="showTech" label="技术栈">
          <el-input v-model="model.tech_stack" placeholder="如 Vue3、FastAPI、MySQL" />
        </el-form-item>
      </div>
      <el-form-item :label="dutyLabel">
        <el-input
          v-model="model.duty"
          type="textarea"
          :rows="4"
          :placeholder="dutyPlaceholder"
        />
      </el-form-item>
      <el-form-item label="成果">
        <el-input
          v-model="model.achievement"
          type="textarea"
          :rows="3"
          placeholder="尽量量化：负责/提升了什么，结果如何"
        />
      </el-form-item>
      <template v-if="starOpen">
        <div class="star-divider">STAR 结构化（可选，可 AI 批量生成）</div>
        <el-form-item label="情境"><el-input v-model="model.situation" type="textarea" :rows="2" placeholder="S：背景与挑战" /></el-form-item>
        <el-form-item label="任务"><el-input v-model="model.task" type="textarea" :rows="2" placeholder="T：目标与职责" /></el-form-item>
        <el-form-item label="行动"><el-input v-model="model.action" type="textarea" :rows="3" placeholder="A：做了什么、用了什么方法" /></el-form-item>
        <el-form-item label="成果"><el-input v-model="model.result" type="textarea" :rows="2" placeholder="R：可量化的结果" /></el-form-item>
      </template>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ArrowUp, ArrowDown, Trash2, Wand2 } from 'lucide-vue-next'
import type { WizardExpEntry } from '../../types'

const model = defineModel<WizardExpEntry>({ required: true })

defineProps<{
  index: number
  label: string
  nameLabel: string
  titleLabel: string
  namePlaceholder: string
  titlePlaceholder: string
  dutyLabel: string
  dutyPlaceholder: string
  showTech: boolean
  starOpen: boolean
}>()

defineEmits<{
  (e: 'remove'): void
  (e: 'move', dir: number): void
  (e: 'toggle-star'): void
}>()
</script>

<style scoped>
.exp-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  background: var(--color-bg-elevated);
}
.exp-card-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.exp-no {
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}
.exp-spacer {
  flex: 1;
}
.gen-form {
  width: 100%;
  max-width: none;
}
.gen-form :deep(.el-form-item__content),
.gen-form :deep(.el-input),
.gen-form :deep(.el-textarea),
.gen-form :deep(.el-date-editor) {
  width: 100%;
  max-width: 100%;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 var(--space-5);
}
@media (max-width: 720px) {
  .form-grid { grid-template-columns: 1fr; }
}
.period-end {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.star-divider {
  margin: var(--space-3) 0 var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px dashed var(--color-border);
  font-size: var(--text-xs);
  color: var(--color-accent-600);
  font-weight: 600;
}
</style>
