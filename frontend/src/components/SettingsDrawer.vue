<template>
  <el-drawer :model-value="modelValue" title="设置" @close="$emit('update:modelValue', false)">
    <div class="settings-body">
      <el-form class="settings-form" label-width="90px">
        <!-- 简历 -->
        <div class="settings-group">
          <h3 class="settings-group-title">简历</h3>

          <el-form-item label="简历模板">
            <el-select v-model="form.preferred_template" @change="save">
              <el-option label="现代" value="modern" />
              <el-option label="经典" value="classic" />
              <el-option label="简洁" value="minimal" />
            </el-select>
          </el-form-item>

          <el-form-item label="简历风格">
            <el-select v-model="form.resume_style" @change="save">
              <el-option label="简洁" value="concise" />
              <el-option label="详细" value="detailed" />
            </el-select>
          </el-form-item>
        </div>

        <el-divider class="settings-divider" />

        <!-- 求职偏好 -->
        <div class="settings-group">
          <h3 class="settings-group-title">求职偏好</h3>

          <el-form-item label="目标行业">
            <el-input v-model="jobPrefs.industry" placeholder="如：互联网、金融" @change="save" />
          </el-form-item>

          <el-form-item label="目标岗位">
            <el-input v-model="jobPrefs.role" placeholder="如：后端工程师" @change="save" />
          </el-form-item>

          <el-form-item label="期望薪资">
            <el-input v-model="jobPrefs.salary" placeholder="如：30-50k" @change="save" />
          </el-form-item>
        </div>
      </el-form>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPreferences, updatePreferences } from '../api/preferences'

defineProps<{ modelValue: boolean }>()
defineEmits<{ 'update:modelValue': [val: boolean] }>()

const form = reactive({
  preferred_template: 'modern',
  resume_style: 'concise',
})

const jobPrefs = reactive({
  industry: '',
  role: '',
  salary: '',
})

onMounted(async () => {
  try {
    const res = await getPreferences()
    form.preferred_template = res.data.preferred_template
    form.resume_style = res.data.resume_style
    const jp = res.data.job_preferences || {}
    jobPrefs.industry = (jp.industry as string) || ''
    jobPrefs.role = (jp.role as string) || ''
    jobPrefs.salary = (jp.salary as string) || ''
  } catch {
    // 首次使用，无偏好
  }
})

async function save() {
  try {
    await updatePreferences({
      preferred_template: form.preferred_template,
      resume_style: form.resume_style,
      job_preferences: { ...jobPrefs },
    })
    ElMessage.success('设置已保存')
  } catch {
    ElMessage.error('保存失败')
  }
}
</script>

<style scoped>
/* 抽屉标题：衬线体 */
:deep(.el-drawer__header) {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: 0;
  padding-bottom: var(--space-4);
  border-bottom: var(--border-light);
}

.settings-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.settings-form {
  display: flex;
  flex-direction: column;
}

.settings-group {
  display: flex;
  flex-direction: column;
}

.settings-group-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--space-4);
  padding-bottom: var(--space-2);
  border-bottom: var(--border-light);
}

/* 选择器统一全宽 */
:deep(.el-select) {
  width: 100%;
}

.settings-divider {
  margin: var(--space-2) 0 var(--space-4);
  border-color: var(--color-gray-200);
}

:deep(.el-form-item__label) {
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  font-weight: var(--font-weight-medium);
}

:deep(.el-form-item) {
  margin-bottom: var(--space-5);
}
</style>
