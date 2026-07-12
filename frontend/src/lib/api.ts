import axios from 'axios'
import type { AdminUserSummary, AuthUser, DocumentDetail, DocumentSummary } from './types'

export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

let refreshPromise: Promise<void> | null = null

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const isAuthRoute = originalRequest?.url?.startsWith('/auth/')

    if (error.response?.status === 401 && !originalRequest._retry && !isAuthRoute) {
      originalRequest._retry = true
      try {
        refreshPromise ??= api
          .post('/auth/refresh')
          .then(() => undefined)
          .finally(() => {
            refreshPromise = null
          })
        await refreshPromise
        return api(originalRequest)
      } catch {
        // fall through to the original rejection
      }
    }

    return Promise.reject(error)
  },
)

export const authApi = {
  async signup(email: string, password: string, fullName: string): Promise<AuthUser> {
    const { data } = await api.post<AuthUser>('/auth/signup', {
      email,
      password,
      full_name: fullName,
    })
    return data
  },

  async login(email: string, password: string): Promise<AuthUser> {
    const { data } = await api.post<AuthUser>('/auth/login', { email, password })
    return data
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout')
  },

  async me(): Promise<AuthUser> {
    const { data } = await api.get<AuthUser>('/auth/me')
    return data
  },
}

export async function uploadDocument(file: File): Promise<DocumentDetail> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post<DocumentDetail>('/documents', formData)
  return data
}

export async function listDocuments(): Promise<DocumentSummary[]> {
  const { data } = await api.get<DocumentSummary[]>('/documents')
  return data
}

export async function getDocument(id: string): Promise<DocumentDetail> {
  const { data } = await api.get<DocumentDetail>(`/documents/${id}`)
  return data
}

export async function deleteDocument(id: string): Promise<void> {
  await api.delete(`/documents/${id}`)
}

export function documentFileUrl(id: string): string {
  return `/api/documents/${id}/file`
}

export const adminApi = {
  async listUsers(): Promise<AdminUserSummary[]> {
    const { data } = await api.get<AdminUserSummary[]>('/admin/users')
    return data
  },
}
