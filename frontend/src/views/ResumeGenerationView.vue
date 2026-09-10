<template>
  <div class="gen-page">
    <AppNav>
      <el-button text @click="onSaveDraft">暂存退出</el-button>
    </AppNav>

    <div class="gen-shell">
      <!-- 左：叙事栏 -->
      <aside class="gen-narrative">
        <p class="eyebrow">{{ currentStep.no }}</p>
        <h1 class="narr-title">{{ currentStep.title }}</h1>
        <p class="narr-desc">{{ currentStep.desc }}</p>
        <div class="narr-mark" aria-hidden="true">
          <component :is="currentStep.icon" :size="26" />
        </div>
      </aside>

      <!-- 右：内容 -->
      <section class="gen-main">
        <!-- 步骤导航 -->
        <nav class="step-nav">
          <button
            v-for="(s, i) in STEPS"
            :key="s.key"
            class="step-chip"
            :class="{ active: wizard.step === i + 1, done: wizard.step > i + 1 }"
            @click="gotoStep(i + 1)"
          >
            <span class="step-no">{{ s.no }}.</span>{{ s.short }}
          </button>
          <el-button class="draft-btn" text type="primary" @click="onSaveDraft">
            <Save :size="14" style="margin-right: 4px" />暂存退出
          </el-button>
        </nav>

        <div class="gen-panel">
          <!-- 01 基础信息 -->
          <template v-if="wizard.step === 1">
            <div class="panel-head">
              <h2>确认你的个人信息</h2>
              <el-button size="small" type="primary" plain @click="importFromKnowledge">
                <Sparkles :size="14" style="margin-right: 4px" />从知识库导入
              </el-button>
            </div>
            <el-form label-width="90px" class="gen-form">
              <div class="form-grid">
                <el-form-item label="姓名"><el-input v-model="basic.name" /></el-form-item>
                <el-form-item label="性别"><el-input v-model="basic.gender" /></el-form-item>
                <el-form-item label="手机"><el-input v-model="basic.phone" /></el-form-item>
                <el-form-item label="邮箱"><el-input v-model="basic.email" /></el-form-item>
                <el-form-item label="所在地"><el-input v-model="basic.location" /></el-form-item>
                <el-form-item label="出生日期"><el-input v-model="basic.birthday" placeholder="2004-04-08" /></el-form-item>
              </div>
              <el-form-item label="教育经历">
                <div class="list-editor">
                  <el-input v-for="(_, i) in basic.education" :key="i" v-model="basic.education[i]" placeholder="如：北京大学 · 本科 · 软件工程 · 2022-2026" class="list-row" />
                  <el-button size="small" text type="primary" @click="basic.education.push('')">
                    <Plus :size="13" style="margin-right: 3px" />加一条
                  </el-button>
                </div>
              </el-form-item>
              <el-form-item label="技能标签">
                <div class="list-editor">
                  <el-tag v-for="(s, i) in basic.skills" :key="i" closable @close="basic.skills.splice(i, 1)" style="margin-right: 6px">{{ s }}</el-tag>
                  <el-input v-model="skillInput" size="small" placeholder="输入后回车" style="width: 140px" @keyup.enter="pushSkill" />
                </div>
              </el-form-item>
              <el-form-item label="证书/荣誉">
                <div class="list-editor">
                  <el-input v-for="(_, i) in basic.certifications" :key="i" v-model="basic.certifications[i]" class="list-row" />
                  <el-button size="small" text type="primary" @click="basic.certifications.push('')">
                    <Plus :size="13" style="margin-right: 3px" />加一条
                  </el-button>
                </div>
              </el-form-item>
            </el-form>
          </template>

          <!-- 02 画像与方向 -->
          <template v-else-if="wizard.step === 2">
            <div class="panel-head">
              <h2>你的个人画像与投递方向</h2>
              <el-button size="small" type="primary" :loading="dirLoading" @click="analyzeDirections">
                <Compass :size="14" style="margin-right: 4px" />分析方向
              </el-button>
            </div>
            <p class="hint">AI 根据你的画像分析适合的投递方向，选 1~3 个感兴趣的方向。</p>
            <div v-if="dirLoading" class="empty-block">正在分析你的画像…</div>
            <div v-else-if="directionError" class="empty-block">
              <p class="hint">{{ directionError }}</p>
              <el-button size="small" text type="primary" @click="goKnowledge">去完善画像</el-button>
            </div>
            <div v-else-if="directions.length" class="dir-grid">
              <div
                v-for="d in directions"
                :key="d.title"
                class="dir-card"
                :class="{ selected: wizard.directions.includes(d.title) }"
                @click="toggleDirection(d.title)"
              >
                <span class="dir-check">{{ wizard.directions.includes(d.title) ? '✓' : '' }}</span>
                <div class="dir-card-title">{{ d.title }}</div>
                <div class="dir-card-reason">{{ d.reason }}</div>
              </div>
            </div>
            <div v-else class="empty-block">点击「分析方向」，或先到个人知识库完善画像。</div>
          </template>

          <!-- 03 经历补充 -->
          <template v-else-if="wizard.step === 3">
            <div class="panel-head">
              <h2>补充你的实践经历</h2>
              <el-button size="small" text type="primary" @click="addExperience"><Plus :size="13" style="margin-right: 3px" />加经历</el-button>
            </div>
            <div v-for="(exp, i) in wizard.experiences" :key="i" class="exp-card">
              <div class="exp-card-head">
                <span class="exp-no">经历 {{ i + 1 }}</span>
                <el-select v-model="exp.exp_type" size="small" style="width: 90px">
                  <el-option v-for="t in ['项目', '实习', '竞赛', '课程', '校园']" :key="t" :label="t" :value="t" />
                </el-select>
                <span class="exp-spacer" />
                <el-button size="small" text @click="moveExp(i, -1)"><ArrowUp :size="13" /></el-button>
                <el-button size="small" text @click="moveExp(i, 1)"><ArrowDown :size="13" /></el-button>
                <el-button size="small" text type="danger" @click="wizard.experiences.splice(i, 1)"><Trash2 :size="13" /></el-button>
              </div>
              <el-form label-width="80px" class="gen-form">
                <div class="form-grid">
                  <el-form-item label="公司/项目"><el-input v-model="exp.company" /></el-form-item>
                  <el-form-item label="角色"><el-input v-model="exp.title" /></el-form-item>
                  <el-form-item label="时间"><el-input v-model="exp.duration" /></el-form-item>
                </div>
                <el-form-item label="职责"><el-input v-model="exp.duty" type="textarea" :rows="2" /></el-form-item>
                <el-form-item label="成果/收获"><el-input v-model="exp.achievement" type="textarea" :rows="2" /></el-form-item>
              </el-form>
            </div>
          </template>

          <!-- 04 STAR 结构化 -->
          <template v-else-if="wizard.step === 4">
            <div class="panel-head">
              <h2>STAR 结构化</h2>
              <el-button size="small" type="primary" :loading="starLoading" :disabled="!wizard.experiences.length" @click="runStar">
                <Wand2 :size="14" style="margin-right: 4px" />AI 结构化为 STAR
              </el-button>
            </div>
            <p class="hint">AI 按「情境 → 任务 → 行动 → 成果」为每条经历提炼，可编辑任何字段。</p>
            <div v-if="starLoading" class="empty-block">正在结构化 {{ wizard.experiences.length }} 段经历…</div>
            <div v-else-if="!wizard.experiences.length" class="empty-block">请先在第 3 步补充经历。</div>
            <div v-for="(exp, i) in wizard.experiences" :key="i" class="exp-card">
              <div class="exp-card-head"><span class="exp-no">{{ exp.company || exp.title || `经历 ${i + 1}` }}</span></div>
              <div class="gen-form">
                <el-form-item label="情境"><el-input v-model="exp.situation" type="textarea" :rows="2" /></el-form-item>
                <el-form-item label="任务"><el-input v-model="exp.task" type="textarea" :rows="2" /></el-form-item>
                <el-form-item label="行动"><el-input v-model="exp.action" type="textarea" :rows="2" /></el-form-item>
                <el-form-item label="成果"><el-input v-model="exp.result" type="textarea" :rows="2" /></el-form-item>
              </div>
            </div>
          </template>

          <!-- 05 软性信息 -->
          <template v-else-if="wizard.step === 5">
            <div class="panel-head">
              <h2>软性信息</h2>
              <el-button size="small" type="primary" :loading="softLoading" @click="generateSoft">
                <Sparkles :size="14" style="margin-right: 4px" />AI 生成
              </el-button>
            </div>
            <p class="hint">补充性格、职业愿景与自我评价，让简历更有温度。</p>
            <el-form label-width="92px" class="gen-form">
              <el-form-item label="性格特点"><el-input v-model="wizard.soft_info.personality" /></el-form-item>
              <el-form-item label="职业愿景"><el-input v-model="wizard.soft_info.vision" /></el-form-item>
              <el-form-item label="不感兴趣方向"><el-input v-model="wizard.soft_info.disinterested" /></el-form-item>
              <el-form-item label="自我评价"><el-input v-model="wizard.soft_info.self_eval" type="textarea" :rows="3" /></el-form-item>
            </el-form>
          </template>

          <!-- 06 证件照 -->
          <template v-else-if="wizard.step === 6">
            <div class="panel-head"><h2>证件照</h2></div>
            <p class="hint">上传一张清晰的证件照（支持 JPG/PNG/WEBP，建议 295×413，≤5MB），或使用占位图。</p>
            <div class="photo-box">
              <img v-if="photoPreview" :src="photoPreview" alt="证件照" class="photo-img" />
              <div v-else class="photo-placeholder">占位图</div>
              <div>
                <el-button type="primary" :loading="photoUploading" @click="fileInput?.click()">
                  <Upload :size="14" style="margin-right: 4px" />上传照片
                </el-button>
                <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onPhotoChange" />
              </div>
            </div>
          </template>

          <!-- 07 预览微调 -->
          <template v-else-if="wizard.step === 7">
            <div class="panel-head">
              <h2>预览与微调</h2>
              <el-button size="small" text type="primary" :disabled="moduleEditor.length === 0" @click="rebuildModules"><RefreshCw :size="13" style="margin-right: 3px" />按数据重建</el-button>
            </div>
            <p class="hint">这是简历的结构预览，可调整模块顺序、修改文案；生成时 AI 会统一润色。</p>
            <div v-for="(m, i) in moduleEditor" :key="m.key" class="module-card">
              <div class="module-head">
                <span class="module-no">{{ i + 1 }}</span>
                <input v-model="m.title" class="module-title-input" />
                <span class="exp-spacer" />
                <el-button size="small" text @click="moveModule(i, -1)"><ArrowUp :size="13" /></el-button>
                <el-button size="small" text @click="moveModule(i, 1)"><ArrowDown :size="13" /></el-button>
              </div>
              <el-input v-model="m.content" type="textarea" :rows="3" />
            </div>
          </template>

          <!-- 08 生成与导出 -->
          <template v-else>
            <div class="panel-head"><h2>生成你的简历</h2></div>
            <p class="hint">AI 会整合前面所有信息，润色文案并生成简历；一次生成后可直接在简历库使用。</p>

            <div class="summary-box">
              <div class="sum-row"><span>投递方向</span><b>{{ wizard.directions.join(' / ') || '未选择' }}</b></div>
              <div class="sum-row"><span>实践经历</span><b>{{ wizard.experiences.length }} 段</b></div>
              <div class="sum-row"><span>技能标签</span><b>{{ basic.skills.length }} 个</b></div>
              <div class="sum-row"><span>自我评价</span><b>{{ wizard.soft_info.self_eval ? '已填写' : '未填写' }}</b></div>
              <div class="sum-row"><span>证件照</span><b>{{ wizard.photo_id ? '已上传' : '占位图' }}</b></div>
            </div>

            <div class="page-pref">
              <div class="pp-card" :class="{ selected: wizard.page_preference === 'one_page' }" @click="wizard.page_preference = 'one_page'">
                <b class="pp-no">1</b>
                <div class="pp-title">1 页简历</div>
                <p class="pp-desc">应届生推荐。内容超出 1 页时自动收紧排版，仍超则精简。</p>
              </div>
              <div class="pp-card" :class="{ selected: wizard.page_preference === 'two_pages' }" @click="wizard.page_preference = 'two_pages'">
                <b class="pp-no">2</b>
                <div class="pp-title">可接受 2 页</div>
                <p class="pp-desc">内容较多时保留完整信息，不做压缩。</p>
              </div>
            </div>

            <div class="gen-actions">
              <el-button type="primary" size="large" :loading="generating" @click="onGenerate">
                生成简历（约 15-60 秒）
              </el-button>
              <el-button size="large" :loading="exporting === 'docx'" @click="onExport('docx')">
                导出当前内容(Word)
              </el-button>
            </div>
            <p v-if="exportError" class="err">{{ exportError }}</p>

            <el-alert v-if="genError" type="error" :title="genError" show-icon style="margin-top: 14px" />

            <div v-if="generated" class="result-box">
              <div class="result-head">
                <CircleCheck :size="18" class="ok" />
                <span class="result-title">简历已生成{{ generated.document ? '并已入库' : '' }}</span>
                <span v-if="generated.document" class="result-sub">共 {{ generated.content.sections.length }} 个模块</span>
              </div>
              <div class="result-preview">
                <div v-for="(s, i) in generated.content.sections" :key="i" class="res-sec">
                  <div class="res-sec-title">{{ s.title }}</div>
                  <pre class="res-sec-content">{{ s.content }}</pre>
                </div>
              </div>
              <div class="result-actions">
                <el-button :loading="exporting === 'docx'" @click="onExport('docx')">下载 Word</el-button>
                <el-button :loading="exporting === 'html'" @click="onExport('html')">下载 HTML</el-button>
                <el-button :loading="exporting === 'md'" @click="onExport('md')">下载 MD</el-button>
                <el-button @click="onPrintPdf">打印/另存 PDF</el-button>
                <span class="exp-spacer" />
                <el-button text type="primary" @click="router.push('/resume-library')">前往简历库 →</el-button>
              </div>
              <p v-if="exportError" class="err">{{ exportError }}</p>
            </div>
          </template>

          <!-- 底部导航 -->
          <div class="foot-nav">
            <el-button v-if="wizard.step > 1" @click="prevStep"><ChevronLeft :size="14" style="margin-right: 4px" />上一步</el-button>
            <span class="exp-spacer" />
            <el-button type="primary" :disabled="!canNext" @click="nextStep">下一步 <ChevronRight :size="14" style="margin-left: 4px" /></el-button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ChevronLeft, ChevronRight, Plus, Trash2, ArrowUp, ArrowDown, Save, Sparkles,
  Compass, Wand2, Upload, RefreshCw, CircleCheck, User, Briefcase, Heart,
  Image as ImageIcon, FileText,
} from 'lucide-vue-next'
import AppNav from '../components/AppNav.vue'
import {
  clearDraft, generateResume, getPhotoInfo, loadDraft, saveDraft, starStructuring, uploadPhotoFile,
  exportResume, downloadBlob, type ExportFormat,
} from '../api/resumeGeneration'
import { recommendDirections, generateSoftInfo } from '../api/profile'
import { listProfileItems } from '../api/profile'
import { useRouter } from 'vue-router'
import type { WizardExperience, WizardGeneratePayload } from '../types'

