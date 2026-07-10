import { useEffect, useState } from 'react'
import { useCrawlerStore } from '@/store/crawlerStore'

/**
 * 扫码登录浮层:当登录方式=QR 且爬虫运行中时,轮询 /api/crawler/qr,
 * 无头浏览器写出二维码后显示出来给用户手机扫。登录成功后后端删除二维码文件
 * → 轮询转 404 → 浮层自动收起。
 */
export function QrLoginCard() {
  const loginType = useCrawlerStore((s) => s.config.login_type)
  const status = useCrawlerStore((s) => s.status)
  const active = loginType === 'qrcode' && status === 'running'
  const [imgUrl, setImgUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!active) {
      setImgUrl(null)
      return
    }
    let stopped = false
    let objUrl: string | null = null

    const poll = async () => {
      try {
        const resp = await fetch('/api/crawler/qr?t=' + Date.now(), { credentials: 'include' })
        if (stopped) return
        if (resp.ok) {
          const blob = await resp.blob()
          if (stopped) return
          const next = URL.createObjectURL(blob)
          if (objUrl) URL.revokeObjectURL(objUrl)
          objUrl = next
          setImgUrl(next)
        } else {
          // 404 = 还没生成 或 已登录被删 → 收起
          if (objUrl) {
            URL.revokeObjectURL(objUrl)
            objUrl = null
          }
          setImgUrl(null)
        }
      } catch {
        /* ignore */
      }
    }

    poll()
    const id = setInterval(poll, 2000)
    return () => {
      stopped = true
      clearInterval(id)
      if (objUrl) URL.revokeObjectURL(objUrl)
    }
  }, [active])

  if (!active || !imgUrl) return null

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-xs rounded-xl border border-cyber-border-DEFAULT bg-cyber-bg-secondary p-5 text-center space-y-3 shadow-cyber-soft">
        <div className="text-sm font-mono font-semibold text-cyber-text-primary">小红书扫码登录</div>
        <img
          src={imgUrl}
          alt="登录二维码"
          className="mx-auto h-52 w-52 rounded-md bg-white p-2"
        />
        <div className="text-[11px] leading-snug text-cyber-text-muted">
          打开小红书 App → 右上角「+」或「扫一扫」→ 扫这个码。
          <br />
          手机上确认登录后,浮层会自动关闭、任务继续。
        </div>
      </div>
    </div>
  )
}
