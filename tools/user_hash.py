# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# 本文件为 MediaCrawler 教学版的一部分。
# 出于教学与防骚扰定位，爬取结果中不保留任何可定位到真人的用户个人信息
# （用户 ID、IP 归属地、头像、主页链接、签名、性别等一律不采集；
# 昵称保留但做中间脱敏）。本模块提供匿名化与脱敏工具。
import hashlib
import os

# 默认脱敏(教学版隐私保护);env MC_ANONYMIZE=0 关闭 → 存真实 user_id / 昵称(对标真实博主用)
_ANON = os.environ.get("MC_ANONYMIZE", "1") == "1"


def anonymize_user_id(user_id) -> str:
    """把原始用户 ID 转成匿名哈希；MC_ANONYMIZE=0 时直接返回真实 user_id。"""
    if user_id is None:
        return ""
    s = str(user_id).strip()
    if not s:
        return ""
    if not _ANON:
        return s
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def mask_nickname(name) -> str:
    """昵称中间脱敏：首尾各保留 1 字，中间替换为星号。
    - 长度 <= 1：返回 "*"
    - 长度 == 2：首字 + "*"
    - 长度 >= 3：首字 + "***" + 尾字
    这样既保留教学分析所需的内容归属语义，又无法据昵称定位到真人。
    """
    if name is None:
        return ""
    s = str(name)
    if not _ANON:
        return s
    if len(s) <= 1:
        return "*"
    if len(s) == 2:
        return s[0] + "*"
    return s[0] + "***" + s[-1]
