<template>
  <div class="gen-page">
    <AppNav />
    <div class="gen-shell">
      <aside class="gen-narrative">
        <p class="eyebrow">简历生成 · {{ currentStep.no }}</p>
        <h1 class="narr-title">{{ currentStep.title }}</h1>
        <p class="narr-desc">{{ currentStep.desc }}</p>
        <div class="narr-mark">
          <component :is="currentStep.icon" :size="28" />
        </div>
      </aside>

      <section class="gen-main">
        <nav class="step-nav">
          <button
            v-for="(s, i) in STEPS"
            :key="s.key"
            type="button"
            class="step-chip"
            :class="{ active: wizard.step === i + 1, done: wizard.step > i + 1 }"
            @click="gotoStep(i + 1)"
          >
            <span class="step-no">{{ s.no }}.</span>{{ s.short }}
          </button>
          <el-button class="draft-btn" size="small" text type="primary" @click="onSaveDraft">
            <Save :size="13" style="margin-right: 3px" />暂存
          </el-button>
          <el-button class="draft-btn" size="small" text @click="onExitToHome">
            返回主界面
          </el-button>
        </nav>

        <div class="gen-panel">
          <!-- 01 基本信息 + 投递方向 -->
          <template v-if="wizard.step === 1">
            <div class="panel-head">
              <h2>基本信息与投递方向</h2>
              <div class="head-actions">
                <el-button size="small" type="primary" plain @click="importFromKnowledge">
                  <Sparkles :size="14" style="margin-right: 4px" />从画像导入
                </el-button>
              </div>
            </div>
            <el-form label-width="90px" class="gen-form">
              <div class="form-grid">
                <el-form-item label="姓名"><el-input v-model="basic.name" /></el-form-item>
                <el-form-item label="性别"><el-input v-model="basic.gender" /></el-form-item>
                <el-form-item label="手机"><el-input v-model="basic.phone" /></el-form-item>
                <el-form-item label="邮箱"><el-input v-model="basic.email" /></el-form-item>
                <el-form-item label="所在地"><el-input v-model="basic.location" /></el-form-item>
                <el-form-item label="出生日期">
                  <el-date-picker v-model="basic.birthday" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
                </el-form-item>
              </div>
            </el-form>

            <div class="block-gap" />
            <div class="panel-head">
              <h2 class="sub-h">投递方向（1~3 个）</h2>
              <div class="head-actions">
                <el-button size="small" type="primary" :loading="dirLoading" @click="analyzeDirections">
                  <Compass :size="14" style="margin-right: 4px" />分析方向
                </el-button>
                <el-button
                  size="small"
                  :loading="dirSaving"
                  :disabled="!wizard.directions.length || dirLoading"
                  @click="saveDirectionsToProfile"
                >
                  <Save :size="14" style="margin-right: 4px" />保存到画像
                </el-button>
              </div>
            </div>
            <p class="hint">优先使用画像中已确认的目标岗位；也可 AI 重新分析。选 1~3 个用于本次简历。</p>
            <p v-if="dirsFromProfile.length" class="dir-profile-note">
              已从个人画像带入 {{ dirsFromProfile.length }} 个已确认方向，可在下方调整。
            </p>
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
            <div v-else class="empty-block">
              点击「分析方向」，或先到个人画像完善信息 / 用「AI 推荐投递方向」。
              <div style="margin-top: 12px">
                <el-button size="small" text type="primary" @click="goKnowledge">去个人画像</el-button>
              </div>
            </div>
          </template>

          <!-- 02 教育经历 -->
          <template v-else-if="wizard.step === 2">
            <div class="panel-head">
              <h2>教育经历</h2>
              <el-button size="small" text type="primary" @click="addEducation">
                <Plus :size="13" style="margin-right: 3px" />加一条
              </el-button>
            </div>
            <p class="hint">GPA、排名、主修课程均为可选；在读可把结束时间勾选为「至今」。</p>
            <div v-if="!wizard.educations.length" class="empty-block">还没有教育经历，点右上角添加。</div>
            <div v-for="(edu, i) in wizard.educations" :key="i" class="exp-card">
              <div class="exp-card-head">
                <span class="exp-no">教育 {{ i + 1 }}</span>
                <span class="exp-spacer" />
                <el-button size="small" text @click="moveItem(wizard.educations, i, -1)"><ArrowUp :size="13" /></el-button>
                <el-button size="small" text @click="moveItem(wizard.educations, i, 1)"><ArrowDown :size="13" /></el-button>
                <el-button size="small" text type="danger" @click="wizard.educations.splice(i, 1)"><Trash2 :size="13" /></el-button>
              </div>
              <el-form label-width="88px" class="gen-form">
                <div class="form-grid">
                  <el-form-item label="学校"><el-input v-model="edu.school" placeholder="如：北京大学" /></el-form-item>
                  <el-form-item label="层次">
                    <el-select v-model="edu.degree" placeholder="选择层次" style="width: 100%">
                      <el-option v-for="d in DEGREES" :key="d" :label="d" :value="d" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="专业"><el-input v-model="edu.major" placeholder="如：软件工程" /></el-form-item>
                  <el-form-item label="开始时间">
                    <el-date-picker v-model="edu.start" type="month" value-format="YYYY-MM" placeholder="如 2022-09" style="width: 100%" />
                  </el-form-item>
                  <el-form-item label="结束时间">
                    <div class="period-end">
                      <el-checkbox v-model="edu.current">至今</el-checkbox>
                      <el-date-picker v-model="edu.end" type="month" value-format="YYYY-MM" placeholder="如 2026-06" :disabled="edu.current" style="flex: 1" />
                    </div>
                  </el-form-item>
                  <el-form-item label="GPA（可选）"><el-input v-model="edu.gpa" placeholder="如 3.8/4.0" /></el-form-item>
                  <el-form-item label="排名（可选）"><el-input v-model="edu.rank" placeholder="如 5/60" /></el-form-item>
                </div>
                <el-form-item label="主修课程"><el-input v-model="edu.courses" type="textarea" :rows="2" placeholder="可选，如：数据结构、计算机网络" /></el-form-item>
              </el-form>
            </div>
          </template>

          <!-- 03 专业技能 -->
          <template v-else-if="wizard.step === 3">
            <div class="panel-head">
              <h2>专业技能</h2>
              <el-button size="small" text type="primary" @click="addSkill">
                <Plus :size="13" style="margin-right: 3px" />加技能
              </el-button>
            </div>
            <p class="hint">按掌握程度填写更可信；熟练度可选。证书/荣誉可写在下方可选区。</p>
            <div v-if="!wizard.skills.length" class="empty-block">还没有技能标签。</div>
            <div v-for="(sk, i) in wizard.skills" :key="i" class="skill-row">
              <el-input v-model="sk.name" placeholder="技能名称，如 Python" style="flex: 1" />
              <el-select v-model="sk.level" placeholder="熟练度（可选）" clearable style="width: 140px">
                <el-option v-for="lv in SKILL_LEVELS" :key="lv" :label="lv" :value="lv" />
              </el-select>
              <el-button size="small" text type="danger" @click="wizard.skills.splice(i, 1)"><Trash2 :size="13" /></el-button>
            </div>
            <div class="quick-skill">
              <el-input
                v-model="skillInput"
                size="small"
                placeholder="输入技能后回车快速添加"
                style="width: 220px"
                @keyup.enter="pushSkill"
              />
            </div>

            <div class="block-gap" />
            <details class="cert-block">
              <summary>证书 / 荣誉（可选）</summary>
              <div class="list-editor" style="margin-top: 12px">
                <el-input
                  v-for="(_, i) in basic.certifications"
                  :key="i"
                  v-model="basic.certifications[i]"
                  class="list-row"
                  placeholder="如 CET-6 / 国家奖学金"
                />
                <el-button size="small" text type="primary" @click="basic.certifications.push('')">
                  <Plus :size="13" style="margin-right: 3px" />加一条
                </el-button>
              </div>
            </details>
          </template>

          <!-- 04 实习经历 -->
          <template v-else-if="wizard.step === 4">
            <div class="panel-head">
              <h2>实习经历</h2>
              <el-button size="small" text type="primary" @click="addInternship">
                <Plus :size="13" style="margin-right: 3px" />加实习
              </el-button>
            </div>
            <p class="hint">实习是简历大头之一：写清公司/岗位、时间段、具体工作与可量化成果。STAR 为可选增强。</p>
            <ExperienceAiRow
              :import-open="importOpen"
              :importing="importingExp"
              :nl-open="nlOpen"
              :generating="genExpLoading"
              :target="'internship'"
              @import="openImportFromProfile"
              @nl="openNlMode"
              @generate="onAiGenerateExp"
            />
            <ExperienceImportPanel
              v-if="importOpen"
              :loading="importLoading"
              :items="profileExperiences"
              @apply="applyProfileExperiences"
              @close="importOpen = false"
              @go-knowledge="goKnowledge"
            />
            <ExperienceNlPanel
              v-if="nlOpen"
              v-model="nlText"
              :loading="structureLoading"
              :error="expAiError"
              :target-label="aiTargetLabel"
              @submit="onStructureExp"
              @cancel="cancelNl"
            />
            <div v-if="!wizard.internships.length" class="empty-block">
              还没有实习经历。可「从画像导入」/ AI 包装，或手动添加。
            </div>
            <ExperienceFormCard
              v-for="(_, i) in wizard.internships"
              :key="i"
              v-model="wizard.internships[i]"
              :index="i"
              label="实习"
              name-label="公司"
              title-label="岗位"
              name-placeholder="如：字节跳动"
              title-placeholder="如：后端实习生"
              duty-label="工作内容"
              duty-placeholder="做了什么、用了什么方法/技术"
              :show-tech="false"
              :star-open="!!expandedStar[`i${i}`]"
              @remove="wizard.internships.splice(i, 1)"
              @move="(d) => moveItem(wizard.internships, i, d)"
              @toggle-star="toggleStar(`i${i}`)"
            />
            <div v-if="wizard.internships.length" class="star-batch">
              <el-button size="small" type="primary" plain :loading="starLoading" @click="runStar('internship')">
                <Wand2 :size="14" style="margin-right: 4px" />
                {{ starLoading ? '正在 STAR 结构化…' : 'AI 一键 STAR（可选）' }}
              </el-button>
              <span class="star-batch-hint">按「情境→任务→行动→成果」批量提炼；跳过也可直接下一步。</span>
            </div>
          </template>

          <!-- 05 项目经历 -->
          <template v-else-if="wizard.step === 5">
            <div class="panel-head">
              <h2>项目经历</h2>
              <el-button size="small" text type="primary" @click="addProject">
                <Plus :size="13" style="margin-right: 3px" />加项目
              </el-button>
            </div>
            <p class="hint">项目同样占简历大头：项目名、角色、技术栈、你负责的部分与成果。可选 STAR。</p>
            <ExperienceAiRow
              :import-open="importOpen"
              :importing="importingExp"
              :nl-open="nlOpen"
              :generating="genExpLoading"
              :target="'project'"
              @import="openImportFromProfile"
              @nl="openNlMode"
              @generate="onAiGenerateExp"
            />
            <ExperienceImportPanel
              v-if="importOpen"
              :loading="importLoading"
              :items="profileExperiences"
              @apply="applyProfileExperiences"
              @close="importOpen = false"
              @go-knowledge="goKnowledge"
            />
            <ExperienceNlPanel
              v-if="nlOpen"
              v-model="nlText"
              :loading="structureLoading"
              :error="expAiError"
              :target-label="aiTargetLabel"
              @submit="onStructureExp"
              @cancel="cancelNl"
            />
            <div v-if="!wizard.projects.length" class="empty-block">
              还没有项目经历。可「从画像导入」/ AI 包装，或手动添加。
            </div>
            <ExperienceFormCard
              v-for="(_, i) in wizard.projects"
              :key="i"
              v-model="wizard.projects[i]"
              :index="i"
              label="项目"
              name-label="项目名"
              title-label="角色"
              name-placeholder="如：校园二手交易平台"
              title-placeholder="如：后端负责人"
              duty-label="我的工作"
              duty-placeholder="负责模块、技术方案、关键实现"
              :show-tech="true"
              :star-open="!!expandedStar[`p${i}`]"
              @remove="wizard.projects.splice(i, 1)"
              @move="(d) => moveItem(wizard.projects, i, d)"
              @toggle-star="toggleStar(`p${i}`)"
            />
            <div v-if="wizard.projects.length" class="star-batch">
              <el-button size="small" type="primary" plain :loading="starLoading" @click="runStar('project')">
                <Wand2 :size="14" style="margin-right: 4px" />
                {{ starLoading ? '正在 STAR 结构化…' : 'AI 一键 STAR（可选）' }}
              </el-button>
              <span class="star-batch-hint">按「情境→任务→行动→成果」批量提炼；跳过也可直接下一步。</span>
            </div>
          </template>

          <!-- 06 自我评价 -->
          <template v-else-if="wizard.step === 6">
            <div class="panel-head">
              <h2>自我评价</h2>
              <div class="head-actions">
                <el-button size="small" type="primary" :loading="softLoading" @click="generateSoft">
                  <Sparkles :size="14" style="margin-right: 4px" />AI 生成
                </el-button>
                <el-button
                  size="small"
                  :loading="softSaving"
                  :disabled="!hasSoftInfo || softLoading"
                  @click="saveSoftToProfile"
                >
                  <Save :size="14" style="margin-right: 4px" />保存到画像
                </el-button>
              </div>
            </div>
            <p class="hint">性格、愿景会并入简历「自我评价」；不感兴趣方向仅用于画像，不会写进简历正文。</p>
            <el-form label-width="100px" class="gen-form">
              <el-form-item label="性格特点"><el-input v-model="wizard.soft_info.personality" /></el-form-item>
              <el-form-item label="职业愿景"><el-input v-model="wizard.soft_info.vision" /></el-form-item>
              <el-form-item label="不感兴趣方向"><el-input v-model="wizard.soft_info.disinterested" placeholder="仅沉淀画像，不进简历" /></el-form-item>
              <el-form-item label="自我评价"><el-input v-model="wizard.soft_info.self_eval" type="textarea" :rows="5" placeholder="一段话概括你的优势与做事风格" /></el-form-item>
            </el-form>
            <p class="soft-save-note" :class="{ 'is-saved': softSaved }">
              <template v-if="softSaved">
                已沉淀到个人画像，后续简历与模拟面试会自动复用；可在「个人画像 → 软性信息」修改。
              </template>
              <template v-else>
                这里的内容仅用于本次简历；点「保存到画像」可沉淀为长期画像，下次自动带入。
              </template>
            </p>
          </template>

          <!-- 07 证件照 -->
          <template v-else-if="wizard.step === 7">
            <div class="panel-head"><h2>证件照</h2></div>
            <p class="hint">上传一张清晰的证件照（支持 JPG/PNG/WEBP，建议 295×413，≤5MB）。未上传时导出不含照片。</p>
            <div class="photo-box">
              <img v-if="photoPreview" :src="photoPreview" alt="证件照" class="photo-img" />
              <div v-else class="photo-placeholder">暂无照片</div>
              <div>
                <el-button type="primary" :loading="photoUploading" @click="fileInput?.click()">
                  <Upload :size="14" style="margin-right: 4px" />{{ photoPreview ? '重新上传' : '上传照片' }}
                </el-button>
                <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onPhotoChange" />
                <p v-if="wizard.photo_id" class="hint" style="margin-top: 8px">
                  已上传证件照，Word / HTML 导出将自动嵌入。
                </p>
              </div>
            </div>
          </template>

          <!-- 08 生成与导出（含预览微调） -->
          <template v-else>
            <div class="panel-head">
              <h2>预览、生成与导出</h2>
              <el-button size="small" text type="primary" :disabled="moduleEditor.length === 0" @click="rebuildModules">
                <RefreshCw :size="13" style="margin-right: 3px" />按数据重建
              </el-button>
            </div>
            <p class="hint">下方为结构预览，可调顺序、改文案；生成时 AI 会统一润色。</p>

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

            <div class="block-gap" />
            <el-form label-width="88px" class="gen-form" style="margin-bottom: 14px">
              <el-form-item label="简历标题">
                <el-input v-model="wizard.title" :placeholder="defaultTitlePlaceholder" />
              </el-form-item>
            </el-form>

            <div class="summary-box">
              <div class="sum-row"><span>投递方向</span><b>{{ wizard.directions.join(' / ') || '未选择' }}</b></div>
              <div class="sum-row"><span>教育经历</span><b>{{ wizard.educations.length }} 段</b></div>
              <div class="sum-row"><span>实习 / 项目</span><b>{{ wizard.internships.length }} / {{ wizard.projects.length }} 段</b></div>
              <div class="sum-row"><span>技能</span><b>{{ wizard.skills.length }} 项</b></div>
              <div class="sum-row"><span>自我评价</span><b>{{ softMerged ? '已填写' : '未填写' }}</b></div>
              <div class="sum-row"><span>证件照</span><b>{{ wizard.photo_id ? '已上传' : '未上传（导出无照片）' }}</b></div>
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

            <div class="tpl-block">
              <div class="tpl-label">版式模板</div>
              <div class="tpl-grid">
                <button
                  v-for="t in templateOptions"
                  :key="t.key"
                  type="button"
                  class="tpl-card"
                  :class="{ selected: wizard.template === t.key }"
                  @click="wizard.template = t.key"
                >
                  <div class="tpl-title">{{ t.label }}</div>
                  <p class="tpl-desc">{{ t.desc }}</p>
                </button>
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

          <div class="foot-nav">
            <el-button v-if="wizard.step > 1" @click="prevStep"><ChevronLeft :size="14" style="margin-right: 4px" />上一步</el-button>
            <span class="exp-spacer" />
            <el-button v-if="wizard.step < STEPS.length" type="primary" :disabled="!canNext" @click="nextStep">
              下一步 <ChevronRight :size="14" style="margin-left: 4px" />
            </el-button>
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
  Compass, Wand2, Upload, RefreshCw, CircleCheck, User, GraduationCap, Wrench,
  Briefcase, FolderKanban, Heart, Image as ImageIcon, FileText,
} from 'lucide-vue-next'
import AppNav from '../components/AppNav.vue'
import ExperienceFormCard from '../components/wizard/ExperienceFormCard.vue'
import ExperienceAiRow from '../components/wizard/ExperienceAiRow.vue'
import ExperienceImportPanel from '../components/wizard/ExperienceImportPanel.vue'
import ExperienceNlPanel from '../components/wizard/ExperienceNlPanel.vue'
import {
  clearDraft, generateResume, getPhotoInfo, loadDraft, saveDraft, starStructuring, uploadPhotoFile,
  exportResume, downloadBlob, structureExperiences, generateExperiences, fetchPhotoBlob, type ExportFormat,
} from '../api/resumeGeneration'
import { recommendDirections, generateSoftInfo, saveSoftInfo, confirmDirections, listProfileItems } from '../api/profile'
import type { DirectionCandidate, WizardEducation, WizardExpEntry, WizardExperience, WizardGeneratePayload, WizardSkill } from '../types'
import { useRouter } from 'vue-router'

