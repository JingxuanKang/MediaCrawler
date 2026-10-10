import { Bug, Wifi, Github, LogOut, User } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { useCrawlerStore } from '@/store/crawlerStore'
import { useCrawlerStatus } from '@/hooks/useCrawler'
import { LanguageSwitch } from './LanguageSwitch'
import { ThemeToggle } from './ThemeToggle'

interface SidebarProps {
  username?: string
  onLogout?: () => void
}

export function Sidebar({ username, onLogout }: SidebarProps) {
  const { t } = useTranslation()
  const status = useCrawlerStore((state) => state.status)

  // Poll status
  useCrawlerStatus()

  const isRunning = status === 'running'

  return (
    <header className="h-14 flex-shrink-0 glass-panel border-b border-cyber-border-subtle relative z-10">
      <div className="h-full px-4 flex items-center justify-between">
        {/* Left: Logo and GitHub Star */}
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <Bug className="w-5 h-5 text-cyber-neon-cyan" />
          <span className="font-mono font-bold text-cyber-text-primary tracking-wider text-sm truncate">
            MediaCrawler
          </span>
          <a
            href="https://github.com/NanmiCoder/MediaCrawler"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:flex items-center gap-1.5 px-2 py-1 rounded-md border border-cyber-border-subtle hover:border-cyber-neon-cyan hover:shadow-glow-cyan-sm transition-all bg-cyber-bg-tertiary"
          >
            <Github className="w-4 h-4 text-cyber-text-secondary" />
            <span className="text-xs font-mono text-cyber-text-secondary">Star</span>
          </a>
          {isRunning && (
            <Badge variant="running" className="text-[10px]">
              {t('status.active')}
            </Badge>
          )}
          {isRunning && (
            <span className="w-2 h-2 bg-cyber-neon-green rounded-full shadow-glow-green-sm animate-pulse-fast" />
          )}
        </div>

        {/* Center: spacer */}
        <div className="flex-1" />

        {/* Right: Actions and Status */}
        <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
          {/* Current user + logout */}
          {username && (
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1 text-xs font-mono text-cyber-text-secondary max-w-[7rem] truncate">
                <User className="w-3.5 h-3.5 flex-shrink-0" />
                <span className="truncate">{username}</span>
              </span>
              <button
                onClick={onLogout}
                title="登出"
                aria-label="登出"
                className="flex items-center gap-1 px-2 py-1 rounded-md border border-cyber-border-subtle hover:border-cyber-neon-orange hover:text-cyber-neon-orange text-cyber-text-secondary transition-all bg-cyber-bg-tertiary text-xs font-mono whitespace-nowrap"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">登出</span>
              </button>
            </div>
          )}
          {/* Theme / Language:手机上收起,省出顶栏宽度 */}
          <div className="hidden sm:flex items-center gap-3">
            <ThemeToggle />
            <LanguageSwitch />
          </div>

          {/* Status Info */}
          <div className="hidden lg:flex items-center gap-2 text-xs font-mono">
            <span className="text-cyber-text-muted">{t('sidebar.api')}:</span>
            <span className="text-cyber-neon-green">v1.0.0</span>
            <div className="flex items-center gap-1.5">
              <Wifi className="w-3 h-3 text-cyber-text-secondary" />
              <span className="text-cyber-text-secondary">{t('sidebar.local')}</span>
              <span className="status-dot status-dot-online" />
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
