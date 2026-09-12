import client from './client'
import type {
  ExperienceDraft,
  ResumeDraftInfo,
  ResumeLibraryDoc,
  ResumePhotoInfo,
  WizardExperience,
  WizardGeneratePayload,
  WizardGenerateResult,
} from '../types'

// 简历生成区（8 步向导）——契约见 docs/resume-generation-contract.md

export function saveDraft(step: number, data: Record<string, unknown>) {
  return client.post<ResumeDraftInfo>('/resume-generation/draft', { step, data })
}

export function loadDraft() {
  return client.get<ResumeDraftInfo>('/resume-generation/draft')
}

export function clearDraft() {
  return client.delete('/resume-generation/draft')
}

export function starStructuring(experiences: WizardExperience[]) {
  // 调 LLM，放宽超时
  return client.post<{ items: WizardExperience[] }>(
    '/resume-generation/star',
    {
      experiences: experiences.map((e) => ({
        exp_type: e.exp_type,
        company: e.company,
        title: e.title,
        duration: e.duration,
        duty: e.duty,
        achievement: e.achievement,
      })),
    },
    { timeout: 180000 },
  )
}

/** 03：自然语言描述 → 结构化+润色经历列表 */
export function structureExperiences(text: string, directions: string[] = []) {
  return client.post<{ items: ExperienceDraft[] }>(
    '/resume-generation/experiences/structure',
    { text, directions },
    { timeout: 180000 },
  )
}

/** 03：无经历时按画像/方向 AI 生成经历草稿 */
export function generateExperiences(directions: string[] = [], count = 2) {
  return client.post<{ items: ExperienceDraft[] }>(
    '/resume-generation/experiences/generate',
    { directions, count },
    { timeout: 180000 },
  )
}

export function uploadPhotoFile(file: File) {
  const form = new FormData()
  form.append('file', file)
  return client.post<ResumePhotoInfo>('/resume-generation/photo', form)
}

export function getPhotoInfo() {
  return client.get<ResumePhotoInfo | null>('/resume-generation/photo')
}

/** 带鉴权拉取证件照二进制，供 <img> 预览（img src 不会带 Bearer） */
export async function fetchPhotoBlob(photoId: number): Promise<Blob> {
  const res = await client.get<Blob>(`/resume-generation/photo/file?id=${photoId}`, {
    responseType: 'blob',
  })
  return res.data
}

export function generateResume(payload: WizardGeneratePayload) {
  // 生成含 LLM 润色（可能多次调用），放宽超时
  return client.post<WizardGenerateResult>('/resume-generation/generate', payload, { timeout: 300000 })
}

// 简历库导入：上传文件（PDF/DOCX/TXT/MD）
export function importUploadResume(title: string, file: File) {
  const form = new FormData()
  form.append('title', title)
  form.append('file', file)
  return client.post<ResumeLibraryDoc>('/resumes/import-upload', form, { timeout: 120000 })
}

// 导出：把简历内容下载为文件（Word/HTML/Markdown/JSON）
export type ExportFormat = 'docx' | 'html' | 'md' | 'json'

export async function exportResume(
  content: { sections: { title: string; content: string }[]; raw_text: string },
  title: string,
  format: ExportFormat,
  photoId?: number | null,
) {
  const res = await client.post(
    '/resume-generation/export',
    {
      title,
      content,
      format,
      photo_id: photoId || null,
    },
    { responseType: 'blob', timeout: 120000 },
  )
  return res.data as Blob
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