const router = useRouter()

type StepDef = { key: string; no: string; short: string; title: string; desc: string; icon: any }

const STEPS: StepDef[] = [
  { key: 'basic', no: '01', short: '基本信息', title: '认识自己', desc: '填写联系方式，并选择 1~3 个投递方向；可从个人画像一键导入。', icon: User },
  { key: 'education', no: '02', short: '教育经历', title: '你的求学轨迹', desc: '学校、层次、专业与起止时间；GPA/排名/课程可选。', icon: GraduationCap },
  { key: 'skills', no: '03', short: '专业技能', title: '你会什么', desc: '技能与熟练度；证书荣誉写在可选区。', icon: Wrench },
  { key: 'internship', no: '04', short: '实习经历', title: '职场初体验', desc: '实习是简历大头：公司、岗位、工作内容与量化成果。', icon: Briefcase },
  { key: 'project', no: '05', short: '项目经历', title: '讲好你的项目', desc: '项目名、角色、技术栈、你的贡献与成果。', icon: FolderKanban },
  { key: 'soft', no: '06', short: '自我评价', title: '看见真实的自己', desc: '性格、愿景与自我评价，并入简历正文；不感兴趣方向仅存画像。', icon: Heart },
  { key: 'photo', no: '07', short: '证件照', title: '留下你的样子', desc: '上传一张清晰的证件照，或使用占位图。', icon: ImageIcon },
  { key: 'generate', no: '08', short: '生成与导出', title: '一份新的开始', desc: '预览微调后选择篇幅与模板，AI 整合润色并生成简历。', icon: FileText },
]