const router = useRouter()

type StepDef = { key: string; no: string; short: string; title: string; desc: string; icon: any }

const STEPS: StepDef[] = [
  { key: 'basic', no: '01', short: '基础信息', title: '认识自己', desc: '整理属于你的个人信息，可从个人知识库一键导入。', icon: User },
  { key: 'directions', no: '02', short: '画像与方向', title: '发现方向', desc: 'AI 根据你的画像，分析适合的投递方向，选 1~3 个。', icon: Compass },
  { key: 'experience', no: '03', short: '经历补充', title: '发现方向', desc: '填写实习、项目或校园经历，也可以让 AI 帮你包装。', icon: Briefcase },
  { key: 'star', no: '04', short: 'STAR 结构化', title: '让经历更清晰', desc: 'AI 按 STAR 法则提炼每段经历，突出亮点与成果。', icon: Wand2 },
  { key: 'soft', no: '05', short: '软性信息', title: '看见真实的自己', desc: '补充性格、职业愿景与自我评价，让简历更有温度。', icon: Heart },
  { key: 'photo', no: '06', short: '证件照', title: '留下你的样子', desc: '上传一张清晰的证件照，或使用占位图。', icon: ImageIcon },
  { key: 'preview', no: '07', short: '预览微调', title: '慢慢打磨', desc: '调整模块顺序、修改文案，生成时 AI 统一润色。', icon: FileText },
  { key: 'generate', no: '08', short: '生成与导出', title: '一份新的开始', desc: '选择篇幅，AI 整合润色并生成简历，之后可在简历库使用。', icon: Sparkles },
]

const wizard = reactive({
  step: 1,
  title: '我的新简历',
  basic_info: {} as Record<string, unknown>,
  directions: [] as string[],
  experiences: [] as WizardExperience[],
  soft_info: { personality: '', vision: '', disinterested: '', self_eval: '' },
  photo_id: null as number | null,
  module_order: [] as string[],
  page_preference: 'one_page' as 'one_page' | 'two_pages',
})

const basic = reactive({
  name: '', gender: '', phone: '', email: '', location: '', birthday: '',
  education: [] as string[],
  certifications: [] as string[],
  skills: [] as string[],
})
const skillInput = ref('')

const directions = ref<{ title: string; reason: string; detail: string }[]>([])
const dirLoading = ref(false)
const directionError = ref('')
const starLoading = ref(false)
const softLoading = ref(false)
const photoUploading = ref(false)
const photoPreview = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const moduleEditor = ref<{ key: string; title: string; content: string }[]>([])
const generating = ref(false)
const genError = ref('')
const generated = ref<{ content: { sections: { title: string; content: string }[]; raw_text: string }; document: any } | null>(null)

const currentStep = computed(() => STEPS[wizard.step - 1])
const canNext = computed(() => true)

function pushSkill() {
  const v = skillInput.value.trim()
  if (v && !basic.skills.includes(v)) basic.skills.push(v)
  skillInput.value = ''
}

