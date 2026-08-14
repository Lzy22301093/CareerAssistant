import client from './client'
import type { RegisterRequest, LoginRequest, TokenResponse, Userinfo } from '../types'

export function register(data: RegisterRequest) {
  return client.post<TokenResponse>('/auth/register', data)
}

export function login(data: LoginRequest) {
  return client.post<TokenResponse>('/auth/login', data)
}

export function getMe() {
  return client.get<Userinfo>('/auth/me')
}
