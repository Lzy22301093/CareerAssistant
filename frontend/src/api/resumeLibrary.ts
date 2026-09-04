import client from './client'
import type { ResumeLibraryDoc, ResumeLibrarySection, ResumeLibraryVersion, RewriteResult } from '../types'

export interface ResumeDocCreateParams {
  title: string
  source?: string
  notes?: string
}

export interface ResumeVersionCreateParams {
  content: Record<string, unknown>
  render_config?: Record<string, unknown>
}

export interface RewriteParams {
  instruction?: string
  conversation_history?: { role: string; content: string }[]
  jd_analysis?: Record<string, unknown> | null
}

export const listResumeDocs = (includeDeleted = false) =>
  client.get<ResumeLibraryDoc[]>('/resumes', { params: { include_deleted: includeDeleted } }).then((r) => r.data)

export const listDeletedResumes = () =>
  client.get<ResumeLibraryDoc[]>('/resumes/recycle-bin').then((r) => r.data)

export const createResumeDoc = (data: ResumeDocCreateParams) =>
  client.post<ResumeLibraryDoc>('/resumes', data).then((r) => r.data)

export const getResumeDoc = (id: number) =>
  client.get<ResumeLibraryDoc>(`/resumes/${id}`).then((r) => r.data)

export const updateResumeDoc = (id: number, data: { title?: string; notes?: string }) =>
  client.patch<ResumeLibraryDoc>(`/resumes/${id}`, data).then((r) => r.data)

export const deleteResumeDoc = (id: number, purge = false) =>
  client.delete(`/resumes/${id}`, { params: { purge } }).then((r) => r.data)

export const restoreResumeDoc = (id: number) =>
  client.post<ResumeLibraryDoc>(`/resumes/${id}/restore`).then((r) => r.data)

export const addResumeVersion = (docId: number, data: ResumeVersionCreateParams) =>
  client.post<ResumeLibraryVersion>(`/resumes/${docId}/versions`, data).then((r) => r.data)

export const listResumeVersions = (docId: number) =>
  client.get<ResumeLibraryVersion[]>(`/resumes/${docId}/versions`).then((r) => r.data)

export const rollbackResumeVersion = (versionId: number) =>
  client.post<ResumeLibraryDoc>(`/resumes/versions/${versionId}/rollback`).then((r) => r.data)

export const updateResumeSection = (sectionId: number, data: Partial<ResumeLibrarySection>) =>
  client.patch<ResumeLibrarySection>(`/resumes/sections/${sectionId}`, data).then((r) => r.data)

// 区域改写走 LLM，放宽单请求超时（与后端 AGENT_TIMEOUT=120s 对齐）
export const rewriteSection = (sectionId: number, data: RewriteParams) =>
  client
    .post<RewriteResult>(`/resumes/sections/${sectionId}/rewrite`, data, { timeout: 180000 })
    .then((r) => r.data)

export const adoptSectionRewrite = (versionId: number, sectionId: number, rewrite: string) =>
  client
    .post<ResumeLibraryVersion>(`/resumes/versions/${versionId}/adopt-rewrite`, {
      section_id: sectionId,
      rewrite,
    })
    .then((r) => r.data)

export const importResumeFromSession = (sessionId: string) =>
  client.post<ResumeLibraryDoc>('/resumes/import-from-session', { session_id: sessionId }).then((r) => r.data)