const DEGREES = ['专科', '本科', '硕士', '博士', '其他']
const SKILL_LEVELS = ['了解', '熟悉', '掌握', '精通']

const wizard = reactive({
  step: 1,
  title: '我的新简历',
  directions: [] as string[],
  educations: [] as WizardEducation[],
  skills: [] as WizardSkill[],
  internships: [] as WizardExpEntry[],
  projects: [] as WizardExpEntry[],
  soft_info: { personality: '', vision: '', disinterested: '', self_eval: '' },
  photo_id: null as number | null,
  page_preference: 'one_page' as 'one_page' | 'two_pages',
  template: 'campus_one_page',
})

const templateOptions = [
  { key: 'campus_one_page', label: '校招一页纸', desc: '应届首选：头信息+教育+项目+技能+短自评' },
  { key: 'tech', label: '技术岗', desc: '项目与技能前置，条目更细，适合开发/算法' },
  { key: 'general', label: '通用版', desc: '教育与经历均衡，适合多种岗位' },
]

const basic = reactive({
  name: '',
  gender: '',
  phone: '',
  email: '',
  location: '',
  birthday: '',
  certifications: [] as string[],
})

const skillInput = ref('')
const directions = ref<DirectionCandidate[]>([])
const dirLoading = ref(false)
const dirSaving = ref(false)
const directionError = ref('')
const dirsFromProfile = ref<string[]>([])
const starLoading = ref(false)
const softLoading = ref(false)
const softSaving = ref(false)
const softSaved = ref(false)

