import client from './client'
import type {
  SessionCreateResponse,
  SessionDetail,
  SessionListItem,
  SessionStatus,
  UploadResponse,
} from '../types'

export function createSession() {
  return client.post<SessionCreateResponse>('/sessions/')
}

export function listSessions() {
  return client.get<SessionListItem[]>('/sessions/')
}

export function getSession(sessionId: string) {
  return client.get<SessionDetail>(`/sessions/${sessionId}`)
}

export function getSessionStatus(sessionId: string) {
  return client.get<SessionStatus>(`/sessions/${sessionId}/status`)
}

export function deleteSession(sessionId: string) {
  return client.delete(`/sessions/${sessionId}`)
}

export function uploadFile(sessionId: string, file: File, docType?: 'jd' | 'resume') {
  const form = new FormData()
  form.append('file', file)
  if (docType) {
    form.append('doc_type', docType)
  }
  return client.post<UploadResponse>(`/sessions/${sessionId}/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/**
 * 发送消息并通过 SSE 监听后端流式响应。
 * 后端返回 text/event-stream，手动解析 SSE 协议。
 */
export function sendMessageSSE(
  sessionId: string,
  content: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  onError?: (err: Error) => void,
  onDone?: () => void,
): AbortController {
  const controller = new AbortController()

  ;(async () => {
    try {
      const token = localStorage.getItem('token') || ''
      const res = await fetch(`/api/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ content, role: 'user' }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(`HTTP ${res.status}: ${text}`)
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let eventType = ''
        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            const jsonStr = line.slice(5).trim()
            if (jsonStr) {
              try {
                const data = JSON.parse(jsonStr)
                onEvent(eventType || 'message', data)
              } catch {
                // 非 JSON data，忽略
              }
            }
          } else if (line.trim() === '' && eventType) {
            eventType = ''
          }
        }
      }

      onDone?.()
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') return
      onError?.(err as Error)
    }
  })()

  return controller
}
