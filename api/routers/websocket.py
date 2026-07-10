# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/routers/websocket.py
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

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services import get_manager
from ..auth import COOKIE_NAME, verify_session, load_users

router = APIRouter(tags=["websocket"])


def _ws_user(websocket: WebSocket):
    """从 cookie 解析登录用户(同源 WS 握手自动带 cookie)。未登录返回 None。"""
    user = verify_session(websocket.cookies.get(COOKIE_NAME))
    if not user or user not in load_users():
        return None
    return user


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """本用户日志流:只推该用户自己的爬虫日志。"""
    user = _ws_user(websocket)
    if not user:
        await websocket.close(code=1008)  # policy violation
        return

    await websocket.accept()
    mgr = get_manager(user)
    mgr.add_ws(websocket)

    try:
        # 先补历史日志
        for log in mgr.logs:
            await websocket.send_json(log.model_dump())

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        mgr.remove_ws(websocket)


@router.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    """本用户状态流。"""
    user = _ws_user(websocket)
    if not user:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    mgr = get_manager(user)
    try:
        while True:
            await websocket.send_json(mgr.get_status())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
