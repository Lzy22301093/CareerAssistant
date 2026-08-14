import client from './client'
import type { UserPreferences, PreferenceUpdateRequest } from '../types'

export function getPreferences() {
  return client.get<UserPreferences>('/preferences/')
}

export function updatePreferences(data: PreferenceUpdateRequest) {
  return client.put<UserPreferences>('/preferences/', data)
}

export function getTemplatePreference() {
  return client.get<{ template: string }>('/preferences/template')
}