function toggleDirection(title: string) {
  const idx = wizard.directions.indexOf(title)
  if (idx >= 0) wizard.directions.splice(idx, 1)
  else if (wizard.directions.length < 3) wizard.directions.push(title)
  else ElMessage.warning('最多选择 3 个方向')
}

function addExperience() {
  wizard.experiences.push({ exp_type: '项目', company: '', title: '', duration: '', duty: '', achievement: '', situation: '', task: '', action: '', result: '' })
  rebuildModules()
}
function moveExp(i: number, dir: number) {
  const j = i + dir
  if (j < 0 || j >= wizard.experiences.length) return
  const [x] = wizard.experiences.splice(i, 1)
  wizard.experiences.splice(j, 0, x)
}
function moveModule(i: number, dir: number) {
  const j = i + dir
  if (j < 0 || j >= moduleEditor.value.length) return
  const [x] = moduleEditor.value.splice(i, 1)
  moduleEditor.value.splice(j, 0, x)
}

async function importFromKnowledge() {
  try {
    const res = await listProfileItems()
    const items = res.data || []
    for (const it of items) {
      const content = it.content || ''
      if (it.category === 'basic_info') {
        if (it.title === '姓名') basic.name = content
        else if (it.title === '邮箱') basic.email = content
        else if (it.title === '电话') basic.phone = content
        else if (it.title === '所在地') basic.location = content
        else if (!basic.gender && it.title === '性别') basic.gender = content
        else if (it.title === '出生日期') basic.birthday = content
      } else if (it.category === 'education') {
        if ((it.title || '').includes('证书')) basic.certifications.push(it.title + (content ? `：${content}` : ''))
        else basic.education.push(it.title + (content ? `：${content}` : ''))
      } else if (it.category === 'award') {
        content.split('\n').filter(Boolean).forEach((line) => basic.certifications.push(line))
      } else if (it.category === 'skill') {
        basic.skills.push(content || it.title || '')
      } else if (it.category === 'soft' && it.title === '性格特点') {
        wizard.soft_info.personality = content
      } else if (it.category === 'soft' && it.title === '自我评价') {
        wizard.soft_info.self_eval = content
      }
    }
    ElMessage.success('已从知识库导入可匹配的信息')
  } catch {
    ElMessage.error('导入失败，请先到个人知识库完善画像')
  }
}

