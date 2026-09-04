<template>
  <div class="app-nav">
    <div class="nav-left">
      <router-link to="/" class="brand">CareerAssistant</router-link>
      <nav class="nav-links">
        <router-link to="/" class="nav-link">功能墙</router-link>
        <router-link to="/resume-library" class="nav-link">简历库</router-link>
        <router-link to="/knowledge-base" class="nav-link">个人知识库</router-link>
        <router-link to="/mock-interview" class="nav-link">模拟面试</router-link>
      </nav>
    </div>
    <div class="nav-right">
      <slot />
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { User } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.app-nav {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  background: var(--color-bg);
  border-bottom: var(--border-light);
  flex-shrink: 0;
}
.nav-left {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}
.brand {
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
  text-decoration: none;
  letter-spacing: -0.01em;
}
.nav-links {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.nav-link {
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--color-text-secondary);
  text-decoration: none;
}
.nav-link:hover {
  color: var(--color-text-primary);
  background: var(--color-gray-50, #f9fafb);
}
.nav-link.router-link-exact-active {
  color: var(--el-color-primary);
  font-weight: var(--weight-medium);
}
.nav-right {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
</style>
