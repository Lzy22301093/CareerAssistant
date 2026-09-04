<template>
  <div class="wall-page">
    <!-- 展开态：完整功能墙 -->
    <template v-if="!collapsed">
      <header class="wall-header">
        <div class="brand">CareerAssistant</div>
        <el-dropdown @command="handleCommand">
          <el-button text>
            <User :size="16" />{{ auth.user?.username || '用户' }}
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>

      <main class="wall-main">
        <h1 class="wall-title">功能墙</h1>
        <p class="wall-subtitle">从左下到右上，逐级进入你的求职工作流</p>

        <div class="wall-grid">
          <div
            v-for="(card, i) in cards"
            :key="card.label"
            class="wall-card"
            :class="{ 'is-locked': card.locked }"
            :style="{ '--delay': `${i * 90}ms` }"
            @click="go(card)"
          >
            <div class="card-icon"><component :is="card.icon" :size="22" /></div>
            <div class="card-body">
              <div class="card-tag">{{ card.tag }}</div>
              <div class="card-label">{{ card.label }}</div>
              <div class="card-desc">{{ card.desc }}</div>
              <div class="card-cta">{{ card.locked ? '后续阶段上线' : '点击进入 →' }}</div>
            </div>
          </div>
        </div>

        <div class="wall-footer">
          <el-button round @click="collapsed = true">收起功能墙</el-button>
          <span class="wall-note">数据安全，你的画像与简历由你掌控</span>
        </div>
      </main>
    </template>

    <!-- 收起态：紧凑导航 -->
    <div v-else class="compact-nav">
      <router-link to="/" class="compact-brand" @click="collapsed = false">CareerAssistant</router-link>
      <nav class="compact-links">
        <button
          v-for="m in compactModules"
          :key="m.label"
          class="compact-link"
          @click="go(m)"
        >{{ m.label }}</button>
      </nav>
      <div class="compact-right">
        <el-dropdown @command="handleCommand">
          <el-button text>
            <User :size="16" />{{ auth.user?.username || '用户' }}
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button text type="primary" @click="collapsed = false">展开功能墙</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  User,
  Library,
  FileText,
  Briefcase,
  MessagesSquare,
  Megaphone,
} from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const collapsed = ref(false)

type Card = {
  label: string
  desc: string
  tag: string
  icon: any
  route: string
  locked?: boolean
}

const cards = computed<Card[]>(() => [
  {
    label: '个人知识库',
    desc: '基本事实 · 教育 · 经历 · 技能 · 面试反馈',
    tag: '建立可复用的个人画像',
    icon: Library,
    route: '/knowledge-base',
  },
  {
    label: '简历工作台',
    desc: '简历库 · 分析 · 匹配',
    tag: '打磨并追踪简历',
    icon: FileText,
    route: '/workspace',
  },
  {
    label: 'AI 模拟面试',
    desc: '基于你的画像与简历，反复演练',
    tag: '面试官视角持续反馈',
    icon: MessagesSquare,
    route: '/mock-interview',
  },
  {
    label: '求职任务',
    desc: 'JD · 匹配 · 投递状态',
    tag: '一次只追一个岗位',
    icon: Briefcase,
    route: '',
    locked: true,
  },
  {
    label: '投递信息圈',
    desc: '公司区 · 秋招信息 · 投递记录',
    tag: '后置模块',
    icon: Megaphone,
    route: '',
    locked: true,
  },
])

const compactModules = computed<Card[]>(() =>
  cards.value.filter((c) => !c.locked),
)

function go(card: Card) {
  if (card.locked) {
    ElMessage.info(`${card.label} 将在后续阶段上线`)
    return
  }
  router.push(card.route)
}

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.wall-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-page);
}
.wall-header {
  height: 48px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-8);
  background: var(--color-bg);
  border-bottom: var(--border-light);
}
.brand {
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}
.wall-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-8);
  text-align: center;
}
.wall-title {
  margin: 0 0 var(--space-2);
  font-size: 40px;
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
  letter-spacing: -0.02em;
}
.wall-subtitle {
  margin: 0 0 var(--space-10);
  color: var(--color-text-secondary);
  font-size: 15px;
}
.wall-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-5);
  max-width: 960px;
  width: 100%;
}
.wall-card {
  display: flex;
  gap: var(--space-4);
  align-items: flex-start;
  background: var(--color-bg);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: var(--space-5);
  cursor: pointer;
  opacity: 0;
  animation: rise 0.4s ease forwards;
  animation-delay: var(--delay, 0ms);
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}
.wall-card:hover {
  border-color: var(--el-color-primary);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  transform: translateY(-2px);
}
.wall-card.is-locked {
  opacity: 0.55;
}
.card-icon {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: var(--color-primary-50, #eff6ff);
  color: var(--el-color-primary);
}
.card-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
}
.card-tag {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.card-label {
  font-size: 18px;
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}
.card-desc {
  font-size: 13px;
  color: var(--color-text-tertiary, #9ca3af);
}
.card-cta {
  margin-top: 6px;
  font-size: 13px;
  color: var(--el-color-primary);
}
.wall-footer {
  margin-top: var(--space-10);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}
.wall-note {
  font-size: 12px;
  color: var(--color-text-tertiary, #9ca3af);
}

/* 收起态：紧凑导航 */
.compact-nav {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  background: var(--color-bg);
  border-bottom: var(--border-light);
}
.compact-brand {
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
  text-decoration: none;
}
.compact-links {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.compact-link {
  border: none;
  background: transparent;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--color-text-secondary);
  cursor: pointer;
}
.compact-link:hover {
  color: var(--color-text-primary);
  background: var(--color-gray-50, #f9fafb);
}
.compact-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
