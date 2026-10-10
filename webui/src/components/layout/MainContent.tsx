import { Terminal } from '@/components/console/Terminal'
import { useLogWebSocket } from '@/hooks/useWebSocket'
import { useCrawlerLogs } from '@/hooks/useCrawler'

export function MainContent() {
  // Connect to WebSocket for logs
  useLogWebSocket()
  useCrawlerLogs()

  return (
    <main className="flex-1 flex flex-col overflow-hidden min-h-[360px] md:min-h-0 relative z-10">
      <Terminal />
    </main>
  )
}
