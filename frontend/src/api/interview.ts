import client from './client'
import type {
  InterviewAnswerResponse,
  InterviewStartParams,
  InterviewStartResponse,
  InterviewState,
} from '../types'

export function startInterview(data: InterviewStartParams) {
  return client.post<InterviewStartResponse>('/interview/start', data)
}

export function submitInterviewAnswer(interviewId: string, answer: string) {
  return client.post<InterviewAnswerResponse>(`/interview/${interviewId}/answer`, { answer })
}

export function getInterviewState(interviewId: string) {
  return client.get<InterviewState>(`/interview/${interviewId}`)
}

export function getInterviewReport(interviewId: string) {
  return client.get<Record<string, unknown>>(`/interview/${interviewId}/report`)
}
