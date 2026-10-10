# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/main.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

"""
MediaCrawler WebUI API Server
Start command: uvicorn api.main:app --port 8080 --reload
Or: python -m api.main
"""
import asyncio
import os
import sys
import subprocess
from pathlib import Path
import uvicorn
import hmac
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routers import crawler_router, data_router, websocket_router
from .routers.auth_router import router as auth_router
from .auth import require_user
from fastapi import Depends

# Project root directory (used for running subprocesses like uv run main.py)
PROJECT_ROOT = Path(__file__).parent.parent

app = FastAPI(
    title="MediaCrawler WebUI API",
    description="API for controlling MediaCrawler from WebUI",
    version="1.0.0"
)

# Get webui static files directory
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")

# CORS configuration - allow frontend dev server access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Backup port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 字段中文名:校验失败时拼进提示
_FIELD_NAMES = {
    "platform": "平台", "login_type": "登录方式", "crawler_type": "爬取类型",
    "keywords": "关键词", "specified_ids": "帖子/视频 ID", "creator_ids": "创作者 ID",
    "start_page": "起始页", "save_option": "保存格式", "account": "子数据集",
    "max_notes_count": "最多抓几条", "max_comments_count": "每条最多评论数",
    "crawl_interval": "每条间隔秒", "username": "用户名", "password": "密码",
}


def _validation_message(err: dict) -> str:
    loc = [str(x) for x in err.get("loc", ()) if x not in ("body", "query", "path") and not isinstance(x, int)]
    name = _FIELD_NAMES.get(loc[-1], loc[-1]) if loc else ""
    ctx = err.get("ctx") or {}
    t = err.get("type", "")
    if t == "json_invalid":
        return "请求体不是合法 JSON"
    if t == "value_error":  # 来自 model_validator 的中文提示
        return str(ctx.get("error") or err.get("msg", "")).removeprefix("Value error, ")
    if t in ("less_than_equal", "less_than"):
        return f"{name}不能大于 {ctx.get('le', ctx.get('lt'))}"
    if t in ("greater_than_equal", "greater_than"):
        return f"{name}不能小于 {ctx.get('ge', ctx.get('gt'))}"
    if t == "enum":
        return f"{name}取值无效"
    if t == "missing":
        return f"缺少{name or '必填项'}"
    if t.endswith("_parsing") or t.endswith("_type"):
        return f"{name}格式不对"
    return f"{name}: {err.get('msg', '')}" if name else err.get("msg", "参数错误")


@app.exception_handler(RequestValidationError)
async def _on_validation_error(request: Request, exc: RequestValidationError):
    """校验错误也回 {"detail": "<中文一句话>"},与 HTTPException 的形状一致,前端只读 detail 字符串。"""
    msgs = list(dict.fromkeys(_validation_message(e) for e in exc.errors()))
    return JSONResponse(status_code=422, content={"detail": ";".join(msgs) or "参数错误"})


# Register routers
app.include_router(auth_router, prefix="/api")  # 登录/登出/me,公开
app.include_router(crawler_router, prefix="/api")
app.include_router(data_router, prefix="/api")
app.include_router(websocket_router, prefix="/api")


@app.get("/")
async def serve_frontend():
    """Return frontend page"""
    index_path = os.path.join(WEBUI_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": "MediaCrawler WebUI API",
        "version": "1.0.0",
        "docs": "/docs",
        "note": "WebUI not found, please build it first: cd webui && npm run build"
    }


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/browser/xhs_cookie")
async def browser_xhs_cookie(x_provider_secret: str = Header(default="")):
    """给 media-sync/xhs-sync 拉登录态:读本地 Chromium(CDP 9222)的小红书 cookie。
    密钥 MC_PROVIDER_SECRET(= xhs bridge secret)保护;CDP 不外露,只本机读、经这个 HTTP 口出。"""
    sec = os.environ.get("MC_PROVIDER_SECRET", "")
    if not sec or not hmac.compare_digest(x_provider_secret.encode(), sec.encode()):
        raise HTTPException(status_code=401, detail="provider secret 不符")
    port = os.environ.get("MC_CDP_PORT", "9222")
    from playwright.async_api import async_playwright
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{port}")
            ctx = browser.contexts[0]
            cks = await ctx.cookies()
            await browser.close()
    except Exception as e:  # noqa
        raise HTTPException(status_code=503, detail=f"读 CDP 失败:{e}")
    xhs = [{"name": c["name"], "value": c["value"]}
           for c in cks if "xiaohongshu" in (c.get("domain") or "")]
    return {"platform": "xhs", "cookies": xhs}


