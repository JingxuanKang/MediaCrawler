import { useState, useEffect } from 'react'
import { Toaster } from 'sonner'
import { Sidebar } from '@/components/layout/Sidebar'
import { MainContent } from '@/components/layout/MainContent'
import { CrawlerConfigPanel } from '@/components/config/CrawlerConfigPanel'
import { EnvironmentCheck, isEnvChecked } from '@/components/env/EnvironmentCheck'
import { LoginPage } from '@/components/auth/LoginPage'
import { QrLoginCard } from '@/components/auth/QrLoginCard'
import { authApi, setUnauthorizedHandler } from '@/lib/api'

type AuthState = 'checking' | 'anon' | 'authed'

function App() {
  const [authState, setAuthState] = useState<AuthState>('checking')
  const [username, setUsername] = useState('')
  const [envChecked, setEnvChecked] = useState(() => isEnvChecked())

  useEffect(() => {
    // 会话过期或任意接口 401 → 退回登录页
    setUnauthorizedHandler(() => setAuthState('anon'))
    authApi
      .me()
      .then((resp) => {
        setUsername(resp.data.username)
        setAuthState('authed')
      })
      .catch(() => setAuthState('anon'))
  }, [])

  const handleLogin = (u: string) => {
    setUsername(u)
    setAuthState('authed')
  }

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {
      /* ignore */
    }
    setUsername('')
    setAuthState('anon')
  }

  if (authState === 'checking') {
    return (
      <div className="flex h-screen items-center justify-center cyber-grid bg-cyber-bg-primary text-xs font-mono text-cyber-text-muted">
        加载中…
      </div>
    )
  }

  if (authState === 'anon') {
    return (
      <>
        <LoginPage onLogin={handleLogin} />
        <Toaster position="top-right" />
      </>
    )
  }

  return (
    <div className="flex flex-col h-screen cyber-grid overflow-hidden relative">
      {/* Environment Check Modal - 登录后跑 */}
      {!envChecked && <EnvironmentCheck onCheckComplete={() => setEnvChecked(true)} />}

      {/* 扫码登录浮层(QR 模式 + 运行中时自动出现) */}
      <QrLoginCard />

      {/* Header Bar */}
      <Sidebar username={username} onLogout={handleLogout} />

      {/* Main Area */}
      <div className="flex-1 flex flex-col gap-4 p-4 overflow-hidden min-h-0">
        <div className="flex-shrink-0">
          <CrawlerConfigPanel />
        </div>
        <MainContent />
      </div>

      <Toaster
        position="top-right"
        toastOptions={{
          className: 'glass-panel font-mono text-cyber-text-primary',
          style: {
            fontFamily: 'JetBrains Mono, monospace',
          },
        }}
      />
    </div>
  )
}

export default App
