import client from './client'
import type {
  InterviewAnswerResponse,
  InterviewHistoryDetail,
  InterviewHistoryItem,
  InterviewStartParams,
  InterviewStartResponse,
  InterviewState,
} from '../types'

export function startInterview(data: InterviewStartParams) {
  // 生成第一道题会调用 LLM（实测约 50s+），必须放宽单请求超时，否则 30s 默认值会先超时被误判为"后端未启动"
  return client.post<InterviewStartResponse>('/interview/start', data, { timeout: 180000 })
}

export function submitInterviewAnswer(interviewId: string, answer: string) {
  // 每轮提交会执行 evaluate + 下一题/报告（最多多次 LLM），放宽超时对齐后端 AGENT_TIMEOUT 链
  return client.post<InterviewAnswerResponse>(
    `/interview/${interviewId}/answer`,
    { answer },
    { timeout: 300000 },
  )
}

export function getInterviewState(interviewId: string) {
  return client.get<InterviewState>(`/interview/${interviewId}`)
}

export function getInterviewReport(interviewId: string) {
  return client.get<Record<string, unknown>>(`/interview/${interviewId}/report`)
}

export function listInterviewHistory(limit = 50) {
  return client.get<InterviewHistoryItem[]>('/interview/history', { params: { limit } })
}

export function getInterviewHistoryDetail(interviewId: string) {
  return client.get<InterviewHistoryDetail>(`/interview/history/${interviewId}`)
}

export type TtsStyleKey = 'professional' | 'casual' | 'concise'

export function listTtsVoices() {
  return client.get<{ default: string; voices: { id: string; label: string }[] }>(
    '/interview/tts-voices',
  )
}

export function previewTts(body: {
  text?: string
  voice?: string
  speed?: number
  style?: TtsStyleKey | string
}) {
  return client.post<ArrayBuffer>('/interview/tts-preview', body, {
    responseType: 'arraybuffer',
    timeout: 60000,
  })
}

/** 从 arraybuffer 错误响应里解析出后端 detail 文案 */
export async function readTtsPreviewError(err: unknown): Promise<string> {
  const anyErr = err as {
    response?: { data?: ArrayBuffer | Blob | unknown; status?: number }
    message?: string
  }
  const data = anyErr?.response?.data
  try {
    let text = ''
    if (data instanceof ArrayBuffer) {
      text = new TextDecoder().decode(data)
    } else if (typeof Blob !== 'undefined' && data instanceof Blob) {
      text = await data.text()
    } else if (typeof data === 'string') {
      text = data
    }
    if (text) {
      const obj = JSON.parse(text)
      if (obj?.detail) return String(obj.detail)
      if (obj?.message) return String(obj.message)
    }
  } catch {
    /* ignore parse errors */
  }
  if (anyErr?.response?.status === 503) return '语音服务未配置 API Key，请检查 backend/.env'
  if (anyErr?.response?.status === 502) return '语音合成失败，请稍后重试'
  return anyErr?.message || '试听失败，请检查后端语音服务'
}
