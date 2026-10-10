# Deploy:MediaCrawler 采集台

本文件只管本 fork 的 WebUI 服务部署。定制内容见 `CUSTOMIZATIONS.md`,机器登录与网络见 `~/Build/infra/servers/linux.md`。

## 现状

| 项 | 值 |
|---|---|
| 机器 | linux(家里 i9 + 3090) |
| 代码 | `linux:~/Build/MediaCrawler`(真源 `macbook:~/Build/MediaCrawler`) |
| 运行环境 | 项目根 `.venv`(py3.11),爬虫子进程用 `uv run` |
| 进程 | `tmux -L claude` 会话 `mcweb` 里跑 `bash run-webui.sh`,监听 `0.0.0.0:8080` |
| 公网入口 | `https://crawl.jingxuan.uk`(korea caddy 反代;无 Google 网关,App 自带登录页) |
| 数据 | `MC_DATA_ROOT=/mnt/mc-nas`(NAS SSHFS 挂载,`nas-mc.service`);用户库与 session 密钥在本机 `data/` |
| 日志 | `/tmp/mc-web.log`(tmux 方式);改用 systemd 后看 `journalctl --user -u mediacrawler-webui` |

tmux 会话不随开机恢复。linux 重启后要手动拉起,或按下文「开机自启」改用 systemd。

## 部署(本地改完之后)

1. 本地 commit。
2. 同步到 linux:

   ```bash
   rsync -a --exclude=.venv --exclude=node_modules --exclude=/data --exclude='*.db' \
     ~/Build/MediaCrawler/ linux:~/Build/MediaCrawler/
   ```

3. 前端有改动时,在 linux 上构建(产物进 `api/webui/`):

   ```bash
   ssh linux 'cd ~/Build/MediaCrawler/webui && npm ci && npm run build'
   ```

4. 重启服务(tmux 方式):

   ```bash
   ssh linux 'tmux -L claude kill-session -t mcweb; tmux -L claude new-session -d -s mcweb \
     "bash ~/Build/MediaCrawler/run-webui.sh > /tmp/mc-web.log 2>&1"'
   ```

   已改用 systemd 时:`ssh linux 'systemctl --user restart mediacrawler-webui'`。

重启会结束正在运行的采集任务。先确认没有人在跑任务。

## 健康检查

```bash
ssh linux 'curl -s localhost:8080/api/health'          # {"status":"ok"}
curl -s -o /dev/null -w '%{http_code}\n' https://crawl.jingxuan.uk/   # 200
ssh linux 'tail -n 30 /tmp/mc-web.log'                  # 看 run-webui.sh 的启动检查输出
```

`run-webui.sh` 启动前会检查下列项。不满足时它打印原因并退出,或打印提醒后继续:

| 检查 | 不满足时 |
|---|---|
| `.venv/bin/uvicorn` 存在 | 退出 |
| PATH 里有 `uv` | 退出 |
| `MC_DATA_ROOT` 已挂载且可写 | 退出(`MC_REQUIRE_MOUNT=0` 可跳过挂载检查) |
| `api/webui/index.html` 存在 | 提醒:前端没构建 |
| `data/_users.json` 非空 | 提醒:还没有用户 |
| `~/.mc-provider-secret` 存在 | 提醒:登录态提供口会回 401 |

可覆盖的环境变量:`MC_DATA_ROOT`、`MC_HOST`、`MC_PORT`、`MC_GET_MEDIAS`、`MC_ANONYMIZE`、`MC_CDP_USERS`、`MC_REQUIRE_MOUNT`。

## 开户

```bash
ssh linux 'cd ~/Build/MediaCrawler && .venv/bin/python -m api.usertool add <用户名> <密码>'   # list / remove 同理
```

## 回滚

```bash
git -C ~/Build/MediaCrawler log --oneline -5      # 本地找到上一个好版本
git -C ~/Build/MediaCrawler checkout <hash> -- .  # 或 git revert
```

然后按「部署」第 2 到 4 步重新同步、构建、重启。回滚后回到 main 并 commit,保持本地为真源。

## 开机自启(草案,尚未启用)

单元文件在 `deploy/mediacrawler-webui.service`。它调用同一个 `run-webui.sh`,崩溃或 NAS 未挂载时每 15 秒重试。

启用步骤(在 linux 上,一次性):

```bash
# 1. 停掉 tmux 会话,避免抢 8080 端口
tmux -L claude kill-session -t mcweb
# 2. 安装并启用单元
mkdir -p ~/.config/systemd/user
cp ~/Build/MediaCrawler/deploy/mediacrawler-webui.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now mediacrawler-webui
# 3. 让 user 单元在未登录时也运行(开机即起)
sudo loginctl enable-linger "$USER"
# 4. 验证
systemctl --user status mediacrawler-webui
journalctl --user -u mediacrawler-webui -n 50
```

启用后同步更新本文件「现状」和 `~/Build/infra/servers/linux.md`。
