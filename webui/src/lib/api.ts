import axios from 'axios'
import type { CrawlerConfig } from '@/types/crawler'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

/** 从 axios 错误里取出给人看的一句话:后端统一回 {detail: string};网络错误/超时单独说明。 */
export function errMsg(err: unknown, fallback = '请求失败'): string {
  const e = err as { response?: { status?: number; data?: { detail?: unknown } }; code?: string; message?: string }
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => (d as { msg?: string })?.msg || String(d)).join(';')
  }
  if (e?.code === 'ECONNABORTED') return '请求超时,稍后再试'
  if (!e?.response) return '连不上服务器,检查网络后重试'
  return `${fallback}(HTTP ${e.response.status})`
}

// 未登录(401)回调:App 注册,收到即弹登录页
let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn
}

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const url: string = error?.config?.url || ''
    // 登录接口自己的 401 不触发全局跳登录(交给登录页显示错误)
    if (error?.response?.status === 401 && !url.includes('/auth/login')) {
      onUnauthorized?.()
    }
    return Promise.reject(error)
  }
)

// Types
export type { CrawlerConfig }

export interface CrawlerStatus {
  status: 'idle' | 'running' | 'stopping' | 'error'
  platform: string | null
  crawler_type: string | null
  started_at: string | null
  error_message: string | null
}

export interface LogEntry {
  id: number
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'success' | 'debug'
  message: string
}

export interface DataFile {
  name: string
  path: string
  size: number
  modified_at: number
  record_count: number | null
  type: string
}

export interface FilePreviewResponse {
  data: Record<string, unknown>[]
  total: number
  columns?: string[]
}

export interface Platform {
  value: string
  label: string
  icon: string
}

export interface ConfigOption {
  value: string
  label: string
}

// API functions
export const crawlerApi = {
  start: (config: CrawlerConfig) => api.post('/crawler/start', config),
  stop: () => api.post('/crawler/stop'),
  getStatus: () => api.get<CrawlerStatus>('/crawler/status'),
  getLogs: (limit = 100) => api.get<{ logs: LogEntry[] }>('/crawler/logs', { params: { limit } }),
}

export const dataApi = {
  getFiles: (platform?: string, fileType?: string) =>
    api.get<{ files: DataFile[] }>('/data/files', { params: { platform, file_type: fileType } }),
  getFileContent: (path: string, limit = 100) =>
    api.get<FilePreviewResponse>('/data/files/' + path, { params: { preview: true, limit } }),
  getStats: () => api.get('/data/stats'),
  getDownloadUrl: (path: string) => `/api/data/download/${path}`,
}

export const configApi = {
  getPlatforms: () => api.get<{ platforms: Platform[] }>('/config/platforms'),
  getOptions: () =>
    api.get<{
      login_types: ConfigOption[]
      crawler_types: ConfigOption[]
      save_options: ConfigOption[]
    }>('/config/options'),
}

export interface EnvCheckResult {
  success: boolean
  message: string
  output?: string
  error?: string
}

export const envApi = {
  check: () => api.get<EnvCheckResult>('/env/check'),
}

export const authApi = {
  login: (username: string, password: string) =>
    api.post<{ username: string }>('/auth/login', { username, password }),
  logout: () => api.post('/auth/logout'),
  me: () => api.get<{ username: string; cdp: boolean }>('/auth/me'),
}

export default api
