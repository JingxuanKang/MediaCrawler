import { create } from 'zustand'
import type { LogEntry, CrawlerConfig } from '@/types/crawler'

interface CrawlerState {
  // Status
  status: 'idle' | 'running' | 'stopping' | 'error'
  platform: string | null
  crawlerType: string | null
  startedAt: string | null
  errorMessage: string | null
  wsConnected: boolean  // 日志 WebSocket 是否连上;没连上时改用接口轮询

  // Logs
  logs: LogEntry[]
  clearedAfterLogId: number | null  // 清除日志后，只显示 id 大于此值的日志
  clearedRunKey: string | null      // 清除标记属于哪一轮任务(started_at);后端每轮日志 id 从 1 重新计

  // Config
  config: CrawlerConfig

  // Actions
  setStatus: (status: CrawlerState['status']) => void
  setRunningInfo: (platform: string | null, crawlerType: string | null, startedAt: string | null) => void
  setErrorMessage: (msg: string | null) => void
  setWsConnected: (v: boolean) => void
  addLog: (log: LogEntry) => void
  setLogs: (logs: LogEntry[]) => void
  clearLogs: () => void
  resetLogsForNewRun: () => void
  restoreLogs: () => void
  updateConfig: (config: Partial<CrawlerConfig>) => void
  reset: () => void
}

// 持久化相关的 localStorage key
const CLEARED_LOG_ID_KEY = 'mediacrawler_cleared_log_id'
const CLEARED_RUN_KEY = 'mediacrawler_cleared_run'
export const MAX_LOGS = 500  // 与后端 MAX_LOGS 一致

// 从 localStorage 读取清除标记
function getClearedLogIdFromStorage(): number | null {
  const stored = localStorage.getItem(CLEARED_LOG_ID_KEY)
  if (stored === null) return null
  const value = parseInt(stored, 10)
  return isNaN(value) ? null : value
}

// 保存清除标记到 localStorage
function saveClearedLogIdToStorage(id: number | null, runKey: string | null = null): void {
  if (id === null) {
    localStorage.removeItem(CLEARED_LOG_ID_KEY)
    localStorage.removeItem(CLEARED_RUN_KEY)
  } else {
    localStorage.setItem(CLEARED_LOG_ID_KEY, id.toString())
    if (runKey) localStorage.setItem(CLEARED_RUN_KEY, runKey)
    else localStorage.removeItem(CLEARED_RUN_KEY)
  }
}

const defaultConfig: CrawlerConfig = {
  platform: 'bili',
  login_type: 'qrcode',
  crawler_type: 'search',
  keywords: '',
  specified_ids: '',
  creator_ids: '',
  start_page: 1,
  enable_comments: true,
  enable_sub_comments: false,
  save_option: 'json',
  cookies: '',
  headless: false,
  account: '',
  max_notes_count: 10,
  crawl_interval: 3,
}

export const useCrawlerStore = create<CrawlerState>((set, get) => ({
  status: 'idle',
  platform: null,
  crawlerType: null,
  startedAt: null,
  errorMessage: null,
  wsConnected: false,
  logs: [],
  clearedAfterLogId: getClearedLogIdFromStorage(), // 从 localStorage 初始化
  clearedRunKey: localStorage.getItem(CLEARED_RUN_KEY),
  config: defaultConfig,

  setStatus: (status) => {
    set({ status })
  },

  resetLogsForNewRun: () => {
    // 新一轮任务:后端日志 id 从 1 重新计,旧的清除标记必须作废,否则新日志会被过滤掉
    set({ logs: [], clearedAfterLogId: null, clearedRunKey: null, errorMessage: null })
    saveClearedLogIdToStorage(null)
  },

  setRunningInfo: (platform, crawlerType, startedAt) => {
    set({ platform, crawlerType, startedAt })
    // 清除标记只对它所属的那一轮有效;换了一轮(started_at 变了)才作废。
    // 每次轮询都清会让"清除"在 2 秒后失效、刷新后日志又全回来。
    const { clearedAfterLogId, clearedRunKey } = get()
    if (clearedAfterLogId !== null && startedAt !== null && clearedRunKey !== startedAt) {
      set({ clearedAfterLogId: null, clearedRunKey: null })
      saveClearedLogIdToStorage(null)
    }
  },

  setWsConnected: (v) => {
    if (get().wsConnected !== v) set({ wsConnected: v })
  },

  setErrorMessage: (msg) => {
    if (get().errorMessage !== msg) set({ errorMessage: msg })
  },

  addLog: (log) => {
    const { clearedAfterLogId, logs } = get()
    // 如果有清除标记，过滤掉 id 小于等于该标记的日志
    if (clearedAfterLogId !== null && log.id <= clearedAfterLogId) {
      return
    }
    // 防止 WebSocket 重连/重复连接导致的重复日志
    if (logs.length > 0 && logs[logs.length - 1].id === log.id) {
      return
    }
    if (logs.some((existing) => existing.id === log.id)) {
      return
    }
    set((state) => ({
      logs: [...state.logs.slice(-(MAX_LOGS - 1)), log],
    }))
  },

  setLogs: (logs) => {
    const { clearedAfterLogId } = get()
    // 如果有清除标记，过滤掉 id 小于等于该标记的日志
    const filteredLogs = clearedAfterLogId !== null
      ? logs.filter((log) => log.id > clearedAfterLogId)
      : logs
    // 合并而不是覆盖:接口快照可能比 WebSocket 已推来的新日志旧
    const maxId = filteredLogs.length > 0 ? filteredLogs[filteredLogs.length - 1].id : 0
    const newer = get().logs.filter((log) => log.id > maxId)
    set({ logs: [...filteredLogs, ...newer].slice(-MAX_LOGS) })
  },

  clearLogs: () => {
    const { logs } = get()
    // 记录当前最大的 log id，清除后只显示比这个 id 大的日志
    const maxLogId = logs.length > 0 ? Math.max(...logs.map(l => l.id)) : 0
    const runKey = get().startedAt
    set({ logs: [], clearedAfterLogId: maxLogId, clearedRunKey: runKey })
    // 持久化到 localStorage
    saveClearedLogIdToStorage(maxLogId, runKey)
  },

  restoreLogs: () => {
    // 清除清除标记，这样下次重新加载日志时就会显示所有日志
    set({ clearedAfterLogId: null, clearedRunKey: null })
    saveClearedLogIdToStorage(null)
    // 触发日志重新加载（通过刷新页面或重新连接 WebSocket）
    window.location.reload()
  },

  updateConfig: (config) =>
    set((state) => ({
      config: { ...state.config, ...config },
    })),

  reset: () =>
    set({
      status: 'idle',
      platform: null,
      crawlerType: null,
      startedAt: null,
    }),
}))