async function analyzeDirections() {
  dirLoading.value = true
  directionError.value = ''
  try {
    const res = await recommendDirections()
    directions.value = res.data || []
    wizard.directions = wizard.directions.filter((d) => directions.value.some((x) => x.title === d))
  } catch (e: any) {
    directionError.value = e?.response?.data?.detail || '方向分析失败，请重试'
  } finally {
    dirLoading.value = false
  }
}

async function runStar() {
  starLoading.value = true
  try {
    const res = await starStructuring(wizard.experiences)
    const items = res.data.items || []
    for (const exp of wizard.experiences) {
      const hit = items.find((it) => (it.title || '') === exp.title && (it.company || '') === exp.company)
      if (hit) {
        exp.situation = hit.situation || exp.situation
        exp.task = hit.task || exp.task
        exp.action = hit.action || exp.action
        exp.result = hit.result || exp.result
      }
    }
    ElMessage.success('STAR 结构化完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || 'STAR 结构化失败，请重试')
  } finally {
    starLoading.value = false
  }
}

async function generateSoft() {
  softLoading.value = true
  try {
    const res = await generateSoftInfo()
    const d = res.data
    wizard.soft_info.personality = d.personality || wizard.soft_info.personality
    wizard.soft_info.vision = d.vision || wizard.soft_info.vision
    wizard.soft_info.disinterested = d.disinterested || wizard.soft_info.disinterested
    wizard.soft_info.self_eval = d.self_eval || wizard.soft_info.self_eval
    ElMessage.success('已生成，可继续修改')
  } catch {
    ElMessage.error('生成失败，请重试')
  } finally {
    softLoading.value = false
  }
}

async function onPhotoChange(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  photoUploading.value = true
  try {
    const res = await uploadPhotoFile(file)
    wizard.photo_id = res.data.id
    photoPreview.value = `${res.data.url}?t=${Date.now()}`
    ElMessage.success('证件照已上传')
  } catch {
    ElMessage.error('上传失败（支持 JPG/PNG/WEBP，≤5MB）')
  } finally {
    photoUploading.value = false
    input.value = ''
  }
}

function rebuildModules() {
  const modules = assemblePreview()
  moduleEditor.value = modules.map((m, i) => ({ key: `${i}`, title: m.title, content: m.content }))
}

function assemblePreview() {
  const out: { title: string; content: string }[] = []
  const info: string[] = []
  for (const [k, label] of [['name', '姓名'], ['email', '邮箱'], ['phone', '电话'], ['location', '所在地']] as const) {
    const v = (wizard.basic_info[k] as string) || (basic as any)[k]
    if (v) info.push(`${label}：${v}`)
  }
  if (info.length) out.push({ title: '基本信息', content: info.join('\n') })
  if (wizard.directions.length) out.push({ title: '求职意向', content: wizard.directions.join('，') })
  if (basic.education.some(Boolean)) out.push({ title: '教育背景', content: basic.education.filter(Boolean).join('\n') })
  const work: string[] = [], projects: string[] = []
  for (const e of wizard.experiences) {
    const block = `### ${[e.company, e.title].filter(Boolean).join(' | ')}
${[['情境', e.situation], ['任务', e.task], ['行动', e.action], ['成果', e.result]].filter(([, v]) => v).map(([k, v]) => `- ${k}：${v}`).join('\n')}`
    if (['实习', '工作'].includes(e.exp_type)) work.push(block)
    else projects.push(block)
  }
  if (work.length) out.push({ title: '实习/工作经历', content: work.join('\n\n') })
  if (projects.length) out.push({ title: '项目经历', content: projects.join('\n\n') })
  if (basic.skills.length) out.push({ title: '技能', content: basic.skills.join(', ') })
  if (wizard.soft_info.self_eval) out.push({ title: '自我评价', content: wizard.soft_info.self_eval })
  if (basic.certifications.some(Boolean)) out.push({ title: '证书/荣誉', content: basic.certifications.filter(Boolean).join('\n') })
  return out
}

function gotoStep(step: number) {
  wizard.step = Math.min(8, Math.max(1, step))
  if (wizard.step === 7) rebuildModules()
}
function prevStep() { gotoStep(wizard.step - 1) }
function nextStep() {
  if (wizard.step === 6 && !wizard.photo_id) wizard.photo_id = 0 // 允许占位
  gotoStep(wizard.step + 1)
  void onSaveDraft()
}

function snapshot(): Record<string, unknown> {
  return {
    basic_info: { ...basic },
    directions: [...wizard.directions],
    experiences: wizard.experiences.map((e) => ({ ...e })),
    soft_info: { ...wizard.soft_info },
    photo_id: wizard.photo_id,
    module_order: moduleEditor.value.map((m) => m.title),
    page_preference: wizard.page_preference,
    title: wizard.title,
  }
}
function restore(data: Record<string, unknown>) {
  const d = data || {}
  const bi = (d.basic_info || {}) as any
  Object.assign(basic, bi)
  wizard.directions = (d.directions as string[]) || []
  wizard.experiences = (d.experiences as WizardExperience[]) || []
  Object.assign(wizard.soft_info, (d.soft_info as any) || {})
  wizard.photo_id = (d.photo_id as number) || null
  wizard.page_preference = (d.page_preference as 'one_page' | 'two_pages') || 'one_page'
  wizard.title = (d.title as string) || wizard.title
}

async function onSaveDraft() {
  try {
    const step = wizard.step
    await saveDraft(step, snapshot())
    ElMessage.success(`已暂存第 ${step} 步，下次可继续`)
  } catch {
    ElMessage.error('暂存失败')
  }
}

async function onGenerate() {
  generating.value = true
  genError.value = ''
  generated.value = null
  try {
    const payload: WizardGeneratePayload = {
      title: wizard.title,
      basic_info: {
        name: basic.name, email: basic.email, phone: basic.phone, location: basic.location,
        gender: basic.gender, birthday: basic.birthday,
        education: basic.education.filter(Boolean),
        certifications: basic.certifications.filter(Boolean),
        skills: basic.skills,
      },
      directions: wizard.directions,
      experiences: wizard.experiences,
      soft_info: { ...wizard.soft_info },
      photo_id: wizard.photo_id,
      module_order: moduleEditor.value.map((m) => m.title),
      page_preference: wizard.page_preference,
      polish: true,
      import_to_library: true,
    }
    const res = await generateResume(payload)
    generated.value = res.data
    await clearDraft()
    ElMessage.success('简历生成成功，已导入简历库')
  } catch (e: any) {
    genError.value = e?.response?.data?.detail || '生成失败，请重试'
  } finally {
    generating.value = false
  }
}

function goKnowledge() {
  router.push('/knowledge-base')
}

// ---- 导出 ----
const exporting = ref('')
const exportError = ref('')

function contentFromEditor(): { sections: { title: string; content: string }[]; raw_text: string } {
  const sections = moduleEditor.value.map((m) => ({ title: m.title || '模块', content: m.content || '' }))
  const raw_text = sections.map((s) => `## ${s.title}\n${s.content}`).join('\n\n')
  return { sections, raw_text }
}

function currentContent() {
  if (generated.value) return generated.value.content
  return contentFromEditor()
}

async function onExport(format: ExportFormat) {
  exporting.value = format
  exportError.value = ''
  try {
    const content = currentContent()
    const blob = await exportResume(content, wizard.title, format)
    downloadBlob(blob, `${wizard.title}.${format === 'md' ? 'md' : format}`)
    ElMessage.success(`已导出 ${format === 'docx' ? 'Word' : format.toUpperCase()}`)
  } catch {
    exportError.value = '导出失败，请重试'
  } finally {
    exporting.value = ''
  }
}

async function onPrintPdf() {
  exportError.value = ''
  try {
    const blob = await exportResume(currentContent(), wizard.title, 'html')
    const url = URL.createObjectURL(blob)
    const win = window.open(url, '_blank')
    if (win) {
      setTimeout(() => win.print(), 400)
    } else {
      downloadBlob(blob, `${wizard.title}.html`)
    }
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch {
    exportError.value = '导出失败，请重试'
  }
}

onMounted(async () => {
  try {
    const res = await loadDraft()
    if (res.data.step) {
      const cont = await ElMessageBox.confirm(
        `检测到上次暂存于第 ${res.data.step} 步，是否继续？`,
        '继续上次的简历生成',
        { confirmButtonText: '继续', cancelButtonText: '从头开始' },
      ).then(() => true).catch(() => false)
      if (cont) {
        wizard.step = res.data.step || 1
        restore(res.data.data)
        if (wizard.step === 7) rebuildModules()
      } else {
        await clearDraft()
      }
    }
  } catch { /* 静默 */ }
  try {
    const photo = await getPhotoInfo()
    if (photo.data) {
      wizard.photo_id = photo.data.id
      photoPreview.value = `${photo.data.url}?t=${Date.now()}`
    }
  } catch { /* 静默 */ }
})
</script>

<style scoped>
.gen-page { min-height: 100vh; display: flex; flex-direction: column; background: var(--color-bg-page); }
.gen-shell { flex: 1; display: grid; grid-template-columns: minmax(260px, 360px) 1fr; max-width: 1200px; width: 100%; margin: 0 auto; }

.gen-narrative {
  position: relative;
  padding: var(--space-10) var(--space-8);
  border-right: var(--border-light);
  display: flex; flex-direction: column; gap: var(--space-4);
}
.eyebrow { font-size: var(--text-sm); color: var(--color-accent-600); font-weight: var(--weight-semibold); letter-spacing: 0.08em; }
.narr-title { font-family: var(--font-display); font-size: var(--text-2xl); margin: 0; color: var(--color-text-primary); }
.narr-desc { color: var(--color-text-secondary); line-height: 1.7; margin: 0; }
.narr-mark {
  margin-top: auto; width: 64px; height: 64px; border-radius: 20px;
  display: grid; place-items: center; color: var(--color-accent-600);
  background: var(--color-accent-50); border: 1px solid var(--color-accent-200);
}

.gen-main { padding: var(--space-6) var(--space-8) var(--space-10); overflow-y: auto; }
.step-nav { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: var(--space-5); }
.step-chip {
  border: 1px solid var(--color-border); background: var(--color-bg);
  border-radius: var(--radius-full); padding: 6px 12px; font-size: var(--text-xs);
  color: var(--color-text-secondary); cursor: pointer; transition: all var(--duration-fast) var(--ease-default);
}
.step-chip .step-no { color: var(--color-text-tertiary); margin-right: 4px; }
.step-chip.active { background: var(--color-accent-600); border-color: var(--color-accent-600); color: #fff; }
.step-chip.active .step-no { color: rgba(255,255,255,.8); }
.step-chip.done { color: var(--color-accent-600); border-color: var(--color-accent-200); background: var(--color-accent-50); }
.draft-btn { margin-left: auto; }

.gen-panel {
  background: var(--color-bg); border: 1px solid var(--border-light);
  border-radius: var(--radius-xl); padding: var(--space-6); box-shadow: var(--shadow-card);
}
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-4); }
.panel-head h2 { font-family: var(--font-display); font-size: var(--text-lg); margin: 0; color: var(--color-text-primary); }
.hint { color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.6; margin: 0 0 var(--space-4); }
.gen-form { max-width: 680px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 var(--space-4); }
.list-editor { width: 100%; display: flex; flex-direction: column; gap: 6px; }
.list-row { width: 100%; }

.empty-block {
  padding: var(--space-8) 0; text-align: center; color: var(--color-text-secondary);
  border: 1px dashed var(--color-border); border-radius: var(--radius-xl);
}

.dir-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: var(--space-3); }
.dir-card {
  position: relative; border: 1px solid var(--color-border); border-radius: var(--radius-xl);
  padding: var(--space-4); cursor: pointer; transition: all var(--duration-fast) var(--ease-default);
}
.dir-card.selected { border-color: var(--color-accent-600); background: var(--color-accent-50); }
.dir-check { position: absolute; top: 10px; right: 12px; color: var(--color-accent-600); font-weight: 700; }
.dir-card-title { font-weight: var(--weight-semibold); color: var(--color-text-primary); }
.dir-card-reason { margin-top: 6px; font-size: var(--text-xs); color: var(--color-text-secondary); line-height: 1.5; }

