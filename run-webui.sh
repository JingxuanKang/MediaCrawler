#!/bin/bash
# MediaCrawler WebUI 启动脚本(linux 部署用;systemd --user 单元或 tmux 里跑都调它)。
# 用 export 确保环境变量确实进到 uvicorn 及其爬虫子进程(内联 env 经 tmux 有时不生效)。
# 下面的变量都可以在调用前用环境变量覆盖。
set -u
cd "$(dirname "$0")" || exit 1

die()  { echo "[run-webui] 错误:$*" >&2; exit 1; }
warn() { echo "[run-webui] 提醒:$*" >&2; }

export UV_NO_SYNC=1                                   # uv run 不重装,用现成 .venv
export MC_DATA_ROOT="${MC_DATA_ROOT:-/mnt/mc-nas}"    # 数据落 NAS(SSHFS rw 挂载,/volume3/mediacrawler)
export MC_GET_MEDIAS="${MC_GET_MEDIAS:-1}"            # 下载图片/视频文件本身(非只存 URL)
export MC_ANONYMIZE="${MC_ANONYMIZE:-0}"              # 存真实作者 user_id / 昵称(不脱敏)
# CDP 白名单(默认 jingxuan);如需改 export MC_CDP_USERS=a,b
MC_HOST="${MC_HOST:-0.0.0.0}"
MC_PORT="${MC_PORT:-8080}"

# ---- 启动前检查:缺什么就直接说缺什么 ----
[ -x .venv/bin/uvicorn ] || die "找不到 .venv/bin/uvicorn。先在项目根建 py3.11 venv 并装依赖(见 Deploy.md「首次安装」)。"
command -v uv >/dev/null 2>&1 || die "PATH 里没有 uv,爬虫子进程用 uv run 启动。systemd 单元里要把 ~/.local/bin 加进 PATH。"

[ -f api/webui/index.html ] || warn "前端没构建(api/webui/index.html 不存在),首页只会返回 JSON。执行:(cd webui && npm ci && npm run build)"

# 数据根必须是已挂载的 NAS;没挂上就退出,免得数据写进本机空目录。
# 本机调试可设 MC_REQUIRE_MOUNT=0 跳过。
if [ "${MC_REQUIRE_MOUNT:-1}" = "1" ] && command -v mountpoint >/dev/null 2>&1; then
  mountpoint -q "$MC_DATA_ROOT" || die "数据目录 $MC_DATA_ROOT 没有挂载(NAS SSHFS 未就绪)。先检查 nas-mc.service,或设 MC_REQUIRE_MOUNT=0 用本机目录。"
fi
[ -d "$MC_DATA_ROOT" ] && [ -w "$MC_DATA_ROOT" ] || die "数据目录 $MC_DATA_ROOT 不存在或不可写。"

[ -s data/_users.json ] || warn "还没有任何用户,登录页进不去。开户:.venv/bin/python -m api.usertool add <用户名> <密码>"

# 给 xhs-sync 拉登录态的提供口密钥(= xhs bridge secret);存本地文件,不入 git
if [ -f "$HOME/.mc-provider-secret" ]; then
  export MC_PROVIDER_SECRET="$(cat "$HOME/.mc-provider-secret")"
else
  warn "没有 ~/.mc-provider-secret,/api/browser/xhs_cookie 会一律回 401(不影响 WebUI 本身)。"
fi

echo "[run-webui] 启动 uvicorn $MC_HOST:$MC_PORT,数据根 $MC_DATA_ROOT"
exec .venv/bin/uvicorn api.main:app --host "$MC_HOST" --port "$MC_PORT"
