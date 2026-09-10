<template>
  <el-dialog
    v-model="visible"
    title="完善画像"
    width="820px"
    :append-to-body="true"
    :close-on-click-modal="false"
    class="profile-wizard-dialog"
    @closed="reset"
  >
    <!-- 顶部步骤条（FResume 风格）：基本信息 / 教育经历 / 个人奖项 / 社交账号 / 个人头像 -->
    <div class="wiz-steps">
      <button
        v-for="(s, i) in STEPS"
        :key="s.key"
        class="wiz-step"
        :class="{ active: step === i + 1, done: step > i + 1 }"
        @click="step = i + 1"
      >
        <span class="wiz-step-no" :class="{ done: step > i + 1 }">
          <Check v-if="step > i + 1" :size="14" />
          <span v-else>{{ i + 1 }}</span>
        </span>
        <span class="wiz-step-info">
          <b>{{ s.label }}</b>
          <small>{{ s.sub }}</small>
        </span>
      </button>
    </div>

    <div class="wiz-body">
      <!-- 01 基本信息 -->
      <template v-if="step === 1">
        <div v-if="basicHint" class="wiz-hint">{{ basicHint }}</div>
        <div class="wiz-grid">
          <div class="wiz-field" v-for="f in BASIC_FIELDS" :key="f.key">
            <label :class="{ req: f.required }">{{ f.label }}<span v-if="f.required" class="req-mark">*</span></label>
            <el-input v-model="form.basic_info[f.key]" :placeholder="f.placeholder" clearable />
          </div>
        </div>
      </template>

      <!-- 02 教育经历 -->
      <template v-else-if="step === 2">
        <div v-for="(edu, i) in form.education" :key="i" class="wiz-card">
          <div class="wiz-card-head">
            <span class="idx">EDU · {{ String(i + 1).padStart(2, '0') }}</span>
            <el-button text type="danger" size="small" @click="form.education.splice(i, 1)">
              <Trash2 :size="14" /> 删除
            </el-button>
          </div>
          <div class="wiz-grid">
            <div class="wiz-field">
              <label class="req">学校<span class="req-mark">*</span></label>
              <el-input v-model="edu.school" placeholder="如：北京交通大学" />
            </div>
            <div class="wiz-field">
              <label class="req">学历<span class="req-mark">*</span></label>
              <el-select v-model="edu.degree" placeholder="选择学历" style="width: 100%">
                <el-option v-for="d in DEGREES" :key="d" :label="d" :value="d" />
              </el-select>
            </div>
            <div class="wiz-field">
              <label>专业</label>
              <el-input v-model="edu.major" placeholder="如：软件工程" />
            </div>
            <div class="wiz-field">
              <label>开始时间</label>
              <el-date-picker v-model="edu.start" type="month" value-format="YYYY-MM" placeholder="如：2020-09" style="width: 100%" />
            </div>
            <div class="wiz-field">
              <label>结束时间</label>
              <el-date-picker v-model="edu.end" type="month" value-format="YYYY-MM" placeholder="如：2024-06" style="width: 100%" />
            </div>
            <div class="wiz-field">
              <label>GPA</label>
              <el-input v-model="edu.gpa" placeholder="0.0 - 5.0" />
            </div>
          </div>
          <div class="wiz-field">
            <label>主修课程</label>
            <el-input v-model="edu.courses" type="textarea" :rows="2" placeholder="如：数据结构、计算机网络" />
          </div>
        </div>
        <button class="wiz-add" @click="addEducation">
          <Plus :size="14" style="margin-right: 4px" /> 新增教育经历
        </button>
      </template>

      <!-- 03 个人奖项 -->
      <template v-else-if="step === 3">
        <div class="wiz-field">
          <label class="req">个人奖项<span class="req-mark">*</span></label>
          <el-input
            v-model="form.awards"
            type="textarea"
            :rows="6"
            placeholder="每行一条，如：&#10;国家奖学金&#10;全国大学生数学建模竞赛一等奖"
          />
          <p class="wiz-sub">建议 20 字以上，每行一条，便于后续简历生成更完整的内容。</p>
        </div>
      </template>

      <!-- 04 社交账号 -->
      <template v-else-if="step === 4">
        <div v-for="(soc, i) in form.social" :key="i" class="wiz-card">
          <div class="wiz-card-head">
            <span class="idx">SOC · {{ String(i + 1).padStart(2, '0') }}</span>
            <el-button text type="danger" size="small" @click="form.social.splice(i, 1)">
              <Trash2 :size="14" /> 删除
            </el-button>
          </div>
          <div class="wiz-grid two">
            <div class="wiz-field">
              <label class="req">平台<span class="req-mark">*</span></label>
              <el-input v-model="soc.platform" placeholder="如：QQ / 微信 / 小红书" />
            </div>
            <div class="wiz-field">
              <label class="req">账号<span class="req-mark">*</span></label>
              <el-input v-model="soc.account" placeholder="如：2323613122" />
            </div>
          </div>
        </div>
        <button class="wiz-add" @click="form.social.push({ platform: '', account: '' })">
          <Plus :size="14" style="margin-right: 4px" /> 新增社交账号
        </button>
      </template>

      <!-- 05 个人头像 -->
      <template v-else-if="step === 5">
        <div class="avatar-box">
          <div class="avatar-preview" :class="{ empty: !avatarPreview }">
            <img v-if="avatarPreview" :src="avatarPreview" alt="头像" />
            <UserRound v-else :size="40" />
          </div>
          <div class="avatar-info">
            <p>支持 JPG / PNG / WEBP，自动居中裁剪为 256×256。</p>
            <p class="muted">这张头像将展示在个人知识库节点图中央，连接你的所有信息卡片。</p>
            <div class="avatar-actions">
              <el-button type="primary" :loading="avatarUploading" @click="fileInput?.click()">
                <Upload :size="14" style="margin-right: 4px" /> 上传头像
              </el-button>
              <el-button v-if="avatarPreview" text @click="clearAvatar">重新选择</el-button>
            </div>
            <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onAvatarChange" />
          </div>
        </div>
      </template>

      <!-- 06 其他分类（项目/技能/目标/自我评价/面试反馈） -->
      <template v-else-if="step === 6">
        <p class="wiz-sub">补充不在上面五类里的条项（项目经历 / 专业技能 / 目标岗位 / 自我评价 / 面试反馈）。</p>
        <div v-for="(ext, i) in form.extra" :key="i" class="wiz-card">
          <div class="wiz-card-head">
            <span class="idx">OTH · {{ String(i + 1).padStart(2, '0') }}</span>
            <el-button text type="danger" size="small" @click="form.extra.splice(i, 1)">
              <Trash2 :size="14" /> 删除
            </el-button>
          </div>
          <div class="wiz-grid two">
            <div class="wiz-field">
              <label class="req">分类<span class="req-mark">*</span></label>
              <el-select v-model="ext.category" placeholder="选择分类" style="width: 100%">
                <el-option v-for="c in EXTRA_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
              </el-select>
            </div>
            <div class="wiz-field">
              <label class="req">标题<span class="req-mark">*</span></label>
              <el-input v-model="ext.title" placeholder="如：arXiv 论文问答系统" />
            </div>
          </div>
          <div class="wiz-field">
            <label>内容</label>
            <el-input v-model="ext.content" type="textarea" :rows="3" placeholder="具体事实 / 经历描述" />
          </div>
        </div>
        <button class="wiz-add" @click="addExtra">
          <Plus :size="14" style="margin-right: 4px" /> 新增条目
        </button>
      </template>
    </div>

    <template #footer>
      <div class="wiz-foot">
        <div class="wiz-progress">
          <span class="done-count">已填 {{ filledCount }}</span>
          <span class="wiz-req">必填 * · 完成后进入系统</span>
        </div>
        <div class="wiz-foot-actions">
          <el-button v-if="step > 1 && step <= STEPS.length" @click="step--">上一步</el-button>
          <el-button v-if="step < STEPS.length" type="primary" @click="next">{{ step === STEPS.length ? '完成' : '保存并下一步' }} <ArrowRight :size="14" style="margin-left: 4px" /></el-button>
          <el-button v-else type="primary" :loading="saving" @click="saveAll">完成 →</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ArrowRight, Check, Plus, Trash2, Upload, UserRound,
} from 'lucide-vue-next'
import { saveProfileForm, getProfileForm } from '../api/profile'
import { getPhotoInfo, uploadPhotoFile } from '../api/resumeGeneration'
import type { ProfileEducationEntry, ProfileExtraEntry, ProfileFormSave, ProfileSocialEntry } from '../types'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void; (e: 'saved'): void }>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const STEPS = [
  { key: 'basic', label: '基本信息', sub: '姓名·邮箱·手机' },
  { key: 'education', label: '教育经历', sub: '学校·学历·专业' },
  { key: 'award', label: '个人奖项', sub: '奖学金·竞赛·荣誉等' },
  { key: 'social', label: '社交账号', sub: '微信·QQ·小红书等' },
  { key: 'avatar', label: '个人头像', sub: '上传头像作为信息墙' },
  { key: 'other', label: '其他画像', sub: '项目·技能·目标等' },
]

