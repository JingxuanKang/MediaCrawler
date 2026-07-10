# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/routers/crawler.py
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

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse

from ..schemas import CrawlerStartRequest, CrawlerStatusResponse
from ..services import get_manager
from ..auth import require_user

router = APIRouter(prefix="/crawler", tags=["crawler"])


@router.post("/start")
async def start_crawler(request: CrawlerStartRequest, user: str = Depends(require_user)):
    """Start crawler task (本用户独立实例)"""
    mgr = get_manager(user)
    success = await mgr.start(request)
    if not success:
        if mgr.process and mgr.process.poll() is None:
            raise HTTPException(status_code=400, detail="Crawler is already running")
        raise HTTPException(status_code=500, detail="Failed to start crawler")

    return {"status": "ok", "message": "Crawler started successfully"}


@router.post("/stop")
async def stop_crawler(user: str = Depends(require_user)):
    """Stop crawler task"""
    mgr = get_manager(user)
    success = await mgr.stop()
    if not success:
        if not mgr.process or mgr.process.poll() is not None:
            raise HTTPException(status_code=400, detail="No crawler is running")
        raise HTTPException(status_code=500, detail="Failed to stop crawler")

    return {"status": "ok", "message": "Crawler stopped successfully"}


@router.get("/status", response_model=CrawlerStatusResponse)
async def get_crawler_status(user: str = Depends(require_user)):
    """Get crawler status"""
    return get_manager(user).get_status()


@router.get("/logs")
async def get_logs(limit: int = 100, user: str = Depends(require_user)):
    """Get recent logs"""
    mgr = get_manager(user)
    logs = mgr.logs[-limit:] if limit > 0 else mgr.logs
    return {"logs": [log.model_dump() for log in logs]}


@router.get("/qr")
async def get_login_qr(user: str = Depends(require_user)):
    """扫码登录二维码(无头浏览器写出的 PNG)。没有则 404。"""
    qr = get_manager(user).qr_file()
    if not qr.exists():
        raise HTTPException(status_code=404, detail="no qrcode")
    return FileResponse(
        qr, media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )
