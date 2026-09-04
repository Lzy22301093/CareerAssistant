import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  listProfileItems,
  createProfileItem,
  updateProfileItem,
  changeProfileStatus,
  deleteProfileItem,
  getCategorySummary,
} from '../api/profile'
import type {
  CategorySummary,
  ProfileCategory,
  ProfileItem,
  ProfileItemCreate,
  ProfileItemUpdate,
  ProfileStatus,
} from '../types'

export const useKnowledgeBaseStore = defineStore('knowledgeBase', () => {
  const items = ref<ProfileItem[]>([])
  const categories = ref<CategorySummary[]>([])
  const loading = ref(false)
  const error = ref('')

  const CATEGORY_LABELS: Record<ProfileCategory, string> = {
    basic_info: '基本信息',
    education: '教育经历',
    experience: '项目经历',
    skill: '专业技能',
    target: '目标岗位',
    soft: '自我评价',
    interview_feedback: '面试反馈',
  }

  async function fetchItems(category?: string, status?: string) {
    loading.value = true
    error.value = ''
    try {
      const res = await listProfileItems(category, status)
      items.value = res.data
    } catch (e) {
      error.value = '加载画像失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchCategories() {
    try {
      const res = await getCategorySummary()
      categories.value = res.data
    } catch {
      categories.value = []
    }
  }

  async function add(data: ProfileItemCreate) {
    const res = await createProfileItem(data)
    await Promise.all([fetchItems(), fetchCategories()])
    return res.data
  }

  async function update(id: number, data: ProfileItemUpdate) {
    const res = await updateProfileItem(id, data)
    await fetchItems()
    return res.data
  }

  async function setStatus(id: number, status: ProfileStatus) {
    const res = await changeProfileStatus(id, status)
    await Promise.all([fetchItems(), fetchCategories()])
    return res.data
  }

  async function remove(id: number) {
    await deleteProfileItem(id)
    await Promise.all([fetchItems(), fetchCategories()])
  }

  return {
    items,
    categories,
    loading,
    error,
    CATEGORY_LABELS,
    fetchItems,
    fetchCategories,
    add,
    update,
    setStatus,
    remove,
  }
})