const photoUploading = ref(false)
const photoPreview = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const moduleEditor = ref<{ key: string; title: string; content: string }[]>([])
const generating = ref(false)
const genError = ref('')
const generated = ref<{ content: { sections: { title: string; content: string }[]; raw_text: string }; document: any } | null>(null)

// AI 经历
type AiTarget = 'internship' | 'project'
const aiTarget = ref<AiTarget>('project')
const nlOpen = ref(false)
const nlText = ref('')
const structureLoading = ref(false)
const genExpLoading = ref(false)
const expAiError = ref('')
const importOpen = ref(false)
const importLoading = ref(false)
const importingExp = ref(false)
const profileExperiences = ref<{ id: number; title: string; content: string; checked: boolean }[]>([])
const expandedStar = reactive<Record<string, boolean>>({})

const aiTargetLabel = computed(() => (aiTarget.value === 'internship' ? '实习' : '项目'))

const defaultTitlePlaceholder = computed(() => defaultTitle())
const softMerged = computed(() =>
  !!(wizard.soft_info.self_eval || wizard.soft_info.personality || wizard.soft_info.vision),
)
const hasSoftInfo = softMerged
const currentStep = computed(() => STEPS[wizard.step - 1])
const canNext = computed(() => true)

function emptyEducation(): WizardEducation {
  return { school: '', degree: '', major: '', start: '', end: '', current: false, gpa: '', rank: '', courses: '' }
}
function emptyExp(): WizardExpEntry {
  return {
    company: '', title: '', start: '', end: '', current: false, duration: '',
    tech_stack: '', duty: '', achievement: '', situation: '', task: '', action: '', result: '',
  }
}

function formatPeriod(e: Pick<WizardExpEntry, 'start' | 'end' | 'current'>): string {
  const s = (e.start || '').replace(/-/g, '.')
  const end = e.current ? '至今' : (e.end || '').replace(/-/g, '.')
  if (s && end) return `${s}–${end}`
  return s || end
}

function moveItem<T>(arr: T[], i: number, dir: number) {
  const j = i + dir
  if (j < 0 || j >= arr.length) return
  const [x] = arr.splice(i, 1)
  arr.splice(j, 0, x)
}

function toggleStar(key: string) {
  expandedStar[key] = !expandedStar[key]
}

function pushSkill() {
  const v = skillInput.value.trim()
  if (v && !wizard.skills.some((s) => s.name === v)) wizard.skills.push({ name: v, level: '' })
  skillInput.value = ''
}

function addEducation() {
  wizard.educations.push(emptyEducation())
}
function addSkill() {
  wizard.skills.push({ name: '', level: '' })
}
function addInternship() {
  wizard.internships.push(emptyExp())
}
function addProject() {
  wizard.projects.push(emptyExp())
}

function toggleDirection(title: string) {
  const idx = wizard.directions.indexOf(title)
  if (idx >= 0) wizard.directions.splice(idx, 1)
  else if (wizard.directions.length < 3) wizard.directions.push(title)
}

// ---- 经历 AI ----

function expToDraft(e: WizardExpEntry, exp_type: string): WizardExperience {
  return {
    exp_type,
    company: e.company,
    title: e.title,
    duration: e.duration || formatPeriod(e),
    duty: e.duty,
    achievement: e.achievement,
    situation: e.situation,
    task: e.task,
    action: e.action,
    result: e.result,
  }
}

function draftToEntry(d: WizardExperience & Record<string, any>): WizardExpEntry {
  const e = emptyExp()
  e.company = d.company || ''
  e.title = d.title || ''
  e.duration = d.duration || ''
  e.tech_stack = d.tech_stack || ''
  e.duty = d.duty || ''
  e.achievement = d.achievement || ''
  e.situation = d.situation || ''
  e.task = d.task || ''
  e.action = d.action || ''
  e.result = d.result || ''
  e.start = d.start || ''
  e.end = d.end || ''
  e.current = !!d.current
  return e
}

function isInternType(t: string) {
  return ['实习', '工作', '职场'].includes(t || '')
}

function openNlMode(target: AiTarget) {
  aiTarget.value = target
  importOpen.value = false
  nlOpen.value = !nlOpen.value
  expAiError.value = ''
}

function cancelNl() {
  nlOpen.value = false
  nlText.value = ''
  expAiError.value = ''
}

async function openImportFromProfile() {
  aiTarget.value = wizard.step === 4 ? 'internship' : 'project'
  nlOpen.value = false
  importOpen.value = !importOpen.value
  if (!importOpen.value) return
  importLoading.value = true
  try {
    const res = await listProfileItems('experience')
    const items = res.data || []
    profileExperiences.value = (Array.isArray(items) ? items : [])
      .map((it: any) => ({
        id: it.id,
        title: it.title || '',
        content: it.content || '',
        checked: false,
      }))
      .filter((it: any) => it.content || it.title)
  } catch {
    profileExperiences.value = []
  } finally {
    importLoading.value = false
  }
}

function applyProfileExperiences() {
  const chosen = profileExperiences.value.filter((p) => p.checked)
  if (!chosen.length) {
    ElMessage.warning('请先勾选要导入的经历')
    return
  }
  for (const pe of chosen) {
    const entry = emptyExp()
    entry.company = pe.title || ''
    entry.duty = pe.content || ''
    if (aiTarget.value === 'internship') wizard.internships.push(entry)
    else wizard.projects.push(entry)
  }
  importOpen.value = false
  ElMessage.success(`已导入 ${chosen.length} 条到${aiTargetLabel.value}经历`)
}

