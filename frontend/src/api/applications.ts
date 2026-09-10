import client from './client'
import type {
  JobApplication,
  JobApplicationCreate,
  JobApplicationSummary,
  JobApplicationUpdate,
} from '../types'

export function listApplications(q?: string, status?: string, result?: string) {
  return client.get<JobApplication[]>('/applications', { params: { q, status, result } })
}

export function getApplicationSummary() {
  return client.get<JobApplicationSummary>('/applications/summary')
}

export function createApplication(data: JobApplicationCreate) {
  return client.post<JobApplication>('/applications', data)
}

export function updateApplication(id: number, data: JobApplicationUpdate) {
  return client.patch<JobApplication>(`/applications/${id}`, data)
}

export function deleteApplication(id: number) {
  return client.delete(`/applications/${id}`)
}
