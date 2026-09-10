<template>
  <div class="result-panel">
    <!-- 无数据时的空状态 -->
    <ScreenState
      v-if="!session.sessionId"
      type="empty"
      title="CareerAssistant"
      desc="在左侧对话面板中输入 JD 和简历，分析结果将在此展示"
    />

    <!-- 有数据时的 Tab 展示 -->
    <div v-else class="panel-with-tabs">
      <div class="export-bar">
        <el-dropdown @command="handleExport">
          <el-button size="small" type="primary" plain :loading="exporting">
            导出简历<ChevronDown :size="16" style="margin-left: 4px" />
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="html">HTML</el-dropdown-item>
              <el-dropdown-item command="json">JSON</el-dropdown-item>
              <el-dropdown-item command="md">Markdown</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    <el-tabs v-model="session.activeTab" class="result-tabs">
      <!-- JD 分析 Tab -->
      <el-tab-pane label="JD 分析" name="jd">
        <div v-if="session.jdAnalysis" class="tab-content">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="职位名称">{{ session.jdAnalysis.job_title }}</el-descriptions-item>
            <el-descriptions-item label="公司">{{ session.jdAnalysis.company || '-' }}</el-descriptions-item>
            <el-descriptions-item label="薪资">{{ session.jdAnalysis.salary_range || '-' }}</el-descriptions-item>
            <el-descriptions-item label="地点">{{ session.jdAnalysis.location || '-' }}</el-descriptions-item>
            <el-descriptions-item label="摘要" :span="2">{{ session.jdAnalysis.summary }}</el-descriptions-item>
          </el-descriptions>

          <h4 class="section-title">岗位要求</h4>
          <el-table :data="session.jdAnalysis.requirements">
            <el-table-column prop="category" label="类别" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.category }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="content" label="要求内容" />
            <el-table-column prop="importance" label="重要性" width="100">
              <template #default="{ row }">
                <el-tag :type="importanceType(row.importance)" size="small">
                  {{ row.importance }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <div v-if="session.jdAnalysis.nice_to_have.length" class="nice-to-have-section">
            <h4 class="section-title">加分项</h4>
            <div class="tag-list">
              <el-tag v-for="item in session.jdAnalysis.nice_to_have" :key="item" size="small">
                {{ item }}
              </el-tag>
            </div>
          </div>
        </div>
        <SkeletonLoader v-else-if="session.isLoading" variant="table" :rows="5" />
        <div v-else class="tab-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <p>暂无 JD 分析数据</p>
          <p class="tab-empty-hint">请在左侧对话中粘贴目标岗位 JD</p>
        </div>
      </el-tab-pane>

      <!-- 个人画像 Tab -->
      <el-tab-pane label="个人画像" name="profile">
        <div v-if="session.profile" class="tab-content">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="姓名">{{ session.profile.name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="邮箱">{{ session.profile.email || '-' }}</el-descriptions-item>
            <el-descriptions-item label="电话">{{ session.profile.phone || '-' }}</el-descriptions-item>
            <el-descriptions-item label="摘要" :span="2">{{ session.profile.summary || '-' }}</el-descriptions-item>
          </el-descriptions>

          <div v-if="session.profile.skills.length" class="skills-section">
            <h4 class="section-title">技能标签</h4>
            <div class="tag-list">
              <el-tag v-for="skill in session.profile.skills" :key="skill" type="success" size="small">
                {{ skill }}
              </el-tag>
            </div>
          </div>

          <div v-if="session.profile.experience.length" class="experience-section">
            <h4 class="section-title">工作经历</h4>
            <el-timeline>
              <el-timeline-item
                v-for="(exp, i) in session.profile.experience"
                :key="i"
                :timestamp="exp.duration"
                placement="top"
              >
                <div class="experience-card">
                  <h4 class="exp-title">{{ exp.title }} · {{ exp.company }}</h4>
                  <ul v-if="exp.highlights.length" class="exp-highlights">
                    <li v-for="(h, j) in exp.highlights" :key="j">{{ h }}</li>
                  </ul>
                </div>
              </el-timeline-item>
            </el-timeline>
          </div>

          <div v-if="session.profile.projects.length" class="projects-section">
            <h4 class="section-title">项目经历</h4>
            <div v-for="(proj, i) in session.profile.projects" :key="i" class="project-card">
              <h4 class="proj-title">{{ proj.name }}</h4>
              <p class="proj-desc">{{ proj.description }}</p>
              <div v-if="proj.tech_stack.length" class="tag-list">
                <el-tag v-for="tech in proj.tech_stack" :key="tech" size="small" type="info">
                  {{ tech }}
                </el-tag>
              </div>
              <ul v-if="proj.highlights.length" class="proj-highlights">
                <li v-for="(h, j) in proj.highlights" :key="j">{{ h }}</li>
              </ul>
            </div>
          </div>
        </div>
        <SkeletonLoader v-else-if="session.isLoading" variant="card" :lines="3" />
        <div v-else class="tab-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
          <p>暂无个人画像数据</p>
          <p class="tab-empty-hint">请在左侧对话中上传简历或输入个人信息</p>
        </div>
      </el-tab-pane>

      <!-- Gap 分析 Tab -->
      <el-tab-pane label="Gap 分析" name="gap">
        <div v-if="session.gapAnalysis" class="tab-content">
          <!-- 匹配度：横向进度条 -->
          <div class="score-section">
            <div class="score-header">
              <span class="score-label">匹配度</span>
              <span class="score-value" :style="{ color: scoreColor }">{{ Math.round(session.gapAnalysis.overall_score) }}%</span>
            </div>
            <div class="score-bar-track">
              <div
                class="score-bar-fill"
                :style="{ width: `${session.gapAnalysis.overall_score}%`, backgroundColor: scoreColor }"
              />
            </div>
          </div>

          <div v-if="session.gapAnalysis.strengths.length" class="strengths-section">
            <h4 class="section-title">优势</h4>
            <div class="tag-list">
              <el-tag v-for="s in session.gapAnalysis.strengths" :key="s" type="success" size="small">
                {{ s }}
              </el-tag>
            </div>
          </div>

          <div class="gaps-section">
            <h4 class="section-title">Gap 列表</h4>
            <el-table :data="session.gapAnalysis.gaps">
              <el-table-column prop="category" label="类别" width="100">
                <template #default="{ row }">
                  <el-tag size="small">{{ row.category }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="requirement" label="JD 要求" />
              <el-table-column prop="current_level" label="当前水平" />
              <el-table-column prop="gap_severity" label="严重度" width="100">
                <template #default="{ row }">
                  <el-tag :type="severityType(row.gap_severity)" size="small">
                    {{ row.gap_severity }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="suggestion" label="建议" />
            </el-table>
          </div>

          <div v-if="session.gapAnalysis.recommendations.length" class="recommendations-section">
            <h4 class="section-title">建议</h4>
            <ul class="recommendation-list">
              <li v-for="(r, i) in session.gapAnalysis.recommendations" :key="i">{{ r }}</li>
            </ul>
          </div>
        </div>
        <SkeletonLoader v-else-if="session.isLoading" variant="chart" />
        <div v-else class="tab-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="20" x2="18" y2="10"/>
            <line x1="12" y1="20" x2="12" y2="4"/>
            <line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
          <p>暂无 Gap 分析数据</p>
          <p class="tab-empty-hint">请在左侧对话中同时提供 JD 和简历</p>
        </div>
      </el-tab-pane>

      <!-- 简历内容 Tab -->
      <el-tab-pane label="简历内容" name="resume">
        <div v-if="session.resumeContent" class="tab-content">
          <div v-for="(section, i) in session.resumeContent.sections" :key="i" class="resume-section">
            <h4 class="resume-section-title">{{ section.title }}</h4>
            <div class="section-content" v-html="renderMarkdown(section.content)" />
          </div>
          <div v-if="session.renderConfig" class="render-config">
            <el-divider />
            <p class="hint-text">
              模板: {{ session.renderConfig.template }} |
              字号: {{ session.renderConfig.font_size }}pt |
              行距: {{ session.renderConfig.line_spacing }}
            </p>
          </div>
        </div>
        <SkeletonLoader v-else-if="session.isLoading" variant="text" :lines="6" />
        <div v-else class="tab-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <p>暂无简历内容</p>
          <p class="tab-empty-hint">请在左侧对话中提供 JD 和简历以生成优化内容</p>
        </div>
      </el-tab-pane>

      <!-- 面试准备 Tab -->
      <el-tab-pane label="面试准备" name="interview">
        <div v-if="session.interviewQuestions.length" class="tab-content">
          <el-collapse>
            <el-collapse-item
              v-for="(q, i) in session.interviewQuestions"
              :key="i"
              :name="i"
            >
              <template #title>
                <div class="question-header">
                  <el-tag :type="difficultyType(q.difficulty)" size="small">{{ q.difficulty }}</el-tag>
                  <el-tag size="small" type="info" style="margin-left: 8px">{{ q.category }}</el-tag>
                  <span style="margin-left: 12px">{{ q.question }}</span>
                </div>
              </template>
              <div v-if="q.answer_points.length">
                <h4 class="section-title">答题要点</h4>
                <ul class="answer-points">
                  <li v-for="(p, j) in q.answer_points" :key="j">{{ p }}</li>
                </ul>
              </div>
              <div v-if="q.sample_answer" class="sample-answer">
                <h4 class="section-title">参考回答</h4>
                <p>{{ q.sample_answer }}</p>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
        <SkeletonLoader v-else-if="session.isLoading" variant="card" :lines="4" />
        <div v-else class="tab-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <p>暂无面试题</p>
          <p class="tab-empty-hint">完成 Gap 分析后将自动生成面试准备内容</p>
        </div>
      </el-tab-pane>

      <!-- AI 模拟面试 Tab -->
      <el-tab-pane label="AI 模拟面试" name="voice-chat">
        <div class="tab-content voice-chat-tab">
          <div v-if="session.voiceChatActive" class="voice-chat-active">
            <VoiceInterviewPanel
              :ws-url="session.voiceChatWsUrl"
              mode="chat"
              @end="onVoiceChatEnd"
            />
          </div>
          <div v-else class="voice-chat-start">
            <div class="voice-chat-info">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8" y1="23" x2="16" y2="23"/>
              </svg>
              <h3>AI 模拟面试</h3>
              <p>基于 JD 分析和个人画像，进行一场逼真的语音模拟面试</p>
              <el-button
                type="primary"
                size="large"
                :disabled="!canStartVoiceChat"
                @click="startVoiceChat"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                </svg>
                开始语音面试
              </el-button>
              <p v-if="!canStartVoiceChat" class="voice-chat-hint">
                请先完成 JD 分析后再开始模拟面试
              </p>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 调试 Tab -->
      <el-tab-pane label="调试" name="debug">
        <div class="tab-content debug-panel">
          <!-- Session ID -->
          <div class="debug-section">
            <h4 class="section-title">Session ID</h4>
            <code class="debug-code">{{ session.sessionId || '-' }}</code>
          </div>

          <!-- Agent 链路 -->
          <div class="debug-section">
            <h4 class="section-title">触发的 Agent 链路</h4>
            <div v-if="session.triggeredAgents.length" class="agent-chain">
              <span v-for="(agent, i) in session.triggeredAgents" :key="i" class="agent-pill">
                <span class="agent-name">{{ agent }}</span>
                <span v-if="i < session.triggeredAgents.length - 1" class="agent-arrow">→</span>
              </span>
            </div>
            <p v-else class="debug-empty">暂无 Agent 链路数据</p>
          </div>

          <!-- resume_content_json -->
          <div class="debug-section">
            <h4 class="section-title">
              Resume Content JSON
              <el-button size="small" text @click="copyJson('resume')">复制</el-button>
            </h4>
            <pre class="json-block">{{ formattedResumeJson }}</pre>
          </div>

          <!-- render_config -->
          <div class="debug-section">
            <h4 class="section-title">
              Render Config
              <el-button size="small" text @click="copyJson('render')">复制</el-button>
            </h4>
            <pre class="json-block">{{ formattedRenderConfig }}</pre>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { useSessionStore } from '../stores/session'
import { exportResume } from '../api/sessions'
import SkeletonLoader from './SkeletonLoader.vue'
import VoiceInterviewPanel from './VoiceInterviewPanel.vue'
import ScreenState from './ScreenState.vue'

const session = useSessionStore()
const exporting = ref(false)

// Voice Chat
const canStartVoiceChat = computed(() => {
  return !!session.jdAnalysis && !!session.sessionId
})

async function startVoiceChat() {
  if (!session.sessionId) return
  try {
    const res = await fetch(`/api/sessions/${session.sessionId}/voice-chat`, { method: 'POST' })
    if (!res.ok) {
      const data = await res.json()
      ElMessage.error(data.detail || '启动失败')
      return
    }
    const data = await res.json()
    session.voiceChatActive = true
    session.voiceChatWsUrl = data.ws_url
    ElMessage.success('语音面试已启动')
  } catch (e) {
    ElMessage.error('启动语音面试失败')
  }
}

function onVoiceChatEnd() {
  session.voiceChatActive = false
  session.voiceChatWsUrl = ''
}

const formattedResumeJson = computed(() => {
  if (!session.resumeContent) return 'null'
  return JSON.stringify(session.resumeContent, null, 2)
})

const formattedRenderConfig = computed(() => {
  if (!session.renderConfig) return 'null'
  return JSON.stringify(session.renderConfig, null, 2)
})

function copyJson(type: 'resume' | 'render') {
  const text = type === 'resume' ? formattedResumeJson.value : formattedRenderConfig.value
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制到剪贴板')
  })
}

async function handleExport(format: string) {
  if (!session.sessionId) return
  exporting.value = true
  try {
    const res = await exportResume(session.sessionId, format as 'html' | 'json' | 'md')
    // 触发浏览器下载
    const blob = res.data as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `resume_${session.sessionId.slice(0, 8)}.${format === 'md' ? 'md' : format}`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error((e as Error)?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

function importanceType(val: string) {
  return val === 'high' ? 'danger' : val === 'medium' ? 'warning' : 'info'
}

function severityType(val: string) {
  return val === 'critical' ? 'danger' : val === 'major' ? 'warning' : 'info'
}

function difficultyType(val: string) {
  return val === 'hard' ? 'danger' : val === 'medium' ? 'warning' : 'success'
}

const scoreColor = computed(() => {
  const score = session.gapAnalysis?.overall_score || 0
  if (score >= 75) return 'var(--color-success-600)'
  if (score >= 50) return 'var(--color-warning-600)'
  return 'var(--color-danger-600)'
})

/** 简单 Markdown 渲染（加粗、换行、列表） */
function renderMarkdown(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
    .replace(/^- (.+)/gm, '<li>$1</li>')
}
</script>

<style scoped>
.result-panel {
  flex: 1;
  min-height: 0;
  padding: var(--space-4);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-with-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.export-bar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: var(--space-2);
}

/* ── 空状态 ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  padding: var(--space-8);
}

.empty-icon {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--color-accent-600) 12%, white);
  border-radius: var(--radius-lg);
  color: var(--color-accent-600);
  margin-bottom: var(--space-4);
}

.empty-title {
  margin: 0 0 var(--space-2);
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}

.empty-desc {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  max-width: 300px;
  line-height: var(--leading-relaxed);
}

/* ── Tab 内空状态 ── */
.tab-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-12) var(--space-8);
  text-align: center;
  color: var(--color-text-disabled);
}

.tab-empty svg {
  margin-bottom: var(--space-3);
}

.tab-empty p {
  margin: 0 0 var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.tab-empty-hint {
  font-size: var(--text-xs) !important;
  color: var(--color-text-disabled) !important;
}

/* ── Tab 内容 ── */
.result-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.result-tabs :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 var(--space-4) var(--space-4);
}

.tab-content {
  padding: var(--space-2) 0;
}

.section-title {
  margin: var(--space-4) 0 var(--space-2);
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

/* ── 匹配度进度条 ── */
.score-section {
  background: var(--color-bg-elevated);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
}

.score-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: var(--space-2);
}

.score-label {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--color-text-secondary);
}

.score-value {
  font-size: var(--text-xl);
  font-weight: var(--weight-semibold);
  font-family: var(--font-mono);
}

.score-bar-track {
  height: 8px;
  background: var(--color-gray-200);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.score-bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width var(--duration-slow) var(--ease-out);
}

/* ── 工作经历卡片 ── */
.experience-card {
  background: var(--color-bg-elevated);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-4);
}

.exp-title {
  margin: 0 0 var(--space-2);
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}

.exp-highlights {
  margin: 0;
  padding-left: var(--space-5);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
}

.exp-highlights li {
  margin-bottom: var(--space-1);
}

/* ── 项目卡片 ── */
.project-card {
  background: var(--color-bg-elevated);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: var(--space-4);
  margin-bottom: var(--space-3);
}

.proj-title {
  margin: 0 0 var(--space-2);
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}

.proj-desc {
  margin: 0 0 var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}

.proj-highlights {
  margin: var(--space-2) 0 0;
  padding-left: var(--space-5);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
}

.proj-highlights li {
  margin-bottom: var(--space-1);
}

/* ── 简历内容 ── */
.resume-section {
  margin-bottom: var(--space-5);
}

.resume-section-title {
  border-bottom: 2px solid var(--color-accent-600);
  padding-bottom: var(--space-1);
  margin: 0 0 var(--space-3);
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}

.section-content {
  line-height: var(--leading-relaxed);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
}

.render-config {
  margin-top: var(--space-4);
}

/* ── 面试准备 ── */
.question-header {
  display: flex;
  align-items: center;
  width: 100%;
}

.answer-points {
  margin: 0;
  padding-left: var(--space-5);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
}

.answer-points li {
  margin-bottom: var(--space-1);
}

.sample-answer {
  margin-top: var(--space-3);
}

.sample-answer p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
}

/* ── 通用 ── */
.hint-text {
  color: var(--color-text-disabled);
  font-size: var(--text-sm);
}

.nice-to-have-section,
.skills-section,
.strengths-section,
.experience-section,
.projects-section,
.gaps-section,
.recommendations-section {
  margin-top: var(--space-4);
}

.recommendation-list {
  margin: 0;
  padding-left: var(--space-5);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
}

.recommendation-list li {
  margin-bottom: var(--space-1);
}

/* ── 调试面板 ── */
.debug-panel {
  padding: var(--space-2) 0;
}

.debug-section {
  margin-bottom: var(--space-5);
}

.debug-code {
  display: inline-block;
  padding: var(--space-1) var(--space-2);
  background: var(--color-gray-100);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  word-break: break-all;
}

.agent-chain {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
}

.agent-pill {
  display: inline-flex;
  align-items: center;
}

.agent-name {
  display: inline-block;
  padding: 2px 10px;
  background: var(--color-accent-50);
  border: 1px solid var(--color-accent-200);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  color: var(--color-accent-700);
}

.agent-arrow {
  margin: 0 2px;
  color: var(--color-text-disabled);
  font-size: var(--text-sm);
}

.json-block {
  background: var(--color-gray-50);
  border: var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}

.debug-empty {
  color: var(--color-text-disabled);
  font-size: var(--text-sm);
}

/* ── AI 模拟面试 Tab ── */
.voice-chat-tab {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.voice-chat-active {
  flex: 1;
  min-height: 0;
}

.voice-chat-start {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.voice-chat-info {
  text-align: center;
  max-width: 360px;
}

.voice-chat-info svg {
  color: var(--color-accent-600);
  margin-bottom: var(--space-4);
}

.voice-chat-info h3 {
  margin: 0 0 var(--space-2);
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}

.voice-chat-info p {
  margin: 0 0 var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}

.voice-chat-hint {
  color: var(--color-text-disabled) !important;
  font-size: var(--text-xs) !important;
}
</style>
