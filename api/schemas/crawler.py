# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/schemas/crawler.py
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

import re
from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


MAX_API_LIMIT_COUNT = 10000
MAX_KEYWORDS = 20          # 一次搜索最多几个关键词
MAX_KEYWORD_LEN = 50       # 单个关键词最长字数
MAX_IDS_TEXT_LEN = 20000   # 详情/创作者 ID 文本框最长字数


def _split_ids(text: str) -> list:
    """ID/URL 列表:前端允许换行、空白或中英文逗号分隔;命令行只认英文逗号。"""
    return [x for x in re.split(r"[,，\s]+", text or "") if x]


class PlatformEnum(str, Enum):
    """Supported media platforms"""
    XHS = "xhs"
    DOUYIN = "dy"
    KUAISHOU = "ks"
    BILIBILI = "bili"
    WEIBO = "wb"
    TIEBA = "tieba"
    ZHIHU = "zhihu"


class LoginTypeEnum(str, Enum):
    """Login method"""
    QRCODE = "qrcode"
    PHONE = "phone"
    COOKIE = "cookie"


class CrawlerTypeEnum(str, Enum):
    """Crawler type"""
    SEARCH = "search"
    DETAIL = "detail"
    CREATOR = "creator"


class SaveDataOptionEnum(str, Enum):
    """Data save option"""
    CSV = "csv"
    DB = "db"
    JSON = "json"
    JSONL = "jsonl"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    EXCEL = "excel"


class CrawlerStartRequest(BaseModel):
    """Crawler start request"""
    platform: PlatformEnum
    login_type: LoginTypeEnum = LoginTypeEnum.QRCODE
    crawler_type: CrawlerTypeEnum = CrawlerTypeEnum.SEARCH
    keywords: str = ""  # Keywords for search mode
    specified_ids: str = ""  # Post/video ID list for detail mode, comma-separated
    creator_ids: str = ""  # Creator ID list for creator mode, comma-separated
    start_page: int = Field(default=1, ge=1, le=1000)
    enable_comments: bool = True
    enable_sub_comments: bool = False
    save_option: SaveDataOptionEnum = SaveDataOptionEnum.JSONL
    cookies: str = ""
    account: str = ""  # 账号/数据集名 → 数据分区落 data/<account>/;留空进公共 data/
    headless: bool = False
    max_notes_count: Optional[int] = Field(default=None, ge=1, le=MAX_API_LIMIT_COUNT)
    max_comments_count: Optional[int] = Field(default=None, ge=1, le=MAX_API_LIMIT_COUNT)
    crawl_interval: Optional[int] = Field(default=None, ge=0, le=60)  # 每条抓取间隔秒(悠着抓)

    @model_validator(mode="after")
    def _check_mode_inputs(self):
        """按爬取类型检查必填项。留空会让爬虫回落到 config 里的默认关键词/ID,结果不是用户要的。"""
        if self.crawler_type == CrawlerTypeEnum.SEARCH:
            kws = [k.strip() for k in self.keywords.replace("，", ",").split(",") if k.strip()]
            if not kws:
                raise ValueError("搜索模式需要至少一个关键词")
            if len(kws) > MAX_KEYWORDS:
                raise ValueError(f"关键词最多 {MAX_KEYWORDS} 个")
            if any(len(k) > MAX_KEYWORD_LEN for k in kws):
                raise ValueError(f"单个关键词最多 {MAX_KEYWORD_LEN} 字")
            self.keywords = ",".join(dict.fromkeys(kws))
        elif self.crawler_type == CrawlerTypeEnum.DETAIL:
            if len(self.specified_ids) > MAX_IDS_TEXT_LEN:
                raise ValueError("ID 列表过长")
            ids = _split_ids(self.specified_ids)
            if not ids:
                raise ValueError("详情模式需要至少一个帖子/视频 ID")
            self.specified_ids = ",".join(ids)
        elif self.crawler_type == CrawlerTypeEnum.CREATOR:
            if len(self.creator_ids) > MAX_IDS_TEXT_LEN:
                raise ValueError("ID 列表过长")
            ids = _split_ids(self.creator_ids)
            if not ids:
                raise ValueError("创作者模式需要至少一个创作者 ID")
            self.creator_ids = ",".join(ids)
        if len(self.account) > 64:
            raise ValueError("子数据集名最多 64 字")
        return self


class CrawlerStatusResponse(BaseModel):
    """Crawler status response"""
    status: Literal["idle", "running", "stopping", "error"]
    platform: Optional[str] = None
    crawler_type: Optional[str] = None
    started_at: Optional[str] = None
    error_message: Optional[str] = None


class LogEntry(BaseModel):
    """Log entry"""
    id: int
    timestamp: str
    level: Literal["info", "warning", "error", "success", "debug"]
    message: str


class DataFileInfo(BaseModel):
    """Data file information"""
    name: str
    path: str
    size: int
    modified_at: str
    record_count: Optional[int] = None
