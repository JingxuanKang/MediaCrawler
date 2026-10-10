import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { crawlerApi, configApi, errMsg } from '@/lib/api'
import { useCrawlerStore } from '@/store/crawlerStore'
import type { CrawlerConfig } from '@/types/crawler'

export function useCrawlerStatus() {
  const setStatus = useCrawlerStore((state) => state.setStatus)
  const setRunningInfo = useCrawlerStore((state) => state.setRunningInfo)
  const setErrorMessage = useCrawlerStore((state) => state.setErrorMessage)

  return useQuery({
    queryKey: ['crawlerStatus'],
    queryFn: async () => {
      const { data } = await crawlerApi.getStatus()
      setStatus(data.status)
      setRunningInfo(data.platform, data.crawler_type, data.started_at)
      setErrorMessage(data.error_message)
      return data
    },
    refetchInterval: 2000,
  })
}

export function useStartCrawler() {
  const queryClient = useQueryClient()
  const setStatus = useCrawlerStore((state) => state.setStatus)
  const resetLogsForNewRun = useCrawlerStore((state) => state.resetLogsForNewRun)

  return useMutation({
    mutationFn: (config: CrawlerConfig) => crawlerApi.start(config),
    onMutate: () => {
      resetLogsForNewRun()
      setStatus('running')
    },
    onSuccess: () => {
      toast.success('任务已启动')
      queryClient.invalidateQueries({ queryKey: ['crawlerStatus'] })
    },
    onError: (error: unknown) => {
      setStatus('idle')
      toast.error(`启动失败:${errMsg(error)}`)
      queryClient.invalidateQueries({ queryKey: ['crawlerStatus'] })
    },
  })
}

export function useStopCrawler() {
  const queryClient = useQueryClient()
  const setStatus = useCrawlerStore((state) => state.setStatus)

  return useMutation({
    mutationFn: () => crawlerApi.stop(),
    onMutate: () => {
      setStatus('stopping')
    },
    onSuccess: () => {
      toast.success('任务已停止')
      setStatus('idle')
      queryClient.invalidateQueries({ queryKey: ['crawlerStatus'] })
    },
    onError: (error: unknown) => {
      toast.error(`停止失败:${errMsg(error)}`)
      queryClient.invalidateQueries({ queryKey: ['crawlerStatus'] })
    },
  })
}

/** 首屏拉一次历史日志;WebSocket 没连上时(代理不支持、断线重连中)每 3 秒轮询兜底。 */
export function useCrawlerLogs() {
  const setLogs = useCrawlerStore((state) => state.setLogs)
  const wsConnected = useCrawlerStore((state) => state.wsConnected)
  const status = useCrawlerStore((state) => state.status)

  return useQuery({
    queryKey: ['crawlerLogs'],
    queryFn: async () => {
      const { data } = await crawlerApi.getLogs(0)
      setLogs(data.logs)
      return data.logs
    },
    refetchInterval: !wsConnected && (status === 'running' || status === 'stopping') ? 3000 : false,
    refetchOnWindowFocus: false,
  })
}

export function usePlatforms() {
  return useQuery({
    queryKey: ['platforms'],
    queryFn: async () => {
      const { data } = await configApi.getPlatforms()
      return data.platforms
    },
    staleTime: Infinity,
  })
}

export function useConfigOptions() {
  return useQuery({
    queryKey: ['configOptions'],
    queryFn: async () => {
      const { data } = await configApi.getOptions()
      return data
    },
    staleTime: Infinity,
  })
}