.exp-card, .module-card {
  border: 1px solid var(--color-border); border-radius: var(--radius-xl);
  padding: var(--space-4); margin-bottom: var(--space-4); background: var(--color-bg-elevated);
}
.exp-card-head, .module-head { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); }
.exp-no { font-weight: var(--weight-semibold); color: var(--color-text-primary); }
.exp-spacer { flex: 1; }

.photo-box { display: flex; align-items: flex-start; gap: var(--space-6); }
.photo-img { width: 90px; height: 120px; object-fit: cover; border-radius: var(--radius-lg); border: 1px solid var(--color-border); }
.photo-placeholder {
  width: 90px; height: 120px; border-radius: var(--radius-lg); border: 1px dashed var(--color-border);
  display: grid; place-items: center; color: var(--color-text-tertiary); font-size: var(--text-xs);
}

.module-title-input {
  border: none; outline: none; background: transparent; font-weight: var(--weight-semibold);
  color: var(--color-text-primary); font-size: var(--text-base); min-width: 120px; flex: 1;
}
.module-no { display: grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; background: var(--color-accent-100); color: var(--color-accent-700); font-size: var(--text-xs); font-weight: 700; }

.summary-box { border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-4); margin-bottom: var(--space-5); }
.sum-row { display: flex; padding: 6px 0; }
.sum-row span { width: 96px; color: var(--color-text-tertiary); font-size: var(--text-sm); }
.sum-row b { color: var(--color-text-primary); font-weight: var(--weight-medium); }

