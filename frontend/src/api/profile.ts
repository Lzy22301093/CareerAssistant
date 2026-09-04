import client from './client'
import type {
  CategorySummary,
  ProfileEvidence,
  ProfileItem,
  ProfileItemCreate,
  ProfileItemUpdate,
  ProfileUpdateProposal,
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