async function onStructureExp() {
  const text = nlText.value.trim()
  if (!text) {
    expAiError.value = '请先粗略描述你的经历'
    return
  }
  structureLoading.value = true
  expAiError.value = ''
  try {
    const res = await structureExperiences(text, wizard.directions)
    const typed = (res.data?.items || []) as (WizardExperience & Record<string, any>)[]
    const entries = typed.map(draftToEntry)
    const toIntern: WizardExpEntry[] = []
    const toProject: WizardExpEntry[] = []
    typed.forEach((d, idx) => {
      if (isInternType(d.exp_type)) toIntern.push(entries[idx])
      else toProject.push(entries[idx])
    })
    if (aiTarget.value === 'internship') {
      wizard.internships.push(...toIntern, ...toProject)
    } else {
      wizard.projects.push(...toProject, ...toIntern)
    }
    cancelNl()
    ElMessage.success(`已结构化 ${entries.length} 条${aiTargetLabel.value}经历`)
  } catch (e: any) {
    expAiError.value = e?.response?.data?.detail || '结构化失败，请重试'
  } finally {
    structureLoading.value = false
  }
}

async function onAiGenerateExp() {
  aiTarget.value = wizard.step === 4 ? 'internship' : 'project'
  genExpLoading.value = true
  expAiError.value = ''
  try {
    const res = await generateExperiences(wizard.directions, 2)
    const typed = (res.data?.items || []) as WizardExperience[]
    const entries = typed.map(draftToEntry)
    const targetList = aiTarget.value === 'internship' ? wizard.internships : wizard.projects
    if (targetList.length) {
      const replace = await ElMessageBox.confirm(
        `已生成 ${entries.length} 条草稿，要替换现有 ${targetList.length} 条吗？`,
        'AI 生成经历',
        { confirmButtonText: '替换', cancelButtonText: '追加' },
      ).then(() => true).catch(() => false)
      if (replace) targetList.splice(0, targetList.length, ...entries)
      else targetList.push(...entries)
    } else {
      targetList.push(...entries)
    }
    ElMessage.success(`已生成 ${entries.length} 条草稿`)
  } catch (e: any) {
    expAiError.value = e?.response?.data?.detail || '生成失败，请重试'
  } finally {
    genExpLoading.value = false
  }
}

async function runStar(target: AiTarget) {
  const list = target === 'internship' ? wizard.internships : wizard.projects
  if (!list.length) return
  starLoading.value = true
  try {
    const payloads = list.map((e) => expToDraft(e, target === 'internship' ? '实习' : '项目'))
    const res = await starStructuring(payloads)
    const items = res.data?.items || []
    items.forEach((star: WizardExperience, i: number) => {
      if (!list[i]) return
      list[i].situation = star.situation || list[i].situation
      list[i].task = star.task || list[i].task
      list[i].action = star.action || list[i].action
      list[i].result = star.result || list[i].result
      if (!list[i].duration && star.duration) list[i].duration = star.duration
      const key = `${target === 'internship' ? 'i' : 'p'}${i}`
      expandedStar[key] = true
    })
    ElMessage.success('STAR 结构化完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || 'STAR 结构化失败')
  } finally {
    starLoading.value = false
  }
}

// ---- 方向 / 画像 ----

async function analyzeDirections() {
  dirLoading.value = true
  directionError.value = ''
  try {
    const res = await recommendDirections()
    directions.value = Array.isArray(res.data) ? res.data : []
    if (!directions.value.length) directionError.value = '画像信息不足，暂时无法分析方向。'
  } catch {
    directionError.value = '分析失败，请确认后端已启动，或先完善个人画像。'
  } finally {
    dirLoading.value = false
  }
}

async function saveDirectionsToProfile() {
  if (!wizard.directions.length || dirSaving.value) return
  dirSaving.value = true
  try {
    const chosen = wizard.directions.map((title) => {
      const found = directions.value.find((d) => d.title === title)
      return { title, reason: found?.reason || '', detail: found?.detail || '' }
    })
    await confirmDirections(chosen)
    dirsFromProfile.value = Array.from(new Set([...dirsFromProfile.value, ...wizard.directions]))
    ElMessage.success('已保存到个人画像')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    dirSaving.value = false
  }
}

async function loadProfileDirections() {
  try {
    const res = await listProfileItems('target', 'confirmed')
    const items = res.data || []
    const titles = (Array.isArray(items) ? items : [])
      .map((it: any) => (it.title || '').trim())
      .filter(Boolean)
    dirsFromProfile.value = titles
    if (!wizard.directions.length && titles.length) {
      wizard.directions = titles.slice(0, 3)
    }
    if (!directions.value.length && titles.length) {
      directions.value = titles.map((t: string) => ({ title: t, reason: '来自个人画像已确认目标岗位', detail: '' }))
    }
  } catch { /* 静默 */ }
}

function goKnowledge() {
  router.push('/knowledge-base')
}

async function importFromKnowledge() {
  try {
    const [basicRes, eduRes, skillRes] = await Promise.all([
      listProfileItems('basic_info'),
      listProfileItems('education'),
      listProfileItems('skill'),
    ])
    const basicItems = (basicRes.data || []) as any[]
    const map: Record<string, string> = {
      姓名: 'name', 性别: 'gender', 手机号: 'phone', 邮箱: 'email',
      所在地: 'location', 出生日期: 'birthday',
    }
    for (const it of basicItems) {
      const key = map[it.title]
      if (key && it.content) (basic as any)[key] = it.content
    }
    const eduItems = (eduRes.data || []) as any[]
    if (eduItems.length && !wizard.educations.length) {
      wizard.educations = eduItems.map((it) => {
        const e = emptyEducation()
        e.school = it.title || ''
        const c = String(it.content || '')
        const parts = c.split('·').map((x) => x.trim())
        if (parts[0]) e.school = e.school || parts[0]
        if (parts[1]) e.degree = parts[1]
        if (parts[2]) e.major = parts[2]
        return e
      })
    }
    const skillItems = (skillRes.data || []) as any[]
    if (skillItems.length && !wizard.skills.length) {
      wizard.skills = skillItems.map((it) => ({ name: it.title || it.content || '', level: '' })).filter((s) => s.name)
    }
    ElMessage.success('已从画像导入可匹配的信息')
    await loadProfileDirections()
  } catch {
    ElMessage.error('从画像导入失败')
  }
}

// ---- 软性信息 ----

async function generateSoft() {
  softLoading.value = true
  try {
    const res = await generateSoftInfo()
    const d = res.data || {}
    wizard.soft_info.personality = d.personality || wizard.soft_info.personality
    wizard.soft_info.vision = d.vision || wizard.soft_info.vision
    wizard.soft_info.disinterested = d.disinterested || wizard.soft_info.disinterested
    wizard.soft_info.self_eval = d.self_eval || wizard.soft_info.self_eval
    ElMessage.success('已生成自我评价建议，可再修改')
  } catch {
    ElMessage.error('AI 生成失败，请稍后重试')
  } finally {
    softLoading.value = false
  }
}

async function saveSoftToProfile() {
  softSaving.value = true
  try {
    await saveSoftInfo({
      personality: wizard.soft_info.personality.trim(),
      vision: wizard.soft_info.vision.trim(),
      disinterested: wizard.soft_info.disinterested.trim(),
      self_eval: wizard.soft_info.self_eval.trim(),
    })
    softSaved.value = true
    ElMessage.success('已保存到个人画像')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    softSaving.value = false
  }
}

// ---- 证件照 ----

async function onPhotoChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('照片不能超过 5MB')
    input.value = ''
    return
  }
  photoUploading.value = true
  try {
    const res = await uploadPhotoFile(file)
    wizard.photo_id = res.data.id
    await refreshPhotoPreview(res.data.id)
    ElMessage.success('证件照已上传')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '上传失败')
  } finally {
    photoUploading.value = false
    input.value = ''
  }
}

