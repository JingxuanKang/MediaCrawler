#!/bin/bash
# MediaCrawler WebUI 启动脚本(linux 部署用,tmux -L claude 里跑)。
# 用 export 确保环境变量确实进到 uvicorn 及其爬虫子进程(内联 env 经 tmux 有时不生效)。
cd "$(dirname "$0")" || exit 1

export UV_NO_SYNC=1                       # uv run 不重装,用现成 .venv
export MC_DATA_ROOT=/mnt/mc-nas           # 数据落 NAS(SSHFS rw 挂载,/volume3/mediacrawler)
export MC_GET_MEDIAS=1                    # 下载图片/视频文件本身(非只存 URL)
export MC_ANONYMIZE=0                     # 存真实作者 user_id / 昵称(不脱敏)
# CDP 白名单(默认 jingxuan);如需改 export MC_CDP_USERS=a,b

# 给 xhs-sync 拉登录态的提供口密钥(= xhs bridge secret);存本地文件,不入 git
[ -f "$HOME/.mc-provider-secret" ] && export MC_PROVIDER_SECRET="$(cat "$HOME/.mc-provider-secret")"

exec .venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8080
