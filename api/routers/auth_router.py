# -*- coding: utf-8 -*-
"""登录/登出/当前用户。同源 httpOnly cookie,前端 axios/WS 自动携带。"""
import time
from collections import defaultdict

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel

from .. import auth
from ..services.crawler_manager import CDP_USERS

router = APIRouter(prefix="/auth", tags=["auth"])

# 极简登录限速:同 IP 5 分钟内失败 10 次即拒
_FAILS: dict = defaultdict(list)
_WINDOW = 300
_MAX_FAILS = 10


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    ip = _client_ip(request)
    now = time.time()
    _FAILS[ip] = [t for t in _FAILS[ip] if now - t < _WINDOW]
    if len(_FAILS[ip]) >= _MAX_FAILS:
        raise HTTPException(status_code=429, detail="尝试过多,稍后再试")

    users = auth.load_users()
    rec = users.get((body.username or "").strip().lower())
    if not rec or not auth.verify_password(body.password, rec["pw"]):
        _FAILS[ip].append(now)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    _FAILS.pop(ip, None)
    username = (body.username or "").strip().lower()
    token = auth.create_session(username)
    # 经 caddy 时 X-Forwarded-Proto=https → Secure;本地直连 http 不加 Secure(便于内网/排障)
    secure = (request.headers.get("x-forwarded-proto", request.url.scheme) == "https")
    response.set_cookie(
        auth.COOKIE_NAME, token,
        httponly=True, samesite="lax", secure=secure,
        max_age=auth.SESSION_TTL, path="/",
    )
    return {"username": username}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: str = Depends(auth.require_user)):
    # cdp=True 的用户走 chrome.jingxuan.uk 桌面登录(连真 Chromium),前端不弹扫码浮层
    return {"username": user, "cdp": user in CDP_USERS}