const BASIC_FIELDS = [
  { key: 'name', label: '姓名', required: true, placeholder: '如：栗子' },
  { key: 'phone', label: '手机', required: true, placeholder: '如：19823342343' },
  { key: 'email', label: '邮箱', required: true, placeholder: '如：2378166881@qq.com' },
  { key: 'location', label: '所在地点', required: true, placeholder: '如：北京' },
  { key: 'gender', label: '性别', required: false, placeholder: '如：男' },
  { key: 'birthday', label: '出生日期', required: false, placeholder: '如：2004-04-08' },
  { key: 'nationality', label: '国籍', required: false, placeholder: '如：中国' },
  { key: 'hometown', label: '家乡', required: false, placeholder: '如：请输家乡' },
]

const DEGREES = ['高中', '大专', '本科', '硕士', '博士']

const EXTRA_OPTIONS = [
  { value: 'experience', label: '项目经历' },
  { value: 'skill', label: '专业技能' },
  { value: 'target', label: '目标岗位' },
  { value: 'soft', label: '自我评价' },
  { value: 'interview_feedback', label: '面试反馈' },
]

const step = ref(1)
const saving = ref(false)
const avatarUploading = ref(false)
const avatarPreview = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const form = reactive<ProfileFormSave>({
  basic_info: {},
  education: [] as ProfileEducationEntry[],
  awards: '',
  social: [] as ProfileSocialEntry[],
  extra: [] as ProfileExtraEntry[],
})

