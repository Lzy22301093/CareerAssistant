<template>
  <el-container style="height: 100vh">
    <el-header>
      <div class="header-content">
        <h1>CareerAssistant</h1>
        <div class="header-actions">
          <el-button text @click="showHistory = true">
            <el-icon><Clock /></el-icon>历史
          </el-button>
          <el-button text @click="showSettings = true">
            <el-icon><Setting /></el-icon>设置
          </el-button>
          <el-dropdown @command="handleCommand">
            <el-button text>
              <el-icon><User /></el-icon>{{ auth.user?.username || '用户' }}
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </el-header>
    <el-container>
      <el-aside width="400px">
        <ChatPanel />
      </el-aside>
      <el-main>
        <ResultPanel />
      </el-main>
    </el-container>

    <HistoryDrawer v-model="showHistory" />
    <SettingsDrawer v-model="showSettings" />
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Clock, Setting, User } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import ChatPanel from '../components/ChatPanel.vue'
import ResultPanel from '../components/ResultPanel.vue'
import HistoryDrawer from '../components/HistoryDrawer.vue'
import SettingsDrawer from '../components/SettingsDrawer.vue'

const router = useRouter()
const auth = useAuthStore()

const showHistory = ref(false)
const showSettings = ref(false)

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.el-header {
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.header-content h1 {
  margin: 0;
  font-size: 1.25rem;
  color: #303133;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.el-aside {
  border-right: 1px solid #e4e7ed;
  background: #fff;
}

.el-main {
  padding: 0;
  background: #f5f7fa;
}
</style>
