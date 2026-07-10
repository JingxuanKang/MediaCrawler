#!/bin/bash
# MediaCrawler 桌面会话(以 jingxuan 跑,连 root 起的 Xorg :1)。
export DISPLAY=:1 XAUTHORITY=/run/mc-xauth HOME=/home/jingxuan
xset s off -dpms s noblank 2>/dev/null

# 窗口管理器
openbox &
sleep 1

# 真 Google Chrome:CDP 9222(供 MediaCrawler 挂),持久 profile,崩溃自拉起
(
  while true; do
    google-chrome-stable \
      --user-data-dir="$HOME/.mc-chrome" \
      --remote-debugging-port=9222 \
      --remote-allow-origins=* \
      --no-first-run --no-default-browser-check --password-store=basic \
      --start-maximized --window-size=1920,1080 \
      --disable-session-crashed-bubble --disable-infobars \
      "https://www.xiaohongshu.com"
    sleep 3
  done
) &

# Sunshine(NVENC 串流,前台;它退出则整会话重启)
sleep 3
exec sunshine