const filledCount = computed(() => {
  const bi = Object.values(form.basic_info).filter((v) => (v || '').trim()).length
  return bi
    + form.education.filter((e) => e.school).length
    + (form.awards ? 1 : 0)
    + form.social.filter((s) => s.platform || s.account).length
    + form.extra.filter((e) => e.title).length
})

const basicHint = computed(() => {
  const keys = Object.keys(form.basic_info).filter((k) => (form.basic_info[k] || '').trim())
  const total = BASIC_FIELDS.length
  return `已填写 ${keys.length} / ${total} 项基本信息。`
})

watch(() => props.modelValue, async (open) => {
  if (open) await load()
})

async function load() {
  step.value = 1
  // 重置
  Object.assign(form, {
    basic_info: {}, education: [], awards: '', social: [], extra: [],
  } as ProfileFormSave)
  try {
    const res = await getProfileForm()
    const d = res.data || {}
    Object.assign(form.basic_info, d.basic_info || {})
    form.education = (d.education || []).map((e) => ({ ...e }))
    form.awards = (d.awards || []).join('\n')
    form.social = (d.social || []).map((s) => ({ ...s }))
    form.extra = (d.extra || []).map((e) => ({ ...e }))
  } catch {
    // 静默：无已存数据
  }
  // 头像
  try {
    const photo = await getPhotoInfo()
    if (photo.data) avatarPreview.value = `${photo.data.url}?t=${Date.now()}`
  } catch {
    avatarPreview.value = ''
  }
}

function addEducation() {
  form.education.push({ school: '', degree: '', major: '', courses: '', start: '', end: '', gpa: '' })
}
function addExtra() {
  form.extra.push({ category: 'experience', title: '', content: '' })
}

function next() {
  if (step.value === 1) {
    const required = ['name', 'phone', 'email']
    const missing = required.filter((k) => !(form.basic_info[k] || '').trim())
    if (missing.length) {
      ElMessage.warning('请先填写必填的基本信息（姓名 / 手机 / 邮箱）')
      return
    }
  }
  step.value = Math.min(STEPS.length, step.value + 1)
}

