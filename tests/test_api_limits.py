# -*- coding: utf-8 -*-
import pytest
import config
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from cmd_arg import parse_cmd
from api.schemas import CrawlerStartRequest, PlatformEnum, LoginTypeEnum, CrawlerTypeEnum
from api.services.crawler_manager import CrawlerManager
from api.main import app
from api.auth import require_user


@pytest.fixture(autouse=True)
def _logged_in():
    """全部 /api 都要登录;测试里直接把当前用户固定为 tester。"""
    app.dependency_overrides[require_user] = lambda: "tester"
    yield
    app.dependency_overrides.pop(require_user, None)


def _patch_manager():
    """替换每用户的 CrawlerManager,只记录 start 的入参,不起真爬虫。"""
    mgr = MagicMock()
    mgr.start = AsyncMock(return_value=True)
    return patch("api.routers.crawler.get_manager", return_value=mgr), mgr

@pytest.mark.asyncio
async def test_cmd_arg_crawler_max_notes_count():
    # Store original values
    orig_notes = config.CRAWLER_MAX_NOTES_COUNT
    orig_comments = config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES

    try:
        await parse_cmd([
            "--platform", "xhs",
            "--crawler_max_notes_count", "42",
            "--max_comments_count_singlenotes", "24"
        ])
        assert config.CRAWLER_MAX_NOTES_COUNT == 42
        assert config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES == 24
    finally:
        config.CRAWLER_MAX_NOTES_COUNT = orig_notes
        config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = orig_comments

def test_crawler_manager_build_command():
    cm = CrawlerManager()

    # 1. No max limits passed in API request
    req1 = CrawlerStartRequest(
        platform=PlatformEnum.XHS,
        login_type=LoginTypeEnum.QRCODE,
        crawler_type=CrawlerTypeEnum.SEARCH,
        keywords="test",
        max_notes_count=None,
        max_comments_count=None
    )
    cmd1 = cm._build_command(req1)
    # Check that the custom arguments are NOT present
    assert "--crawler_max_notes_count" not in cmd1
    assert "--max_comments_count_singlenotes" not in cmd1

    # 2. Both limits passed in API request
    req2 = CrawlerStartRequest(
        platform=PlatformEnum.XHS,
        login_type=LoginTypeEnum.QRCODE,
        crawler_type=CrawlerTypeEnum.SEARCH,
        keywords="test",
        max_notes_count=50,
        max_comments_count=5
    )
    cmd2 = cm._build_command(req2)
    # Check that they are correctly added
    assert "--crawler_max_notes_count" in cmd2
    idx_notes = cmd2.index("--crawler_max_notes_count")
    assert cmd2[idx_notes + 1] == "50"

    assert "--max_comments_count_singlenotes" in cmd2
    idx_comments = cmd2.index("--max_comments_count_singlenotes")
    assert cmd2[idx_comments + 1] == "5"

def test_api_start_crawler_with_limits():
    client = TestClient(app)

    patcher, mgr = _patch_manager()
    with patcher:
        mock_start = mgr.start

        # Test case 1: with limits
        response = client.post("/api/crawler/start", json={
            "platform": "xhs",
            "login_type": "qrcode",
            "crawler_type": "search",
            "keywords": "test",
            "max_notes_count": 50,
            "max_comments_count": 5
        })

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "message": "任务已启动"}

        mock_start.assert_called_once()
        called_request = mock_start.call_args[0][0]
        assert called_request.platform == PlatformEnum.XHS
        assert called_request.max_notes_count == 50
        assert called_request.max_comments_count == 5

def test_api_start_crawler_without_limits():
    client = TestClient(app)

    patcher, mgr = _patch_manager()
    with patcher:
        mock_start = mgr.start

        # Test case 2: without limits
        response = client.post("/api/crawler/start", json={
            "platform": "xhs",
            "login_type": "qrcode",
            "crawler_type": "search",
            "keywords": "test"
        })

        assert response.status_code == 200
        mock_start.assert_called_once()
        called_request = mock_start.call_args[0][0]
        assert called_request.platform == PlatformEnum.XHS
        assert called_request.max_notes_count is None
        assert called_request.max_comments_count is None


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("max_notes_count", 0),
        ("max_notes_count", -1),
        ("max_notes_count", 10001),
        ("max_comments_count", 0),
        ("max_comments_count", -1),
        ("max_comments_count", 10001),
    ],
)
def test_api_rejects_invalid_limits(field_name, value):
    client = TestClient(app)
    payload = {
        "platform": "xhs",
        "login_type": "qrcode",
        "crawler_type": "search",
        "keywords": "test",
        field_name: value,
    }

    patcher, mgr = _patch_manager()
    with patcher:
        response = client.post("/api/crawler/start", json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    mgr.start.assert_not_called()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"crawler_type": "search", "keywords": " , "}, "搜索模式需要至少一个关键词"),
        ({"crawler_type": "detail", "specified_ids": "\n "}, "详情模式需要至少一个帖子/视频 ID"),
        ({"crawler_type": "creator"}, "创作者模式需要至少一个创作者 ID"),
        ({"crawler_type": "search", "keywords": "a", "crawl_interval": 61}, "每条间隔秒不能大于 60"),
    ],
)
def test_api_rejects_missing_mode_inputs(payload, message):
    client = TestClient(app)
    patcher, mgr = _patch_manager()
    with patcher:
        response = client.post("/api/crawler/start", json={"platform": "xhs", **payload})
    assert response.status_code == 422
    assert response.json() == {"detail": message}
    mgr.start.assert_not_called()


def test_request_normalizes_ids_and_keywords():
    req = CrawlerStartRequest(platform=PlatformEnum.BILIBILI, crawler_type=CrawlerTypeEnum.DETAIL,
                              specified_ids="BV1\nBV2, BV3，BV4")
    assert req.specified_ids == "BV1,BV2,BV3,BV4"
    req = CrawlerStartRequest(platform=PlatformEnum.BILIBILI, keywords="猫，狗,猫")
    assert req.keywords == "猫,狗"
