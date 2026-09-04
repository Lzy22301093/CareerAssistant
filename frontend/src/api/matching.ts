import client from './client'
import type { JobPostingVO, MatchTaskVO, ResumeLibraryDoc } from '../types'

export interface PostingCreateParams {
  company: string
  title: string
  jd_text: string
}

export interface TaskCreateParams {
  job_posting_id: number
  resume_version_id?: number | null
  page_preference?: 'one_page' | 'two_pages'
}

export const createPosting = (data: PostingCreateParams) =>
  client.post<JobPostingVO>('/matching/postings', data).then((r) => r.data)

export const listPostings = () => client.get<JobPostingVO[]>('/matching/postings').then((r) => r.data)

export const createMatchTask = (data: TaskCreateParams) =>
  client.post<MatchTaskVO>('/matching/tasks', data).then((r) => r.data)

export const listMatchTasks = () => client.get<MatchTaskVO[]>('/matching/tasks').then((r) => r.data)

export const deleteMatchTask = (id: number) => client.delete(`/matching/tasks/${id}`).then((r) => r.data)

// 匹配 = 3 次 LLM 调用（JD 分析 + 差距 + 定向草稿），放宽超时
export const runMatching = (id: number, withDraft = true) =>
  client
    .post<MatchTaskVO>(`/matching/tasks/${id}/run`, { with_draft: withDraft }, { timeout: 480000 })
    .then((r) => r.data)

export const exportMatchDraft = (id: number) =>
  client.post<ResumeLibraryDoc>(`/matching/tasks/${id}/export-draft`, {}).then((r) => r.data)
