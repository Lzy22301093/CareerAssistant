import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginPage.vue'),
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/RegisterPage.vue'),
    },
    {
      path: '/',
      name: 'feature-wall',
      component: () => import('../views/FeatureWallView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/workspace',
      name: 'workspace',
      component: () => import('../views/HomePage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/resume-library',
      name: 'resume-library',
      component: () => import('../views/ResumeLibraryView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/knowledge-base',
      name: 'knowledge-base',
      component: () => import('../views/KnowledgeBaseView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/mock-interview',
      name: 'mock-interview',
      component: () => import('../views/MockInterviewView.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

// 路由守卫
router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    return { name: 'login' }
  }
  if ((to.name === 'login' || to.name === 'register') && token) {
    return { name: 'feature-wall' }
  }
  return true
})

export default router
