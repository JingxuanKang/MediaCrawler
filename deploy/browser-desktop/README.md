# browser-desktop —— jingxuan 专属真 Chrome 桌面(给 MediaCrawler CDP 用)

部署在 **linux**(家里 i9 + RTX 3090)。给 `jingxuan` 一个跑在 3090 虚拟屏上的**真 Google Chrome**,
MediaCrawler 通过 CDP(`localhost:9222`)挂上去驱动它 —— 真实浏览器指纹、持久登录态、低风控。
其他用户不受影响(照旧各自 headless chromium)。

## 组成(全在 linux host,systemd)

| 单元 | 身份 | 作用 |
|---|---|---|
| `mc-xorg.service` | root | 在 3090 上起无头 Xorg `:1`(`/etc/X11/mc-desktop.conf`,假 EDID 1920x1080),xauth cookie 落 `/run/mc-xauth` |
| `mc-session.service` | jingxuan | 连 `:1`,跑 openbox + 真 Chrome(`--remote-debugging-port=9222` 持久 profile `~/.mc-chrome`)+ Sunshine |
| `mc-x11vnc.service` | jingxuan | x11vnc 抓 `:1` → `localhost:5900` |
| `mc-novnc.service` | jingxuan | websockify + noVNC → `:6080`(网页版桌面) |
| Sunshine(会话内拉起) | jingxuan | NVENC 硬件编码串流,Moonlight 客户端连,端口 47989/47990/48010 |

## 两种远程看/操作这个桌面

- **网页版(手机也行,最省事)**:`https://chrome.jingxuan.uk`(korea caddy + Google 登录,只本人)→ noVNC。用来扫码登录小红书。
- **Sunshine(顶配丝滑)**:装 Moonlight 客户端,连 linux tailnet IP `100.125.158.68`,首次在 `https://100.125.158.68:47990` 设管理员账号密码 + 配对 PIN。

## MediaCrawler 联动

- `config/base_config.py`:`ENABLE_CDP_MODE`/`CDP_DEBUG_PORT` 读环境变量,`CDP_CONNECT_EXISTING=True`,`AUTO_CLOSE_BROWSER=False`(绝不关持久 Chrome)。
- `api/services/crawler_manager.py`:白名单 `CDP_USERS`(默认 `jingxuan`,`MC_CDP_USERS` 可覆盖)→ 对这些用户的爬虫子进程注入 `MC_CDP=1`,走 CDP 连 `localhost:9222`;其他用户不注入、照旧 headless。
- 登录:头一次在网页/Moonlight 桌面里把小红书登上(扫码/短信),持久 profile 记住;之后爬虫直接复用会话。

## 部署

```bash
# 配置落位(linux)
sudo cp mc-desktop.conf /etc/X11/mc-desktop.conf
cp session-run.sh ~/.mc-desktop/session-run.sh && chmod +x ~/.mc-desktop/session-run.sh
sudo cp mc-xorg.service mc-session.service mc-x11vnc.service mc-novnc.service /etc/systemd/system/
printf 'allowed_users=anybody\nneeds_root_rights=yes\n' | sudo tee /etc/X11/Xwrapper.config
# jingxuan 需在 video/input/tty 组(非 root 起 X)
sudo usermod -aG video,input,tty jingxuan
sudo systemctl daemon-reload
sudo systemctl enable --now mc-xorg mc-session mc-x11vnc mc-novnc
```

## 排障

- Chrome CDP 活着?`curl -s localhost:9222/json/version`
- X 在 3090?`nvidia-smi | grep -i xorg`(应见 `Xorg :1`)
- Sunshine?`ss -ltn | grep 47990`;日志 `~/.mc-desktop/sunshine.log`
- **不影响 media-process**:whisper 用 CUDA 计算、X/Chrome/Sunshine 用图形+NVENC,24G 显存够;查 `nvidia-smi` 各自占用。
