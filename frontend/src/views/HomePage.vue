<template>
  <div class="app-layout">
    <AppNav>
      <el-button text @click="showHistory = true">
        <Clock :size="16" />历史
      </el-button>
      <el-button text @click="showSettings = true">
        <Settings :size="16" />设置
      </el-button>
    </AppNav>
    <div class="app-body">
      <aside class="app-sidebar">
        <ChatPanel />
      </aside>
      <main class="app-main">
        <ResultPanel />
      </main>
    </div>

    <HistoryDrawer v-model="showHistory" />
    <SettingsDrawer v-model="showSettings" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Clock, Settings } from 'lucide-vue-next'
import AppNav from '../components/AppNav.vue'
import ChatPanel from '../components/ChatPanel.vue'
import ResultPanel from '../components/ResultPanel.vue'
import HistoryDrawer from '../components/HistoryDrawer.vue'
import SettingsDrawer from '../components/SettingsDrawer.vue'

const showHistory = ref(false)
const showSettings = ref(false)
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.app-sidebar {
  flex-shrink: 0;
  width: 380px;
  border-right: var(--border-light);
  background: var(--color-bg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.app-main {
  flex: 1;
  min-width: 0;
  padding: 0;
  background: var(--color-bg-page);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
