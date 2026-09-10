import client from './client'
import type {
  InterviewAnswerResponse,
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
