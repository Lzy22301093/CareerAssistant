<template>
  <header class="app-nav">
    <div class="nav-left">
      <router-link to="/" class="brand">
        <span class="brand-mark" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </span>
        <span class="brand-name">CareerAssistant</span>
      </router-link>

      <nav class="nav-links">
        <router-link
          v-for="m in modules"
          :key="m.route"
          :to="m.route"
          class="nav-link"
        >
          <component :is="m.icon" :size="15" class="nav-icon" />
          <span>{{ m.label }}</span>
        </router-link>
      </nav>
    </div>

    <div class="nav-right">
      <slot />
      <el-dropdown trigger="click" @command="handleCommand">
        <button class="user-chip" type="button">
          <span class="avatar">{{ initials }}</span>
          <span class="user-name">{{ auth.user?.username || '用户' }}</span>
          <ChevronDown :size="14" class="chev" />
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">
              <LogOut :size="14" style="margin-right: 6px" />退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Library,
  FileText,
  User,
  Megaphone,
  MessagesSquare,
  Code2,
  LogOut,
  ChevronDown,
  Sparkles,
} from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const modules = [
  { label: '功能墙', route: '/', icon: Library },
  { label: '简历生成', route: '/resume-generation', icon: Sparkles },
  { label: '简历工作台', route: '/resume-library', icon: FileText },
  { label: '个人画像', route: '/knowledge-base', icon: User },
  { label: '投递记录', route: '/applications', icon: Megaphone },
  { label: '模拟面试', route: '/mock-interview', icon: MessagesSquare },
  { label: '求职分析', route: '/workspace', icon: Code2 },
]

const initials = computed(() => (auth.user?.username || '用户').slice(0, 1).toUpperCase())

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.app-nav {
  position: relative;
  z-index: 20;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  background: color-mix(in srgb, var(--color-bg-page) 92%, white);
  border-bottom: var(--border-light);
  backdrop-filter: blur(6px);
  flex-shrink: 0;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  min-width: 0;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--color-text-primary);
  flex-shrink: 0;
}
.brand-mark {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--color-accent-600);
  color: #fff;
}
.brand-name {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  letter-spacing: -0.01em;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 2px;
  overflow-x: auto;
  scrollbar-width: none;
}
.nav-links::-webkit-scrollbar {
  display: none;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: var(--radius-full);
  font-size: var(--text-base);
  font-weight: var(--weight-medium);
  color: var(--color-text-secondary);
  text-decoration: none;
  white-space: nowrap;
  transition: background var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default);
}
.nav-icon {
  opacity: 0.8;
}
.nav-link:hover {
  color: var(--color-text-primary);
  background: var(--color-gray-100);
}
.nav-link.router-link-exact-active {
  color: var(--color-accent-600);
  background: var(--color-accent-100);
}

.nav-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px 4px 4px;
  border: var(--border-light);
  border-radius: var(--radius-full);
  background: var(--color-bg-elevated);
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default);
}
.user-chip:hover {
  border-color: var(--color-gray-300);
  box-shadow: var(--shadow-sm);
}
.avatar {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-full);
  background: var(--color-accent-600);
  color: #fff;
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
}
.user-name {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--color-text-primary);
}
.chev {
  color: var(--color-text-secondary);
}
</style>
