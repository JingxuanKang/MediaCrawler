# -*- coding: utf-8 -*-
"""多用户鉴权(自包含,纯 stdlib):scrypt 密码哈希 + hmac 签名 session cookie。

用户 store 落 data/_users.json;session 密钥落 data/_session_secret(0600)。
不引第三方依赖。管理员开户走 `python -m api.usertool`。
"""
import os
import re
import json
import hmac
import time
import base64
import hashlib
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Request, HTTPException

_DATA_DIR = Path(__file__).parent.parent / "data"
_USERS_FILE = _DATA_DIR / "_users.json"
_SECRET_FILE = _DATA_DIR / "_session_secret"

COOKIE_NAME = "mc_session"
SESSION_TTL = 7 * 24 * 3600  # 7 天
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{1,31}$")


# ---------- 基础设施 ----------
def _ensure_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_secret() -> bytes:
    """session 签名密钥:优先环境变量,否则本地文件(首次生成,0600)。"""
    env = os.environ.get("MC_SESSION_SECRET")
    if env:
        return env.encode()
    _ensure_dir()
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_bytes()
    sec = secrets.token_bytes(32)
    _SECRET_FILE.write_bytes(sec)
    try:
        os.chmod(_SECRET_FILE, 0o600)
    except OSError:
        pass
    return sec


def safe_username(name: str) -> str:
    """校验并归一用户名:小写字母数字下划线连字符,2-32 位。非法抛错。"""
    n = (name or "").strip().lower()
    if not _USERNAME_RE.match(n):
        raise ValueError("用户名只能是 2-32 位小写字母/数字/下划线/连字符,且以字母数字开头")
    return n


# ---------- 密码哈希(scrypt) ----------
def hash_password(pw: str) -> str:
    if not pw or len(pw) < 6:
        raise ValueError("密码至少 6 位")
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, salt_hex, dk_hex = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt_hex), n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ---------- 用户 store ----------
def load_users() -> dict:
    if not _USERS_FILE.exists():
        return {}
    try:
        return json.loads(_USERS_FILE.read_text("utf-8"))
    except Exception:
        return {}


def save_users(users: dict) -> None:
    _ensure_dir()
    tmp = _USERS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(users, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(_USERS_FILE)
    try:
        os.chmod(_USERS_FILE, 0o600)
    except OSError:
        pass


def add_user(username: str, password: str) -> str:
    u = safe_username(username)
    users = load_users()
    users[u] = {"pw": hash_password(password), "created": int(time.time())}
    save_users(users)
    return u


def remove_user(username: str) -> bool:
    u = safe_username(username)
    users = load_users()
    if u in users:
        del users[u]
        save_users(users)
        return True
    return False


# ---------- session token(base64(payload).hmac) ----------
def create_session(username: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"u": username, "exp": int(time.time()) + SESSION_TTL}).encode()
    ).decode()
    sig = hmac.new(_get_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_session(token: Optional[str]) -> Optional[str]:
    if not token or "." not in token:
        return None
    try:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(_get_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload))
        if int(data.get("exp", 0)) < time.time():
            return None
        return data.get("u")
    except Exception:
        return None


# ---------- FastAPI 依赖 ----------
def require_user(request: Request) -> str:
    """挂到需要登录的路由;未登录 401。返回用户名。"""
    user = verify_session(request.cookies.get(COOKIE_NAME))
    if not user or user not in load_users():
        raise HTTPException(status_code=401, detail="未登录")
    return user
