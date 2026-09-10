import client from './client'
import type {
  CategorySummary,
  DirectionCandidate,
  ProfileEvidence,
  ProfileFormData,
  ProfileFormSave,
  ProfileItem,
  ProfileItemCreate,
  ProfileItemUpdate,
  ProfileUpdateProposal,
  SoftInfo,
} from '../types'

export function listProfileItems(category?: string, status?: string) {
  return client.get<ProfileItem[]>('/profile/items', { params: { category, status } })
}

export function getProfileItem(id: number) {
  return client.get<ProfileItem>(`/profile/items/${id}`)
}

export function createProfileItem(data: ProfileItemCreate) {
  return client.post<ProfileItem>('/profile/items', data)
}

export function updateProfileItem(id: number, data: ProfileItemUpdate) {
  return client.patch<ProfileItem>(`/profile/items/${id}`, data)
}

export function changeProfileStatus(id: number, status: string) {
  return client.post<ProfileItem>(`/profile/items/${id}/status`, { status })
}

export function deleteProfileItem(id: number) {
  return client.delete(`/profile/items/${id}`)
}

export function addProfileEvidence(
  id: number,
  data: { source_type: string; quote?: string; source_id?: string; verified_by_user?: boolean },
) {
  return client.post<ProfileEvidence>(`/profile/items/${id}/evidences`, data)
}

export function getCategorySummary() {
  return client.get<CategorySummary[]>('/profile/categories')
}

export function listProposals(reportId: string) {
  return client.get<ProfileUpdateProposal[]>(`/profile/proposals/${reportId}`)
}

export function actOnProposal(proposalId: number, action: string, after_value?: string) {
  return client.post<ProfileUpdateProposal>(`/profile/proposals/${proposalId}/action`, { action, after_value })
}

// 画像方向推荐（阶段3 指令3-1）
export function recommendDirections() {
  // 生成候选会调用 LLM（较慢），放宽超时
  return client.post<DirectionCandidate[]>('/profile/directions/recommend', null, { timeout: 180000 })
}

export function confirmDirections(selected: DirectionCandidate[]) {
  return client.post<ProfileItem[]>('/profile/directions/confirm', { selected })
}

// 软性信息（阶段3 指令3-2）
export function generateSoftInfo() {
  // 生成会调用 LLM（较慢），放宽超时
  return client.post<SoftInfo>('/profile/soft-info/generate', null, { timeout: 180000 })
}

export function saveSoftInfo(data: { personality: string; vision: string; disinterested: string; self_eval: string }) {
  return client.post<ProfileItem[]>('/profile/soft-info/save', data)
}

// 结构化画像表单（知识库 分阶段向导，阶段3）
export function getProfileForm() {
  return client.get<ProfileFormData>('/profile/form')
}

export function saveProfileForm(data: ProfileFormSave) {
  return client.post<ProfileFormData>('/profile/form', data)
}
