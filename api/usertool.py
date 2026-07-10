# -*- coding: utf-8 -*-
"""管理员开户 CLI。用法(在项目根、venv 内):

    .venv/bin/python -m api.usertool add <用户名> <密码>
    .venv/bin/python -m api.usertool list
    .venv/bin/python -m api.usertool remove <用户名>
"""
import sys

from . import auth


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    try:
        if cmd == "add":
            u = auth.add_user(args[1], args[2])
            print(f"已建用户: {u}")
        elif cmd == "list":
            users = auth.load_users()
            print("\n".join(users.keys()) if users else "(无用户)")
        elif cmd == "remove":
            ok = auth.remove_user(args[1])
            print("已删除" if ok else "用户不存在")
        else:
            print(__doc__)
            return 0 if cmd == "help" else 1
    except (IndexError, ValueError) as e:
        print(f"错误: {e}")
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
