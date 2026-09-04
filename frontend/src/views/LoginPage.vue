<template>
  <div class="login-page">
    <!-- 左侧品牌区 -->
    <div class="login-brand">
      <div class="brand-content">
        <div class="brand-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
        </div>
        <h1 class="brand-title">CareerAssistant</h1>
        <p class="brand-subtitle">AI 求职助手</p>
        <p class="brand-desc">
          贴入目标岗位 JD，上传简历，<br/>
          获得差距分析、优化简历和面试准备。
        </p>

        <!-- CSS 装饰线条 -->
        <div class="brand-decoration">
          <div class="deco-line deco-line--1"></div>
          <div class="deco-line deco-line--2"></div>
          <div class="deco-line deco-line--3"></div>
          <div class="deco-line deco-line--4"></div>
          <div class="deco-line deco-line--5"></div>
        </div>
      </div>
    </div>

    <!-- 右侧表单区 -->
    <div class="login-form-area">
      <div class="login-form-wrapper">
        <h2 class="form-title">登录</h2>
        <p class="form-subtitle">欢迎回来，请输入你的账号信息</p>

        <!-- 内联错误提示 -->
        <div v-if="errorMsg" class="form-error">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span>{{ errorMsg }}</span>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @submit.prevent="handleLogin"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              size="large"
              @input="errorMsg = ''"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              show-password
              size="large"
              @input="errorMsg = ''"
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              :loading="loading"
              size="large"
              style="width: 100%"
              @click="handleLogin"
            >
              登录
            </el-button>
          </el-form-item>
        </el-form>

        <div class="login-footer">
          还没有账号？<router-link to="/register">立即注册</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const errorMsg = ref('')

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  errorMsg.value = ''
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await auth.login({ username: form.username, password: form.password })
    router.push('/')
  } catch (err: unknown) {
    errorMsg.value = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  min-height: 100vh;
  background: var(--color-gray-50);
}

/* ── 左侧品牌区 ── */
.login-brand {
  width: 40%;
  background: var(--color-gray-900);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-12);
  position: relative;
  overflow: hidden;
}

.brand-content {
  position: relative;
  z-index: 1;
  color: var(--color-gray-50);
}

.brand-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-6);
  color: var(--color-accent-400);
}

.brand-title {
  font-family: var(--font-sans);
  font-size: var(--text-2xl);
  font-weight: var(--font-weight-semibold);
  margin: 0 0 var(--space-2);
  letter-spacing: -0.02em;
}

.brand-subtitle {
  font-size: var(--text-sm);
  color: var(--color-gray-400);
  margin: 0 0 var(--space-8);
  font-weight: var(--font-weight-medium);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.brand-desc {
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  color: var(--color-gray-300);
  margin: 0;
  max-width: 280px;
}

/* CSS 装饰线条 */
.brand-decoration {
  position: absolute;
  bottom: -40px;
  right: -40px;
  width: 300px;
  height: 300px;
  opacity: 0.06;
}

.deco-line {
  position: absolute;
  background: white;
  border-radius: 1px;
}

.deco-line--1 {
  width: 180px;
  height: 2px;
  top: 40px;
  left: 20px;
}

.deco-line--2 {
  width: 140px;
  height: 2px;
  top: 60px;
  left: 20px;
}

.deco-line--3 {
  width: 160px;
  height: 2px;
  top: 80px;
  left: 20px;
}

.deco-line--4 {
  width: 100px;
  height: 2px;
  top: 100px;
  left: 20px;
}

.deco-line--5 {
  width: 120px;
  height: 2px;
  top: 120px;
  left: 20px;
}

/* ── 右侧表单区 ── */
.login-form-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-12);
  background: var(--color-bg);
}

.login-form-wrapper {
  width: 100%;
  max-width: 380px;
}

.form-title {
  font-family: var(--font-sans);
  font-size: var(--text-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--space-2);
}

.form-subtitle {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin: 0 0 var(--space-8);
}

/* ── 内联错误 ── */
.form-error {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-6);
  background: var(--color-danger-light);
  border-left: 3px solid var(--color-danger);
  border-radius: var(--radius-sm);
  color: var(--color-danger);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
}

.form-error svg {
  flex-shrink: 0;
  margin-top: 1px;
}

/* ── 底部链接 ── */
.login-footer {
  text-align: center;
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  margin-top: var(--space-6);
}

.login-footer a {
  color: var(--color-accent-600);
  text-decoration: none;
  font-weight: var(--font-weight-medium);
}

.login-footer a:hover {
  text-decoration: underline;
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .login-page {
    flex-direction: column;
  }

  .login-brand {
    width: 100%;
    padding: var(--space-8) var(--space-6);
    min-height: auto;
  }

  .brand-decoration {
    display: none;
  }

  .login-form-area {
    padding: var(--space-8) var(--space-6);
  }
}
</style>
