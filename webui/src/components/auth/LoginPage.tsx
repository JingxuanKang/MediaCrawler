import { useState, FormEvent } from 'react'
import { Bug } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { authApi } from '@/lib/api'

interface LoginPageProps {
  onLogin: (username: string) => void
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username || !password) return
    setLoading(true)
    setError('')
    try {
      const resp = await authApi.login(username.trim(), password)
      onLogin(resp.data.username)
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center cyber-grid bg-cyber-bg-primary/95 p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-5 rounded-xl border border-cyber-border-DEFAULT bg-cyber-bg-secondary/90 p-6 shadow-cyber-soft backdrop-blur"
      >
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-md bg-cyber-bg-tertiary border border-cyber-border-subtle flex items-center justify-center">
            <Bug className="h-5 w-5 text-cyber-neon-cyan" />
          </div>
          <div>
            <div className="text-sm font-mono font-semibold text-cyber-text-primary tracking-wide">
              MediaCrawler
            </div>
            <div className="text-[11px] text-cyber-text-muted">登录后进入各自的采集台</div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <label className="text-xs text-cyber-text-secondary font-mono">用户名</label>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="username"
              autoFocus
              className="h-9 text-xs"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs text-cyber-text-secondary font-mono">密码</label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="password"
              className="h-9 text-xs"
            />
          </div>
        </div>

        {error && (
          <div className="rounded-md border border-cyber-neon-orange/40 bg-cyber-neon-orange/10 px-3 py-2 text-[11px] text-cyber-neon-orange font-mono">
            {error}
          </div>
        )}

        <Button type="submit" disabled={loading} className="w-full">
          {loading ? '登录中…' : '登录'}
        </Button>

        <div className="text-[10px] text-cyber-text-muted leading-snug">
          账号由管理员创建。忘记密码找管理员重置。
        </div>
      </form>
    </div>
  )
}