async function refreshPhotoPreview(photoId: number) {
  try {
    const blob = await fetchPhotoBlob(photoId)
    if (photoPreview.value.startsWith('blob:')) URL.revokeObjectURL(photoPreview.value)
    photoPreview.value = URL.createObjectURL(blob)
  } catch {
    photoPreview.value = ''
  }
}

// ---- 预览 / 生成 ----

function defaultTitle(): string {
  const name = (basic.name || '').trim()
  const primary = (wizard.directions[0] || '').trim()
  if (name && primary) return `${name}·${primary}简历`
  if (name) return `${name}的简历`
  if (primary) return `${primary}简历`
  return '个人简历'
}

function skillLabel(s: WizardSkill): string {
  if (!s.name?.trim()) return ''
  return s.level ? `${s.name.trim()}（${s.level}）` : s.name.trim()
}

function eduLine(e: WizardEducation): string {
  const parts = [e.school, e.degree, e.major].map((x) => (x || '').trim()).filter(Boolean)
  const period = formatPeriod(e)
  let line = parts.join(' · ')
  if (period) line = line ? `${line} · ${period}` : period
  const extras: string[] = []
  if (e.gpa?.trim()) extras.push(e.gpa.trim().toUpperCase().startsWith('GPA') ? e.gpa.trim() : `GPA ${e.gpa.trim()}`)
  if (e.rank?.trim()) extras.push(e.rank.includes('排名') ? e.rank.trim() : `排名 ${e.rank.trim()}`)
  if (extras.length) line = line ? `${line}（${extras.join('；')}）` : extras.join('；')
  if (e.courses?.trim()) line = line ? `${line}\n主修课程：${e.courses.trim()}` : `主修课程：${e.courses.trim()}`
  return line
}

function expBlock(e: WizardExpEntry): string {
  const header = [e.company, e.title, e.tech_stack, e.duration || formatPeriod(e)]
    .map((x) => (x || '').trim())
    .filter(Boolean)
    .join(' | ')
  const lines: string[] = []
  if (header) lines.push(header)
  const duty = (e.duty || e.action || '').trim()
  if (duty) lines.push(`职责：${duty}`)
  for (const [label, val] of [
    ['情境', e.situation], ['任务', e.task], ['行动', e.action], ['成果', e.result || e.achievement],
  ] as const) {
    const v = (val || '').trim()
    if (!v) continue
    if ((label === '行动' || label === '任务') && duty && v === duty) continue
    lines.push(`${label}：${v}`)
  }
  if (lines.length === 1 && (e.achievement || '').trim()) {
    lines.push(`成果：${e.achievement.trim()}`)
  }
  return lines.join('\n').trim()
}

function assemblePreview() {
  const out: { title: string; content: string }[] = []
  const info: string[] = []
  for (const [k, label] of [
    ['name', '姓名'], ['email', '邮箱'], ['phone', '电话'], ['location', '所在地'],
    ['birthday', '出生日期'], ['gender', '性别'],
  ] as const) {
    const v = (basic as any)[k] as string
    if (v && String(v).trim()) info.push(`${label}：${String(v).trim()}`)
  }
  if (info.length) out.push({ title: '基本信息', content: info.join('\n') })
  if (wizard.directions.length) out.push({ title: '求职意向', content: wizard.directions.join('、') })

  const edu = wizard.educations.map(eduLine).filter((s) => s.trim())
  if (edu.length) out.push({ title: '教育背景', content: edu.join('\n') })

  const work = wizard.internships.map(expBlock).filter((s) => s)
  if (work.length) out.push({ title: '实习/工作经历', content: work.join('\n\n') })
  const projects = wizard.projects.map(expBlock).filter((s) => s)
  if (projects.length) out.push({ title: '项目经历', content: projects.join('\n\n') })

  const skills = wizard.skills.map(skillLabel).filter(Boolean)
  if (skills.length) out.push({ title: '技能', content: skills.join('、') })

  const softParts = [wizard.soft_info.self_eval, wizard.soft_info.personality, wizard.soft_info.vision]
    .map((x) => (x || '').trim())
    .filter((x, i, arr) => x && arr.indexOf(x) === i)
  if (softParts.length) out.push({ title: '自我评价', content: softParts.join('\n') })

  const certs = basic.certifications.filter((c) => c && c.trim())
  if (certs.length) out.push({ title: '证书/荣誉', content: certs.join('\n') })
  return out
}

function rebuildModules() {
  const modules = assemblePreview()
  moduleEditor.value = modules.map((m, i) => ({ key: `${i}`, title: m.title, content: m.content }))
}

function moveModule(i: number, dir: number) {
  moveItem(moduleEditor.value, i, dir)
}

function gotoStep(step: number) {
  const max = STEPS.length
  wizard.step = Math.min(max, Math.max(1, step))
  if (wizard.step === 8) rebuildModules()
}
function prevStep() { gotoStep(wizard.step - 1) }
function nextStep() {
  gotoStep(wizard.step + 1)
  void onSaveDraft()
}

function snapshot(): Record<string, unknown> {
  return {
    draft_version: 2,
    basic_info: { ...basic },
    directions: [...wizard.directions],
    educations: wizard.educations.map((e) => ({ ...e })),
    skills: wizard.skills.map((s) => ({ ...s })),
    internships: wizard.internships.map((e) => ({ ...e })),
    projects: wizard.projects.map((e) => ({ ...e })),
    soft_info: { ...wizard.soft_info },
    photo_id: wizard.photo_id,
    module_order: moduleEditor.value.map((m) => m.title),
    page_preference: wizard.page_preference,
    template: wizard.template,
    title: wizard.title,
  }
}

/** 旧草稿自动迁移：education 文本 / 混合 experiences → 新结构 */
function migrateDraftData(d: Record<string, any>) {
  const bi = (d.basic_info || {}) as Record<string, any>
  Object.assign(basic, {
    name: bi.name || '',
    gender: bi.gender || '',
    phone: bi.phone || '',
    email: bi.email || '',
    location: bi.location || '',
    birthday: bi.birthday || '',
    certifications: Array.isArray(bi.certifications) ? [...bi.certifications] : [],
  })

  wizard.directions = Array.isArray(d.directions) ? [...d.directions] : []

  // 教育
  if (Array.isArray(d.educations)) {
    wizard.educations = d.educations.map((e: any) => ({ ...emptyEducation(), ...e, current: !!e.current }))
  } else if (Array.isArray(bi.education)) {
    wizard.educations = bi.education
      .filter((s: any) => typeof s === 'string' && s.trim())
      .map((s: string) => {
        const e = emptyEducation()
        const parts = s.split(/[·|｜]/).map((x) => x.trim())
        e.school = parts[0] || s.trim()
        if (parts[1]) e.degree = parts[1]
        if (parts[2]) e.major = parts[2]
        return e
      })
  }

  // 技能
  if (Array.isArray(d.skills)) {
    wizard.skills = d.skills
      .map((s: any) => (typeof s === 'string' ? { name: s, level: '' } : { name: s.name || '', level: s.level || '' }))
      .filter((s: WizardSkill) => s.name)
  } else if (Array.isArray(bi.skills)) {
    wizard.skills = bi.skills
      .filter((s: any) => typeof s === 'string' && s.trim())
      .map((s: string) => ({ name: s, level: '' }))
  }

  // 经历：优先新字段，否则从 experiences 分流
  if (Array.isArray(d.internships) || Array.isArray(d.projects)) {
    wizard.internships = (d.internships || []).map((e: any) => ({ ...emptyExp(), ...e, current: !!e.current }))
    wizard.projects = (d.projects || []).map((e: any) => ({ ...emptyExp(), ...e, current: !!e.current }))
  } else if (Array.isArray(d.experiences)) {
    wizard.internships = []
    wizard.projects = []
    for (const raw of d.experiences) {
      const entry = draftToEntry(raw)
      if (isInternType(raw?.exp_type)) wizard.internships.push(entry)
      else wizard.projects.push(entry)
    }
  }

  Object.assign(wizard.soft_info, (d.soft_info as any) || {})
  wizard.photo_id = (d.photo_id as number) || null
  wizard.page_preference = (d.page_preference as 'one_page' | 'two_pages') || 'one_page'
  if (d.template) wizard.template = String(d.template)
  wizard.title = (d.title as string) || wizard.title
}

function restore(data: Record<string, unknown>) {
  migrateDraftData(data || {})
}

/** 旧 7 步 → 新 8 步步骤号映射 */
function mapLegacyStep(step: number): number {
  // 旧: 1基础 2方向 3经历 4软性 5照片 6预览 7生成
  // 新: 1基本+方向 2教育 3技能 4实习 5项目 6自我 7照片 8生成
  if (step <= 2) return 1
  if (step === 3) return 4
  if (step === 4) return 6
  if (step === 5) return 7
  return 8
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

async function onExitToHome() {
  try {
    await saveDraft(wizard.step, snapshot())
  } catch { /* 暂存失败仍允许离开 */ }
  router.push('/')
}

async function onGenerate() {
  generating.value = true
  genError.value = ''
  generated.value = null
  try {
    if (!moduleEditor.value.length) rebuildModules()
    if (!wizard.title.trim() || wizard.title === '我的新简历') {
      wizard.title = defaultTitle()
    }
    const payload: WizardGeneratePayload = {
      title: wizard.title,
      basic_info: {
        name: basic.name,
        email: basic.email,
        phone: basic.phone,
        location: basic.location,
        gender: basic.gender,
        birthday: basic.birthday,
        certifications: basic.certifications.filter(Boolean),
      },
      directions: wizard.directions,
      educations: wizard.educations,
      skills: wizard.skills.filter((s) => s.name.trim()),
      internships: wizard.internships,
      projects: wizard.projects,
      soft_info: { ...wizard.soft_info },
      photo_id: wizard.photo_id,
      module_order: moduleEditor.value.map((m) => m.title),
      page_preference: wizard.page_preference,
      polish: true,
      import_to_library: true,
      template: wizard.template,
    }
    const res = await generateResume(payload)
    generated.value = res.data
    if (generated.value?.document?.title) {
      wizard.title = generated.value.document.title
    }
    await clearDraft()
    ElMessage.success('简历生成成功，已导入简历库')
  } catch (e: any) {
    genError.value = e?.response?.data?.detail || '生成失败，请重试'
  } finally {
    generating.value = false
  }
}

// ---- 导出 ----
const exporting = ref('')
const exportError = ref('')

function contentFromEditor(): { sections: { title: string; content: string }[]; raw_text: string } {
  if (!moduleEditor.value.length) rebuildModules()
  const sections = moduleEditor.value.map((m) => ({ title: m.title || '模块', content: m.content || '' }))
  const raw_text = sections.map((s) => `${s.title}\n${s.content}`).join('\n\n')
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
    const title = wizard.title.trim() && wizard.title !== '我的新简历' ? wizard.title : defaultTitle()
    const blob = await exportResume(content, title, format, wizard.photo_id)
    downloadBlob(blob, `${title}.${format === 'md' ? 'md' : format}`)
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
    const title = wizard.title.trim() && wizard.title !== '我的新简历' ? wizard.title : defaultTitle()
    const blob = await exportResume(currentContent(), title, 'html', wizard.photo_id)
    const url = URL.createObjectURL(blob)
    const win = window.open(url, '_blank')
    if (win) setTimeout(() => win.print(), 400)
    else downloadBlob(blob, `${title}.html`)
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
        const rawStep = res.data.step || 1
        // 若草稿已是 v2（含 educations/internships/projects 字段）则按原 step；否则映射
        const d = res.data.data || {}
        const isV2 = Array.isArray(d.educations) || Array.isArray(d.internships) || Array.isArray(d.projects) || d.draft_version === 2
        wizard.step = isV2 ? Math.min(STEPS.length, rawStep) : mapLegacyStep(rawStep)
        restore(d)
        if (wizard.step === 8) rebuildModules()
      } else {
        await clearDraft()
      }
    }
  } catch { /* 静默 */ }
  try {
    const photo = await getPhotoInfo()
    if (photo.data) {
      wizard.photo_id = photo.data.id
      await refreshPhotoPreview(photo.data.id)
    }
  } catch { /* 静默 */ }
  await loadProfileDirections()
})
</script>

<style scoped>
.gen-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg-page);
}
.gen-shell {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(260px, 320px) 1fr;
  width: 100%;
}

.gen-narrative {
  position: relative;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-10) var(--space-6);
  border-right: var(--border-light);
  display: flex; flex-direction: column; gap: var(--space-4);
  background: color-mix(in srgb, var(--color-bg-page) 70%, white);
}
.eyebrow { font-size: var(--text-sm); color: var(--color-accent-600); font-weight: var(--weight-semibold); letter-spacing: 0.08em; }
.narr-title { font-family: var(--font-display); font-size: var(--text-2xl); margin: 0; color: var(--color-text-primary); }
.narr-desc { color: var(--color-text-secondary); line-height: 1.7; margin: 0; max-width: 36ch; }
.narr-mark {
  margin-top: auto; width: 64px; height: 64px; border-radius: 20px;
  display: grid; place-items: center; color: var(--color-accent-600);
  background: var(--color-accent-50); border: 1px solid var(--color-accent-200);
}

.gen-main {
  min-height: 0;
  min-width: 0;
  padding: var(--space-6) var(--space-8) var(--space-10) var(--space-6);
  overflow-y: auto;
  overscroll-behavior: contain;
}
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
.draft-btn + .draft-btn { margin-left: 0; }

