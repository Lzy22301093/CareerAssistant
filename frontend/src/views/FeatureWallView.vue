<template>
  <div class="wall-page">
    <AppNav />

    <main class="wall-main">
      <div class="wall-hero">
        <p class="eyebrow">CareerAssistant</p>
        <h1 class="wall-title">功能墙</h1>
        <p class="wall-subtitle">把求职，变成一件有把握的事。</p>
      </div>

      <div class="wall-grid">
        <component
          :is="card.locked ? 'div' : RouterLink"
          :to="card.locked ? undefined : card.route"
          v-for="(card, i) in cards"
          :key="card.label"
          class="wall-card"
          :class="{ 'is-locked': card.locked }"
          :style="{ '--accent': card.accent, '--delay': `${i * 80}ms` }"
          @click="card.locked && notifyLocked(card)"
        >
          <span class="card-accent" aria-hidden="true"></span>
          <div class="card-content">
            <div class="card-icon">
              <component :is="card.icon" :size="20" />
            </div>
            <div class="card-text">
              <div class="card-label">{{ card.label }}</div>
              <div class="card-desc">{{ card.desc }}</div>
              <div class="card-cta">{{ card.locked ? '后续上线' : '进入 →' }}</div>
            </div>
          </div>
        </component>
      </div>

      <div class="wall-footnote">
        <span class="footnote-dot"></span>
        <span>你的数据，只属于你</span>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import {
  Library,
  FileText,
  MessagesSquare,
  Compass,
  Heart,
  Megaphone,
  Briefcase,
  Code2,
  Sparkles,
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { RouterLink } from 'vue-router'
import AppNav from '../components/AppNav.vue'

type Card = {
  label: string
  desc: string
  icon: any
  route: string
  accent: string
  locked?: boolean
}

const cards: Card[] = [
  {
    label: '个人知识库',
    desc: '基本事实 · 教育 · 经历 · 技能 · 面试反馈',
    icon: Library,
    route: '/knowledge-base',
    accent: '#c15f3c',
  },
  {
    label: '简历工作台',
    desc: '简历库 · 多版本 · 区域改写 · 岗位匹配',
    icon: FileText,
    route: '/resume-library',
    accent: '#b57b1f',
  },
  {
    label: '简历生成',
    desc: '8 步向导，从画像到生成 · 导入 Word/PDF 简历',
    icon: Sparkles,
    route: '/resume-generation',
    accent: '#c15f3c',
  },
  {
    label: 'AI 模拟面试',
    desc: '基于你的画像与简历，反复演练',
    icon: MessagesSquare,
    route: '/mock-interview',
    accent: '#5b6b9e',
  },
  {
    label: 'AI 助手工作台',
    desc: '贴 JD · 传简历 · 对话式协作与结果面板',
    icon: Code2,
    route: '/workspace',
    accent: '#4c7f7d',
  },
  {
    label: '画像与投递方向',
    desc: 'AI 推荐方向，选 1~3 个目标岗位',
    icon: Compass,
    route: '/job-directions',
    accent: '#8a5a83',
  },
  {
    label: '软性信息',
    desc: '性格 · 愿景 · 自我评价，AI 帮你生成',
    icon: Heart,
    route: '/soft-info',
    accent: '#b85c6e',
  },
  {
    label: '投递记录',
    desc: '手动登记投递 · 状态跟踪 · 进度提醒',
    icon: Megaphone,
    route: '/applications',
    accent: '#6f8f5f',
  },
  {
    label: '求职任务',
    desc: 'JD · 匹配 · 投递状态，一次只追一个岗位',
    icon: Briefcase,
    route: '',
    accent: '#a8a294',
    locked: true,
  },
]

function notifyLocked(card: Card) {
  ElMessage.info(`${card.label} 将在后续阶段上线`)
}
</script>

<style scoped>
.wall-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-page);
}

.wall-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-12) var(--space-8) var(--space-10);
}

.wall-hero {
  text-align: center;
  margin-bottom: var(--space-10);
}
.eyebrow {
  margin: 0 0 var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-accent-600);
}
.wall-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--text-4xl);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
  letter-spacing: -0.02em;
}
.wall-subtitle {
  margin: var(--space-3) 0 0;
  color: var(--color-text-secondary);
  font-size: var(--text-md);
}

.wall-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: var(--space-4);
  width: 100%;
  max-width: 1080px;
}

.wall-card {
  position: relative;
  display: block;
  overflow: hidden;
  background: var(--color-bg-elevated);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-5) var(--space-5) var(--space-5) var(--space-6);
  text-decoration: none;
  box-shadow: var(--shadow-card);
  opacity: 0;
  animation: rise 0.45s ease forwards;
  animation-delay: var(--delay, 0ms);
  transition: transform var(--duration-normal) var(--ease-out), box-shadow var(--duration-normal) var(--ease-out), border-color var(--duration-normal) var(--ease-out);
}
.wall-card:hover {
  transform: translateY(-3px);
  border-color: color-mix(in srgb, var(--accent) 40%, transparent);
  box-shadow: var(--shadow-md);
}

.card-accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--accent);
}

.wall-card.is-locked {
  opacity: 0.6;
  cursor: default;
}
.wall-card.is-locked:hover {
  transform: none;
  box-shadow: var(--shadow-card);
  border-color: var(--border-light);
}

.card-content {
  display: flex;
  gap: var(--space-4);
  align-items: flex-start;
}
.card-icon {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--accent) 14%, white);
  color: var(--accent);
}
.card-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.card-label {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
  letter-spacing: -0.01em;
}
.card-desc {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-relaxed);
}
.card-cta {
  margin-top: 6px;
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--accent);
}

.wall-footnote {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-10);
  padding: var(--space-2) var(--space-4);
  border: var(--border-light);
  border-radius: var(--radius-full);
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
  font-size: var(--text-xs);
}
.footnote-dot {
  width: 7px;
  height: 7px;
  border-radius: var(--radius-full);
  background: var(--color-success-600);
}

@keyframes rise {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