async function onAvatarChange(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  avatarUploading.value = true
  try {
    const res = await uploadPhotoFile(file)
    avatarPreview.value = `${res.data.url}?t=${Date.now()}`
    ElMessage.success('头像已上传')
  } catch {
    ElMessage.error('上传失败（支持 JPG/PNG/WEBP）')
  } finally {
    avatarUploading.value = false
    input.value = ''
  }
}

function clearAvatar() {
  avatarPreview.value = ''
}

function reset() {
  step.value = 1
}

async function saveAll() {
  saving.value = true
  try {
    await saveProfileForm({
      basic_info: form.basic_info,
      education: form.education.map((e) => ({ ...e })),
      awards: form.awards,
      social: form.social.map((s) => ({ ...s })),
      extra: form.extra.map((e) => ({ ...e })),
    })
    ElMessage.success('画像已保存')
    visible.value = false
    emit('saved')
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '保存失败，请重试')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.wiz-steps {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
  margin-bottom: var(--space-5);
}
.wiz-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  cursor: pointer;
  text-align: left;
  transition: all var(--duration-fast) var(--ease-default);
}
.wiz-step:hover { border-color: var(--color-accent-300); }
.wiz-step.active {
  border-color: var(--color-accent-600);
  background: var(--color-accent-50);
  box-shadow: 0 0 0 1px var(--color-accent-600) inset;
}
.wiz-step.done { border-color: var(--color-accent-200); }
.wiz-step-no {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  color: var(--color-text-secondary);
  background: var(--color-gray-100);
}
.wiz-step.active .wiz-step-no { background: var(--color-accent-600); color: #fff; }
.wiz-step-no.done { background: var(--color-success-600); color: #fff; }
.wiz-step-info b { font-size: var(--text-sm); color: var(--color-text-primary); display: block; }
.wiz-step-info small { font-size: var(--text-2xs); color: var(--color-text-tertiary); }

.wiz-body {
  max-height: 52vh;
  overflow-y: auto;
  padding: var(--space-2);
}
.wiz-hint { color: var(--color-text-secondary); font-size: var(--text-sm); margin-bottom: var(--space-4); }
.wiz-sub { color: var(--color-text-tertiary); font-size: var(--text-xs); margin: var(--space-2) 0 0; }

.wiz-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-4);
}
.wiz-grid.two { grid-template-columns: 1fr 1fr; }
.wiz-field { display: flex; flex-direction: column; gap: 6px; margin-bottom: var(--space-3); }
.wiz-field label { font-size: var(--text-xs); color: var(--color-text-secondary); }
.wiz-field label.req { font-weight: var(--weight-medium); }
.req-mark { color: var(--color-danger-600); margin-left: 2px; }

.wiz-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  background: var(--color-bg-elevated);
}
.wiz-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}
.idx { font-family: var(--font-display); font-size: var(--text-xs); letter-spacing: 0.06em; color: var(--color-text-tertiary); }

.wiz-add {
  display: inline-flex;
  align-items: center;
  padding: 8px 14px;
  border: 1px dashed var(--color-accent-400);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-accent-600);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  cursor: pointer;
}
.wiz-add:hover { background: var(--color-accent-50); }

.avatar-box { display: flex; gap: var(--space-6); align-items: flex-start; }
.avatar-preview {
  width: 120px; height: 120px;
  border-radius: 50%;
  overflow: hidden;
  display: grid; place-items: center;
  background: var(--color-gray-100);
  color: var(--color-text-tertiary);
  flex-shrink: 0;
  border: 1px solid var(--color-border);
}
.avatar-preview:not(.empty) img { width: 100%; height: 100%; object-fit: cover; }
.avatar-info p { margin: 0 0 var(--space-2); color: var(--color-text-secondary); font-size: var(--text-sm); }
.avatar-info .muted { color: var(--color-text-tertiary); font-size: var(--text-xs); }
.avatar-actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }

.wiz-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.wiz-progress { display: flex; align-items: baseline; gap: var(--space-3); }
.done-count { font-size: var(--text-sm); font-weight: var(--weight-medium); color: var(--color-accent-600); }
.wiz-req { font-size: var(--text-xs); color: var(--color-text-tertiary); }
.wiz-foot-actions { display: flex; gap: var(--space-2); }
</style>
