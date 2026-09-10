<template>
  <div class="login-page">
    <!-- 左侧品牌区：暖米纸感 + 陶土橙 -->
    <div class="login-brand">
      <div class="brand-orb brand-orb--1" aria-hidden="true"></div>
      <div class="brand-orb brand-orb--2" aria-hidden="true"></div>

      <div class="brand-content">
        <div class="brand-icon">
          <Sparkles :size="26" />
        </div>
        <h1 class="brand-title">CareerAssistant</h1>
        <p class="brand-subtitle">AI 求职助手</p>
        <p class="brand-desc">
          贴入目标岗位 JD，上传简历，<br />
          获得差距分析、优化简历与面试准备。
        </p>

        <ul class="brand-features">
          <li><Check :size="15" /> 岗位分析 · 差距诊断</li>
          <li><Check :size="15" /> 简历优化 · 高保真导出</li>
          <li><Check :size="15" /> AI 模拟面试 · 语音对话</li>
        </ul>
      </div>

      <!-- 装饰：简历卡片剪影 -->
      <div class="brand-resume" aria-hidden="true">
        <div class="resume-accent"></div>
        <div class="resume-line resume-line--wide"></div>
        <div class="resume-line"></div>
        <div class="resume-line resume-line--short"></div>
        <div class="resume-gap"></div>
        <div class="resume-line resume-line--wide"></div>
        <div class="resume-line resume-line--short"></div>
      </div>
    </div>

    <!-- 右侧表单区：暖白卡 -->
    <div class="login-form-area">
      <div class="login-form-wrapper">
        <h2 class="form-title">登录</h2>
        <p class="form-subtitle">欢迎回来，请输入你的账号信息</p>

        <!-- 内联错误 -->
        <div v-if="errorMsg" class="form-error">
          <AlertCircle :size="16" />
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
              class="submit-btn"
              type="primary"
              :loading="loading"
              size="large"
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
import { Sparkles, Check, AlertCircle } from 'lucide-vue-next'
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
  background: var(--color-bg-page);
}

/* ── 左侧品牌区 ── */
.login-brand {
  width: 46%;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-12);
  background:
    radial-gradient(circle at 82% 16%, color-mix(in srgb, var(--color-accent-500) 18%, transparent), transparent 46%),
    radial-gradient(circle at 12% 92%, color-mix(in srgb, var(--color-accent-200) 32%, transparent), transparent 42%),
    linear-gradient(160deg, var(--color-bg) 0%, var(--color-bg-page) 52%, var(--color-accent-50) 100%);
}

/* 纸感装饰圆斑 */
.brand-orb {
  position: absolute;
  border-radius: var(--radius-full);
  filter: blur(2px);
  pointer-events: none;
}

.brand-orb--1 {
  width: 340px;
  height: 340px;
  top: -120px;
  right: -80px;
  background: color-mix(in srgb, var(--color-accent-200) 45%, transparent);
  opacity: 0.5;
}

.brand-orb--2 {
  width: 260px;
  height: 260px;
  bottom: -110px;
  left: -90px;
  background: color-mix(in srgb, var(--color-accent-100) 55%, transparent);
  opacity: 0.6;
}

.brand-content {
  position: relative;
  z-index: 1;
  max-width: 360px;
  color: var(--color-text-primary);
}

.brand-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--color-accent-600) 12%, var(--color-bg));
  color: var(--color-accent-600);
  border: var(--border-light);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-6);
  box-shadow: var(--shadow-card);
}

.brand-title {
  font-family: var(--font-display);
  font-size: var(--text-3xl);
  font-weight: var(--font-weight-semibold);
  margin: 0 0 var(--space-2);
  letter-spacing: -0.02em;
  color: var(--color-gray-900);
}

.brand-subtitle {
  font-size: var(--text-md);
  color: var(--color-accent-600);
  margin: 0 0 var(--space-8);
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.04em;
}

.brand-desc {
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  color: var(--color-text-secondary);
  margin: 0 0 var(--space-8);
}

.brand-features {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.brand-features li {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.brand-features li svg {
  color: var(--color-accent-600);
  flex-shrink: 0;
}

/* 装饰：简历卡片剪影 */
.brand-resume {
  position: absolute;
  right: -40px;
  bottom: -46px;
  width: 220px;
  height: 260px;
  background: color-mix(in srgb, var(--color-bg) 78%, transparent);
  border: var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: var(--space-5) var(--space-5);
  transform: rotate(-7deg);
  opacity: 0.55;
}

.resume-accent {
  width: 4px;
  height: 100%;
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  margin: var(--space-5) 0;
  border-radius: var(--radius-full);
  background: linear-gradient(
    180deg,
    var(--color-accent-400),
    var(--color-accent-600)
  );
}

.resume-line {
  width: 70%;
  height: 8px;
  margin-bottom: var(--space-3);
  border-radius: var(--radius-full);
  background: color-mix(in srgb, var(--color-gray-300) 60%, transparent);
}

.resume-line--wide {
  width: 96%;
}

.resume-line--short {
  width: 46%;
}

.resume-gap {
  height: var(--space-4);
}

/* ── 右侧表单区 ── */
.login-form-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-12);
  background: var(--color-bg-page);
}

.login-form-wrapper {
  width: 100%;
  max-width: 420px;
  background: var(--color-bg-elevated);
  border: var(--border-light);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-card);
  padding: var(--space-10);
}

.form-title {
  font-family: var(--font-display);
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

/* 焦点环：accent 200 外圈 + accent 600 内圈 */
.login-form-wrapper :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1px var(--color-accent-600) inset,
    0 0 0 4px color-mix(in srgb, var(--color-accent-600) 14%, transparent);
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

.submit-btn {
  width: 100%;
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
    padding: var(--space-10) var(--space-6);
    min-height: auto;
  }

  .brand-orb,
  .brand-resume {
    display: none;
  }

  .login-form-area {
    padding: var(--space-8) var(--space-6);
  }

  .login-form-wrapper {
    padding: var(--space-8) var(--space-6);
    box-shadow: none;
  }
}
</style>
