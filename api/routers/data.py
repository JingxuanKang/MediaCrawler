# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/routers/data.py
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

import os
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse

from ..auth import require_user

router = APIRouter(prefix="/data", tags=["data"])

# 全部数据根;每个登录用户只看自己 <root>/<用户>/ 这一子树。
# MC_DATA_ROOT 可指 NAS 挂载(如 /mnt/mc-nas),与爬虫落盘保持一致;默认项目本地 data/。
_mc_root = os.environ.get("MC_DATA_ROOT")
DATA_DIR = Path(_mc_root) if _mc_root else (Path(__file__).parent.parent.parent / "data")


def _user_dir(user: str) -> Path:
    """本用户数据子树。用户名已在建号时校验过(仅小写字母数字下划线连字符)。"""
    return DATA_DIR / user


def get_file_info(file_path: Path, base_dir: Path) -> dict:
    """Get file information (path 相对 base_dir)"""
    stat = file_path.stat()
    record_count = None
    try:
        if file_path.suffix == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    record_count = len(data)
        elif file_path.suffix == ".csv":
            with open(file_path, "r", encoding="utf-8") as f:
                record_count = sum(1 for _ in f) - 1
    except Exception:
        pass

    return {
        "name": file_path.name,
        "path": str(file_path.relative_to(base_dir)),
        "size": stat.st_size,
        "modified_at": stat.st_mtime,
        "record_count": record_count,
        "type": file_path.suffix[1:] if file_path.suffix else "unknown",
    }


def _resolve_in_user_dir(user: str, file_path: str) -> Path:
    """把用户给的相对路径解析到其 data/<用户>/ 内,越界即 403。"""
    base = _user_dir(user)
    full = (base / file_path)
    try:
        full.resolve().relative_to(base.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    return full


@router.get("/files")
async def list_data_files(platform: Optional[str] = None, file_type: Optional[str] = None,
                          user: str = Depends(require_user)):
    """Get data file list(仅本用户)"""
    base = _user_dir(user)
    if not base.exists():
        return {"files": []}

    files = []
    supported_extensions = {".json", ".csv", ".xlsx", ".xls"}

    for root, dirs, filenames in os.walk(base):
        root_path = Path(root)
        for filename in filenames:
            file_path = root_path / filename
            if file_path.suffix.lower() not in supported_extensions:
                continue

            if platform:
                rel_path = str(file_path.relative_to(base))
                if platform.lower() not in rel_path.lower():
                    continue

            if file_type and file_path.suffix[1:].lower() != file_type.lower():
                continue

            try:
                files.append(get_file_info(file_path, base))
            except Exception:
                continue

    files.sort(key=lambda x: x["modified_at"], reverse=True)
    return {"files": files}


@router.get("/files/{file_path:path}")
async def get_file_content(file_path: str, preview: bool = True, limit: int = 100,
                           user: str = Depends(require_user)):
    """Get file content or preview(仅本用户)"""
    full_path = _resolve_in_user_dir(user, file_path)

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    if preview:
        try:
            if full_path.suffix == ".json":
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return {"data": data[:limit], "total": len(data)}
                    return {"data": data, "total": 1}
            elif full_path.suffix == ".csv":
                import csv
                with open(full_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = []
                    for i, row in enumerate(reader):
                        if i >= limit:
                            break
                        rows.append(row)
                    f.seek(0)
                    total = sum(1 for _ in f) - 1
                    return {"data": rows, "total": total}
            elif full_path.suffix.lower() in (".xlsx", ".xls"):
                import pandas as pd
                df = pd.read_excel(full_path, nrows=limit)
                df_count = pd.read_excel(full_path, usecols=[0])
                total = len(df_count)
                rows = df.where(pd.notnull(df), None).to_dict(orient="records")
                return {"data": rows, "total": total, "columns": list(df.columns)}
            else:
                raise HTTPException(status_code=400, detail="Unsupported file type for preview")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        return FileResponse(path=full_path, filename=full_path.name,
                            media_type="application/octet-stream")


@router.get("/download/{file_path:path}")
async def download_file(file_path: str, user: str = Depends(require_user)):
    """Download file(仅本用户)"""
    full_path = _resolve_in_user_dir(user, file_path)

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    return FileResponse(path=full_path, filename=full_path.name,
                        media_type="application/octet-stream")


@router.get("/stats")
async def get_data_stats(user: str = Depends(require_user)):
    """Get data statistics(仅本用户)"""
    base = _user_dir(user)
    if not base.exists():
        return {"total_files": 0, "total_size": 0, "by_platform": {}, "by_type": {}}

    stats = {"total_files": 0, "total_size": 0, "by_platform": {}, "by_type": {}}
    supported_extensions = {".json", ".csv", ".xlsx", ".xls"}

    for root, dirs, filenames in os.walk(base):
        root_path = Path(root)
        for filename in filenames:
            file_path = root_path / filename
            if file_path.suffix.lower() not in supported_extensions:
                continue
            try:
                stat = file_path.stat()
                stats["total_files"] += 1
                stats["total_size"] += stat.st_size

                file_type = file_path.suffix[1:].lower()
                stats["by_type"][file_type] = stats["by_type"].get(file_type, 0) + 1

                rel_path = str(file_path.relative_to(base))
                for platform in ["xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"]:
                    if platform in rel_path.lower():
                        stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1
                        break
            except Exception:
                continue

    return stats
