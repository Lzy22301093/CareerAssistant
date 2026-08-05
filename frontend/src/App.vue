<template>
  <el-container style="height: 100vh">
    <el-header>
      <div class="header-content">
        <h1>CareerAssistant</h1>
        <div>
          <el-button text>历史</el-button>
          <el-button text>设置</el-button>
        </div>
      </div>
    </el-header>
    <el-container>
      <el-aside width="350px">
        <ChatPanel />
      </el-aside>
      <el-main>
        <ResultPanel />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import ChatPanel from './components/ChatPanel.vue'
import ResultPanel from './components/ResultPanel.vue'
</script>

<style scoped>
.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.header-content h1 {
  margin: 0;
  font-size: 1.25rem;
}
</style>