@app.get("/api/env/check")
async def check_environment(user: str = Depends(require_user)):
    """Check if MediaCrawler environment is configured correctly"""
    try:
        # Run uv run main.py --help command to check environment
        # Use PROJECT_ROOT so it works regardless of where uvicorn was started
        if sys.platform == "win32":
            loop = asyncio.get_running_loop()
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["uv", "run", "main.py", "--help"],
                    capture_output=True,
                    timeout=30.0,
                    cwd=str(PROJECT_ROOT)
                )
            )
            stdout, stderr = process.stdout, process.stderr  # bytes
        else:
            process = await asyncio.create_subprocess_exec(
                "uv", "run", "main.py", "--help",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(PROJECT_ROOT)  # Project root directory
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0  # 30 seconds timeout
            )
        if process.returncode == 0:
            return {
                "success": True,
                "message": "MediaCrawler environment configured correctly",
                "output": stdout.decode("utf-8", errors="ignore")[:500]  # Truncate to first 500 characters
            }
        else:
            error_msg = stderr.decode("utf-8", errors="ignore") or stdout.decode("utf-8", errors="ignore")
            return {
                "success": False,
                "message": "Environment check failed",
                "error": error_msg[:500]
            }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "message": "Environment check timeout",
            "error": "Command execution exceeded 30 seconds"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "message": "uv command not found",
            "error": "Please ensure uv is installed and configured in system PATH"
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Environment check error",
            "error": f"{type(e).__name__}: {str(e) or 'Unknown'}"
        }


@app.get("/api/config/platforms")
async def get_platforms(user: str = Depends(require_user)):
    """Get list of supported platforms"""
    return {
        "platforms": [
            {"value": "xhs", "label": "Xiaohongshu", "icon": "book-open"},
            {"value": "dy", "label": "Douyin", "icon": "music"},
            {"value": "ks", "label": "Kuaishou", "icon": "video"},
            {"value": "bili", "label": "Bilibili", "icon": "tv"},
            {"value": "wb", "label": "Weibo", "icon": "message-circle"},
            {"value": "tieba", "label": "Baidu Tieba", "icon": "messages-square"},
            {"value": "zhihu", "label": "Zhihu", "icon": "help-circle"},
        ]
    }


@app.get("/api/config/options")
async def get_config_options(user: str = Depends(require_user)):
    """Get all configuration options"""
    return {
        "login_types": [
            {"value": "qrcode", "label": "QR Code Login"},
            {"value": "cookie", "label": "Cookie Login"},
        ],
        "crawler_types": [
            {"value": "search", "label": "Search Mode"},
            {"value": "detail", "label": "Detail Mode"},
            {"value": "creator", "label": "Creator Mode"},
        ],
        "save_options": [
            {"value": "jsonl", "label": "JSONL File"},
            {"value": "json", "label": "JSON File"},
            {"value": "csv", "label": "CSV File"},
            {"value": "excel", "label": "Excel File"},
            {"value": "sqlite", "label": "SQLite Database"},
            {"value": "db", "label": "MySQL Database"},
            {"value": "mongodb", "label": "MongoDB Database"},
        ],
    }


# Mount static resources - must be placed after all routes
if os.path.exists(WEBUI_DIR):
    assets_dir = os.path.join(WEBUI_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    # Mount logos directory
    logos_dir = os.path.join(WEBUI_DIR, "logos")
    if os.path.exists(logos_dir):
        app.mount("/logos", StaticFiles(directory=logos_dir), name="logos")
    # Mount other static files (e.g., vite.svg)
    app.mount("/static", StaticFiles(directory=WEBUI_DIR), name="webui-static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
