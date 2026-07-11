# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/services/crawler_manager.py
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
import subprocess
import signal
import os
import re
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from ..schemas import CrawlerStartRequest, LogEntry


def _safe_seg(name: str) -> str:
    """路径段清洗(用户名/账号):只留字母数字下划线连字符,防路径穿越,截断 64。"""
    return re.sub(r"[^0-9A-Za-z_\-]", "_", (name or "").strip())[:64]


# 走 CDP(连 chrome.jingxuan.uk 的 Selkies Chromium:localhost:9222)的用户白名单;其他用户照旧各自 headless。
# 逗号分隔环境变量 MC_CDP_USERS 覆盖(默认只 jingxuan)。
CDP_USERS = set(
    u.strip().lower() for u in os.environ.get("MC_CDP_USERS", "jingxuan").split(",") if u.strip()
)


class CrawlerManager:
    """每个登录用户一个实例:各自独立的进程/日志/状态/WebSocket 订阅。"""

    def __init__(self, user: str = "_default"):
        self.user = _safe_seg(user) or "_default"
        self._lock = asyncio.Lock()
        self.process: Optional[subprocess.Popen] = None
        self.status = "idle"
        self.started_at: Optional[datetime] = None
        self.current_config: Optional[CrawlerStartRequest] = None
        self._log_id = 0
        self._logs: List[LogEntry] = []
        self._read_task: Optional[asyncio.Task] = None
        self._project_root = Path(__file__).parent.parent.parent
        # 本用户的 WebSocket 日志订阅连接(每连接直推,不走全局广播 → 用户间不串号)
        self._ws_connections: set = set()

    @property
    def logs(self) -> List[LogEntry]:
        return self._logs

    def add_ws(self, ws) -> None:
        self._ws_connections.add(ws)

    def remove_ws(self, ws) -> None:
        self._ws_connections.discard(ws)

    def _create_log_entry(self, message: str, level: str = "info") -> LogEntry:
        self._log_id += 1
        entry = LogEntry(
            id=self._log_id,
            timestamp=datetime.now().strftime("%H:%M:%S"),
            level=level,
            message=message,
        )
        self._logs.append(entry)
        if len(self._logs) > 500:
            self._logs = self._logs[-500:]
        return entry

    async def _push_log(self, entry: LogEntry):
        """直推给本用户的所有 WS 连接;清理断开的。"""
        if not self._ws_connections:
            return
        payload = entry.model_dump()
        dead = []
        for ws in list(self._ws_connections):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_connections.discard(ws)

    def _parse_log_level(self, line: str) -> str:
        line_upper = line.upper()
        if "ERROR" in line_upper or "FAILED" in line_upper:
            return "error"
        elif "WARNING" in line_upper or "WARN" in line_upper:
            return "warning"
        elif "SUCCESS" in line_upper or "完成" in line or "成功" in line:
            return "success"
        elif "DEBUG" in line_upper:
            return "debug"
        return "info"

    def _data_path(self, config: CrawlerStartRequest) -> str:
        """本用户数据根 data/<用户>/;若填了账号/数据集再套一层 data/<用户>/<账号>/。"""
        base = f"data/{self.user}"
        acct = _safe_seg(getattr(config, "account", ""))
        return f"{base}/{acct}" if acct else base

    def qr_file(self):
        """扫码登录时二维码 PNG 落点(本用户根,不进子数据集)。"""
        return self._project_root / "data" / self.user / "_qr.png"

    async def start(self, config: CrawlerStartRequest) -> bool:
        async with self._lock:
            if self.process and self.process.poll() is None:
                return False

            self._logs = []
            self._log_id = 0

            # 清掉上一轮的二维码,避免前端扫到过期码
            try:
                self.qr_file().unlink(missing_ok=True)
            except Exception:
                pass

            cmd = self._build_command(config)

            entry = self._create_log_entry(f"Starting crawler: {' '.join(cmd)}", "info")
            await self._push_log(entry)

            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    bufsize=1,
                    cwd=str(self._project_root),
                    env={
                        **os.environ,
                        "PYTHONUNBUFFERED": "1",
                        # 按登录用户分区:数据落 data/<用户>[/<账号>]/,base_config 读该环境变量
                        "MC_SAVE_DATA_PATH": self._data_path(config),
                        # 扫码登录:无头浏览器把二维码写到这个 PNG,前端拉去显示
                        "MC_QR_PATH": f"data/{self.user}/_qr.png",
                        # 白名单用户走 CDP:连 chrome.jingxuan.uk 的 Selkies Chromium(localhost:9222),真实指纹低风控
                        **({"MC_CDP": "1"} if self.user in CDP_USERS else {}),
                    },
                )

                self.status = "running"
                self.started_at = datetime.now()
                self.current_config = config

                entry = self._create_log_entry(
                    f"Crawler started on platform: {config.platform.value}, type: {config.crawler_type.value}",
                    "success",
                )
                await self._push_log(entry)

                self._read_task = asyncio.create_task(self._read_output())
                return True
            except Exception as e:
                self.status = "error"
                entry = self._create_log_entry(f"Failed to start crawler: {str(e)}", "error")
                await self._push_log(entry)
                return False

    async def stop(self) -> bool:
        async with self._lock:
            if not self.process or self.process.poll() is not None:
                return False

            self.status = "stopping"
            entry = self._create_log_entry("Sending SIGTERM to crawler process...", "warning")
            await self._push_log(entry)

            try:
                self.process.send_signal(signal.SIGTERM)
                for _ in range(30):
                    if self.process.poll() is not None:
                        break
                    await asyncio.sleep(0.5)
                if self.process.poll() is None:
                    entry = self._create_log_entry("Process not responding, sending SIGKILL...", "warning")
                    await self._push_log(entry)
                    self.process.kill()
                entry = self._create_log_entry("Crawler process terminated", "info")
                await self._push_log(entry)
            except Exception as e:
                entry = self._create_log_entry(f"Error stopping crawler: {str(e)}", "error")
                await self._push_log(entry)

            self.status = "idle"
            self.current_config = None
            if self._read_task:
                self._read_task.cancel()
                self._read_task = None
            return True

    def get_status(self) -> dict:
        return {
            "status": self.status,
            "platform": self.current_config.platform.value if self.current_config else None,
            "crawler_type": self.current_config.crawler_type.value if self.current_config else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "error_message": None,
        }

    def _build_command(self, config: CrawlerStartRequest) -> list:
        cmd = ["uv", "run", "python", "main.py"]
        cmd.extend(["--platform", config.platform.value])
        cmd.extend(["--lt", config.login_type.value])
        cmd.extend(["--type", config.crawler_type.value])
        cmd.extend(["--save_data_option", config.save_option.value])

        if config.crawler_type.value == "search" and config.keywords:
            cmd.extend(["--keywords", config.keywords])
        elif config.crawler_type.value == "detail" and config.specified_ids:
            cmd.extend(["--specified_id", config.specified_ids])
        elif config.crawler_type.value == "creator" and config.creator_ids:
            cmd.extend(["--creator_id", config.creator_ids])

        if config.start_page != 1:
            cmd.extend(["--start", str(config.start_page)])

        cmd.extend(["--get_comment", "true" if config.enable_comments else "false"])
        cmd.extend(["--get_sub_comment", "true" if config.enable_sub_comments else "false"])

        if config.max_notes_count is not None:
            cmd.extend(["--crawler_max_notes_count", str(config.max_notes_count)])
        if config.max_comments_count is not None:
            cmd.extend(["--max_comments_count_singlenotes", str(config.max_comments_count)])
        if config.cookies:
            cmd.extend(["--cookies", config.cookies])

        # 服务器无 X server(显示器),有头浏览器必崩;二维码已可在网页扫,无需有头 → 强制无头
        cmd.extend(["--headless", "true"])
        return cmd

    async def _read_output(self):
        loop = asyncio.get_event_loop()
        try:
            while self.process and self.process.poll() is None:
                line = await loop.run_in_executor(None, self.process.stdout.readline)
                if line:
                    line = line.strip()
                    if line:
                        entry = self._create_log_entry(line, self._parse_log_level(line))
                        await self._push_log(entry)

            if self.process and self.process.stdout:
                remaining = await loop.run_in_executor(None, self.process.stdout.read)
                if remaining:
                    for line in remaining.strip().split("\n"):
                        if line.strip():
                            entry = self._create_log_entry(line.strip(), self._parse_log_level(line))
                            await self._push_log(entry)

            if self.status == "running":
                exit_code = self.process.returncode if self.process else -1
                if exit_code == 0:
                    entry = self._create_log_entry("Crawler completed successfully", "success")
                else:
                    entry = self._create_log_entry(f"Crawler exited with code: {exit_code}", "warning")
                await self._push_log(entry)
                self.status = "idle"

        except asyncio.CancelledError:
            pass
        except Exception as e:
            entry = self._create_log_entry(f"Error reading output: {str(e)}", "error")
            await self._push_log(entry)


# ---------- 每用户实例注册表 ----------
_managers: dict = {}


def get_manager(user: str) -> CrawlerManager:
    key = _safe_seg(user) or "_default"
    mgr = _managers.get(key)
    if mgr is None:
        mgr = CrawlerManager(key)
        _managers[key] = mgr
    return mgr


# 兼容旧 import(未登录场景不会用到)
crawler_manager = get_manager("_default")
