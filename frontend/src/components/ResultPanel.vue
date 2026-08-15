<template>
  <div class="result-panel">
    <!-- 无数据时的空状态 -->
    <div v-if="!session.sessionId" class="empty-state">
      <el-icon :size="64" color="#c0c4cc"><Document /></el-icon>
      <h3>CareerAssistant</h3>
      <p>在左侧对话面板中输入 JD 和简历，分析结果将在此展示</p>
    </div>

    <!-- 有数据时的 Tab 展示 -->
    <div v-else class="panel-with-tabs">
      <div class="export-bar">
        <el-dropdown @command="handleExport">
          <el-button size="small" type="primary" plain :loading="exporting">
            导出简历<el-icon style="margin-left: 4px"><ArrowDown /></el-icon>
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

          <h4 style="margin-top: 16px">岗位要求</h4>
          <el-table :data="session.jdAnalysis.requirements" stripe>
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

          <div v-if="session.jdAnalysis.nice_to_have.length" style="margin-top: 16px">
            <h4>加分项</h4>
            <el-tag v-for="item in session.jdAnalysis.nice_to_have" :key="item" style="margin: 4px">
              {{ item }}
            </el-tag>
          </div>
        </div>
        <el-empty v-else description="暂无 JD 分析数据" />
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

          <div v-if="session.profile.skills.length" style="margin-top: 16px">
            <h4>技能标签</h4>
            <el-tag v-for="skill in session.profile.skills" :key="skill" type="success" style="margin: 4px">
              {{ skill }}
            </el-tag>
          </div>

          <div v-if="session.profile.experience.length" style="margin-top: 16px">
            <h4>工作经历</h4>
            <el-timeline>
              <el-timeline-item
                v-for="(exp, i) in session.profile.experience"
                :key="i"
                :timestamp="exp.duration"
                placement="top"
              >
                <el-card shadow="never">
                  <h4>{{ exp.title }} · {{ exp.company }}</h4>
                  <ul v-if="exp.highlights.length">
                    <li v-for="(h, j) in exp.highlights" :key="j">{{ h }}</li>
                  </ul>
                </el-card>
              </el-timeline-item>
            </el-timeline>
          </div>

          <div v-if="session.profile.projects.length" style="margin-top: 16px">
            <h4>项目经历</h4>
            <el-card v-for="(proj, i) in session.profile.projects" :key="i" shadow="never" style="margin-bottom: 12px">
              <h4>{{ proj.name }}</h4>
              <p>{{ proj.description }}</p>
              <div v-if="proj.tech_stack.length" style="margin-top: 8px">
                <el-tag v-for="tech in proj.tech_stack" :key="tech" size="small" type="info" style="margin: 2px">
                  {{ tech }}
                </el-tag>
              </div>
              <ul v-if="proj.highlights.length" style="margin-top: 8px">
                <li v-for="(h, j) in proj.highlights" :key="j">{{ h }}</li>
              </ul>
            </el-card>
          </div>
        </div>
        <el-empty v-else description="暂无个人画像数据" />
      </el-tab-pane>

      <!-- Gap 分析 Tab -->
      <el-tab-pane label="Gap 分析" name="gap">
        <div v-if="session.gapAnalysis" class="tab-content">
          <el-row :gutter="20">
            <el-col :span="8">
              <el-card shadow="never" class="score-card">
                <el-progress
                  type="dashboard"
                  :percentage="Math.round(session.gapAnalysis.overall_score)"
                  :color="scoreColor"
                />
                <p class="score-label">匹配度</p>
              </el-card>
            </el-col>
            <el-col :span="16">
              <h4>优势</h4>
              <el-tag v-for="s in session.gapAnalysis.strengths" :key="s" type="success" style="margin: 4px">
                {{ s }}
              </el-tag>
            </el-col>
          </el-row>

          <div style="margin-top: 20px">
            <h4>Gap 列表</h4>
            <el-table :data="session.gapAnalysis.gaps" stripe>
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

          <div v-if="session.gapAnalysis.recommendations.length" style="margin-top: 16px">
            <h4>建议</h4>
            <ul>
              <li v-for="(r, i) in session.gapAnalysis.recommendations" :key="i">{{ r }}</li>
            </ul>
          </div>
        </div>
        <el-empty v-else description="暂无 Gap 分析数据" />
      </el-tab-pane>

      <!-- 简历内容 Tab -->
      <el-tab-pane label="简历内容" name="resume">
        <div v-if="session.resumeContent" class="tab-content">
          <div v-for="(section, i) in session.resumeContent.sections" :key="i" class="resume-section">
            <h4>{{ section.title }}</h4>
            <div class="section-content" v-html="renderMarkdown(section.content)" />
          </div>
          <div v-if="session.renderConfig" style="margin-top: 16px">
            <el-divider />
            <p class="hint-text">
              模板: {{ session.renderConfig.template }} |
              字号: {{ session.renderConfig.font_size }}pt |
              行距: {{ session.renderConfig.line_spacing }}
            </p>
          </div>
        </div>
        <el-empty v-else description="暂无简历内容" />
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
                <h4>答题要点</h4>
                <ul>
                  <li v-for="(p, j) in q.answer_points" :key="j">{{ p }}</li>
                </ul>
              </div>
              <div v-if="q.sample_answer" style="margin-top: 12px">
                <h4>参考回答</h4>
                <p>{{ q.sample_answer }}</p>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
        <el-empty v-else description="暂无面试题" />
      </el-tab-pane>
    </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowDown, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useSessionStore } from '../stores/session'
import { exportResume } from '../api/sessions'

const session = useSessionStore()
const exporting = ref(false)

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
  if (score >= 75) return '#67c23a'
  if (score >= 50) return '#e6a23c'
  return '#f56c6c'
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
  height: 100%;
  padding: 16px;
  overflow-y: auto;
}

.panel-with-tabs {
  height: 100%;
}

.export-bar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

.empty-state h3 {
  margin: 16px 0 8px;
  color: #303133;
}

.result-tabs {
  height: 100%;
}

.tab-content {
  padding: 8px 0;
}

.score-card {
  text-align: center;
}

.score-label {
  margin-top: 12px;
  font-size: 16px;
  color: #606266;
  font-weight: 500;
}

.resume-section {
  margin-bottom: 20px;
}

.resume-section h4 {
  border-bottom: 2px solid #409eff;
  padding-bottom: 4px;
  color: #303133;
}

.section-content {
  line-height: 1.6;
  color: #606266;
}

.question-header {
  display: flex;
  align-items: center;
  width: 100%;
}

.hint-text {
  color: #909399;
  font-size: 13px;
}
</style>