.gen-panel {
  background: var(--color-bg); border: 1px solid var(--border-light);
  border-radius: var(--radius-xl); padding: var(--space-6) var(--space-8); box-shadow: var(--shadow-card);
  min-height: calc(100% - 52px);
}
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-4); gap: var(--space-3); flex-wrap: wrap; }
.panel-head h2 { font-family: var(--font-display); font-size: var(--text-lg); margin: 0; color: var(--color-text-primary); }
.panel-head h2.sub-h { font-size: var(--text-md); }
.head-actions { display: flex; align-items: center; gap: var(--space-2); }
.soft-save-note {
  margin: var(--space-4) 0 0;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}
.soft-save-note.is-saved { color: var(--color-success-600); }
.hint { color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.6; margin: 0 0 var(--space-4); }
/* 表单铺满右栏，避免中间挤成一条、右侧大片留白 */
.gen-form { width: 100%; max-width: none; }
.gen-form :deep(.el-form-item) { margin-right: 0; }
.gen-form :deep(.el-form-item__content),
.gen-form :deep(.el-input),
.gen-form :deep(.el-select),
.gen-form :deep(.el-textarea),
.gen-form :deep(.el-date-editor) { width: 100%; max-width: 100%; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 var(--space-5); }
.list-editor { width: 100%; display: flex; flex-direction: column; gap: 6px; }
.list-row { width: 100%; }
.block-gap { height: var(--space-5); }
.period-end { display: flex; align-items: center; gap: 8px; width: 100%; }

.skill-row {
  display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
}
.quick-skill { margin-top: 8px; }
.cert-block {
  border: 1px dashed var(--color-border); border-radius: var(--radius-xl);
  padding: var(--space-3) var(--space-4);
}
.cert-block summary {
  cursor: pointer; font-weight: 600; color: var(--color-text-primary); font-size: var(--text-sm);
}

.empty-block {
  padding: var(--space-8) 0; text-align: center; color: var(--color-text-secondary);
  border: 1px dashed var(--color-border); border-radius: var(--radius-xl);
}

.dir-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--space-3); }
.dir-card {
  position: relative; border: 1px solid var(--color-border); border-radius: var(--radius-xl);
  padding: var(--space-4); cursor: pointer; transition: all var(--duration-fast) var(--ease-default);
}
.dir-card.selected { border-color: var(--color-accent-600); background: var(--color-accent-50); }
.dir-check { position: absolute; top: 10px; right: 12px; color: var(--color-accent-600); font-weight: 700; }
.dir-card-title { font-weight: var(--weight-semibold); color: var(--color-text-primary); }
.dir-card-reason { margin-top: 6px; font-size: var(--text-xs); color: var(--color-text-secondary); line-height: 1.5; }
.dir-profile-note { margin: 0 0 var(--space-3); font-size: var(--text-xs); color: var(--color-accent-600); }

.exp-ai-row {
  display: flex; flex-wrap: wrap; gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.exp-chip {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 16px; border-radius: var(--radius-full);
  border: 1px solid var(--color-border); background: var(--color-bg);
  color: var(--color-text-primary); font-size: var(--text-sm);
  cursor: pointer; transition: all var(--duration-fast) var(--ease-default);
}
.exp-chip:hover:not(:disabled) { border-color: var(--color-accent-400); background: var(--color-accent-50); }
.exp-chip.on { border-color: var(--color-accent-600); background: var(--color-accent-50); color: var(--color-accent-600); }
.exp-chip:disabled { opacity: 0.65; cursor: not-allowed; }
.chip-num {
  display: inline-grid; place-items: center;
  width: 20px; height: 20px; border-radius: 50%;
  background: color-mix(in srgb, var(--color-accent-600) 12%, white);
  color: var(--color-accent-600); font-size: 11px; font-weight: 700;
}
.exp-nl-box {
  border: 1px solid var(--color-border); border-radius: var(--radius-xl);
  padding: var(--space-4); margin-bottom: var(--space-4);
  background: var(--color-bg-elevated);
}
.exp-nl-actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.import-item { padding: var(--space-2) 0; border-bottom: var(--border-light); }
.import-item:last-of-type { border-bottom: none; }
.import-title { font-weight: 600; color: var(--color-text-primary); }
.import-preview {
  margin-left: 24px; margin-top: 2px; font-size: var(--text-xs);
  color: var(--color-text-secondary); line-height: 1.5;
}

.star-batch {
  display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap;
  margin-top: var(--space-4); padding-top: var(--space-4); border-top: var(--border-light);
}
.star-batch-hint { font-size: var(--text-xs); color: var(--color-text-secondary); }
.err { color: var(--color-danger-600); font-size: var(--text-sm); margin: 0 0 var(--space-3); }

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

.tpl-block { margin-top: var(--space-4); }
.tpl-label { font-size: var(--text-sm); font-weight: 600; margin-bottom: var(--space-2); color: var(--color-text-primary); }
.tpl-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--space-3); }
.tpl-card {
  text-align: left; border: 1px solid var(--color-border); border-radius: var(--radius-xl);
  padding: var(--space-3) var(--space-4); background: var(--color-bg-elevated);
  cursor: pointer; transition: border-color var(--duration-fast) var(--ease-default);
}
.tpl-card.selected { border-color: var(--color-accent-600); background: var(--color-accent-50); }
.tpl-title { font-weight: 600; color: var(--color-text-primary); margin-bottom: 4px; }
.tpl-desc { margin: 0; font-size: var(--text-xs); color: var(--color-text-secondary); line-height: 1.5; }

.gen-actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }

.result-box { margin-top: var(--space-5); border: 1px solid var(--color-success-600); background: var(--color-success-50); border-radius: var(--radius-xl); padding: var(--space-5); }
.result-head { display: flex; align-items: center; gap: 8px; margin-bottom: var(--space-4); }
.result-head .ok { color: var(--color-success-600); }
.result-title { font-weight: var(--weight-semibold); color: var(--color-text-primary); }
.result-sub { color: var(--color-text-tertiary); font-size: var(--text-xs); }
.result-preview { max-height: 320px; overflow-y: auto; }
.res-sec { padding: var(--space-3) 0; border-top: 1px dashed var(--color-border); }
.res-sec-title { font-weight: var(--weight-semibold); color: var(--color-accent-700); margin-bottom: 4px; }
.res-sec-content { margin: 0; white-space: pre-wrap; font-family: var(--font-sans); font-size: var(--text-sm); color: var(--color-text-secondary); line-height: 1.7; }
.result-actions { margin-top: var(--space-4); display: flex; gap: var(--space-2); flex-wrap: wrap; }

.foot-nav { display: flex; align-items: center; margin-top: var(--space-6); }

/* 窄屏：左栏介绍改顶部横条，表单单列 */
@media (max-width: 960px) {
  .gen-shell { grid-template-columns: 1fr; }
  .gen-narrative {
    border-right: none;
    border-bottom: var(--border-light);
    padding: var(--space-5) var(--space-5) var(--space-4);
    gap: var(--space-2);
  }
  .narr-title { font-size: var(--text-xl); }
  .narr-desc { max-width: none; }
  .narr-mark { display: none; }
  .form-grid { grid-template-columns: 1fr; }
  .gen-main { padding: var(--space-4) var(--space-4) var(--space-8); }
}
</style>
