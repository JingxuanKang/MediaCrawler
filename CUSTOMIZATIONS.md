# 本仓定制(JingxuanKang fork,相对上游 NanmiCoder/MediaCrawler)

上游是"跑一次的采集器";本仓改成 **linux 上常驻的多用户 WebUI 服务**,并接上一台真 Chromium 桌面走 CDP。代码真源 `macbook:~/Build/MediaCrawler`,部署在 `linux:~/Build/MediaCrawler`(py3.11 venv,`tmux -L claude` 里 `bash run-webui.sh`)。公网入口 `crawl.jingxuan.uk`(korea caddy,**无 Google 网关**,鉴权归 App 登录页)。运维细节见 `~/Build/infra/servers/linux.md`。

## 一、多用户(多租户)
- `api/auth.py`:scrypt 密码哈希 + hmac 签名 httpOnly cookie(全 stdlib)。用户库 `data/_users.json`(0600),session 密钥 `data/_session_secret`(0600)。
- `api/routers/auth_router.py`:`/api/auth/{login,logout,me}`,登录限速。`/me` 返回 `{username, cdp}`。
- 全部 `/api`(crawler/data/ws/config/env)挂 `require_user`;WS 用 cookie 鉴权。
- **每用户独立**:`api/services/crawler_manager.py` 单例 → `get_manager(user)` 注册表,爬虫进程/日志/状态/WS 全隔离;数据 `data/<用户>/{平台}/`(可再套子数据集)。
- **开户(管理员)**:`.venv/bin/python -m api.usertool add <用户名> <密码>`(`list`/`remove`)。

## 二、CDP:白名单用户连真 Chromium(低风控)
- `config/base_config.py`:`ENABLE_CDP_MODE`/`CDP_DEBUG_PORT` 读 env,`CDP_CONNECT_EXISTING=True`,**`AUTO_CLOSE_BROWSER=False`**(绝不关那台桌面浏览器)。
- `crawler_manager` 白名单 `CDP_USERS`(env `MC_CDP_USERS`,默认 `jingxuan`)→ 对其爬虫注入 `MC_CDP=1` 连 `localhost:9222`(= `chrome.jingxuan.uk` 的 Selkies Chromium,host 网络);其他用户照旧 headless。
- 登录:白名单用户在 `chrome.jingxuan.uk` 桌面里登一次,持久 profile 记住,爬虫复用。前端对 CDP 用户**不弹扫码浮层**(`QrLoginCard` 收 `cdp` prop)。
- ⚠️ **数据抓取走 httpx 签名(非浏览器)**,CDP 只兜登录;猛抓热词照样撞 CAPTCHA 并作废 web_session → 悠着抓。

## 三、数据落 NAS + 下媒体 + 真作者(env 开关)
`run-webui.sh` export:
- `MC_DATA_ROOT=/mnt/mc-nas`:爬取产物落 NAS(rw SSHFS → `/volume3/mediacrawler`,`nas-mc.service`);`crawler_manager._data_path` + `api/routers/data.py` 的 `DATA_DIR` 都读它。用户库/session 仍本地 `data/`。
- `MC_GET_MEDIAS=1`:`config.ENABLE_GET_MEIDAS` → 下载图片/视频**文件**(非只存 URL)。
- `MC_ANONYMIZE=0`:`tools/user_hash.py` → 存**真实** user_id/昵称(上游默认脱敏)。
- `MC_SLEEP`:抓取间隔秒(前端「每条间隔秒」);`MAX_CONCURRENCY_NUM` 保持 1。

## 四、给 media-sync/xhs-sync 供登录态
- `api/main.py` 加 `GET /api/browser/xhs_cookie`(`X-Provider-Secret`=`MC_PROVIDER_SECRET`,`run-webui.sh` 从 `~/.mc-provider-secret` 读)→ 读本地 Chromium CDP 的小红书 cookie 返回。
- xhs-sync 的「从浏览器同步登录态」按钮拉这个口(见 `media-sync/xhs-sync`)。CDP 不外露,只经这个密钥口出。

## 五、前端(webui/)
- 登录门(`App.tsx` + `auth/LoginPage.tsx`);登出;`lib/api.ts` `withCredentials` + 401 拦截。
- 采集台字段:**账号/子数据集**、**最多抓几条**、**每条间隔秒**(`CrawlerConfigPanel.tsx`)。
- 扫码浮层 `auth/QrLoginCard.tsx`(仅非 CDP 用户、QR 模式运行中显示;`crawler_manager` 把 `show_qrcode` 二维码写 `MC_QR_PATH`,`/api/crawler/qr` 提供)。
- 去掉:顶栏免责横幅、登录前 license 弹窗、底部作者推广栏、界面上的「无头模式」开关(服务器强制无头)。

## 部署
```bash
# 本地改 → 推 linux
rsync -a --exclude=.venv --exclude=node_modules --exclude=/data --exclude='*.db' \
  ~/Build/MediaCrawler/ linux:~/Build/MediaCrawler/
# linux 上:前端改了要 (cd webui && npm run build);重启
ssh linux 'tmux -L claude kill-session -t mcweb; tmux -L claude new-session -d -s mcweb \
  "bash ~/Build/MediaCrawler/run-webui.sh > /tmp/mc-web.log 2>&1"'
```