.page-pref { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-5); }
.pp-card { position: relative; border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-5); cursor: pointer; }
.pp-card.selected { border-color: var(--color-accent-600); box-shadow: 0 0 0 1px var(--color-accent-600) inset; }
.pp-no { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; background: var(--color-accent-600); color: #fff; font-size: var(--text-sm); margin-bottom: 8px; }
.pp-title { font-weight: var(--weight-semibold); color: var(--color-text-primary); }
.pp-desc { margin: 6px 0 0; font-size: var(--text-xs); color: var(--color-text-secondary); line-height: 1.6; }

.gen-actions { display: flex; }

.result-box { margin-top: var(--space-5); border: 1px solid var(--color-success-600); background: var(--color-success-50); border-radius: var(--radius-xl); padding: var(--space-5); }
.result-head { display: flex; align-items: center; gap: 8px; margin-bottom: var(--space-4); }
.result-head .ok { color: var(--color-success-600); }
.result-title { font-weight: var(--weight-semibold); color: var(--color-text-primary); }
.result-sub { color: var(--color-text-tertiary); font-size: var(--text-xs); }
.result-preview { max-height: 320px; overflow-y: auto; }
.res-sec { padding: var(--space-3) 0; border-top: 1px dashed var(--color-border); }
.res-sec-title { font-weight: var(--weight-semibold); color: var(--color-accent-700); margin-bottom: 4px; }
.res-sec-content { margin: 0; white-space: pre-wrap; font-family: var(--font-sans); font-size: var(--text-sm); color: var(--color-text-secondary); line-height: 1.7; }
.result-actions { margin-top: var(--space-4); display: flex; gap: var(--space-2); }

.foot-nav { display: flex; align-items: center; margin-top: var(--space-6); }
</style>
