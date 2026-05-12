import sys
import platform
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from core.browser import BrowserManager


class TestDetectChromePath:
    def test_custom_path_returned_as_is(self):
        bm = BrowserManager(debug_port=9222, chrome_path="/custom/chrome")
        assert bm.chrome_path == "/custom/chrome"

    def test_auto_detect_macos(self):
        with patch(
            "core.browser._detect_chrome_path",
            return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ):
            bm = BrowserManager(debug_port=9222, chrome_path="")
            assert "Google Chrome" in bm.chrome_path


class TestBuildLaunchCommand:
    def test_command_includes_debug_port(self):
        bm = BrowserManager(debug_port=9333, chrome_path="/usr/bin/chrome")
        cmd = bm.build_launch_command()
        assert "--remote-debugging-port=9333" in cmd

    def test_command_includes_chrome_path(self):
        bm = BrowserManager(debug_port=9222, chrome_path="/my/chrome")
        cmd = bm.build_launch_command()
        assert cmd[0] == "/my/chrome"


class TestCDPUrl:
    def test_cdp_url_format(self):
        bm = BrowserManager(debug_port=9222, chrome_path="/chrome")
        assert bm.cdp_url == "http://localhost:9222"

    def test_cdp_url_custom_port(self):
        bm = BrowserManager(debug_port=9999, chrome_path="/chrome")
        assert bm.cdp_url == "http://localhost:9999"


@pytest.mark.asyncio
class TestConnectAndFindPage:
    async def test_get_damai_page_finds_matching_url(self):
        bm = BrowserManager(debug_port=9222, chrome_path="/chrome")

        mock_page_other = MagicMock()
        mock_page_other.url = "https://www.google.com"
        mock_page_damai = MagicMock()
        mock_page_damai.url = "https://m.damai.cn/shows/detail.html?id=123"

        mock_context = MagicMock()
        mock_context.pages = [mock_page_other, mock_page_damai]
        mock_browser = MagicMock()
        mock_browser.contexts = [mock_context]

        bm._browser = mock_browser
        page = bm.get_damai_page()
        assert page.url == mock_page_damai.url

    async def test_get_damai_page_returns_none_if_not_found(self):
        bm = BrowserManager(debug_port=9222, chrome_path="/chrome")

        mock_page = MagicMock()
        mock_page.url = "https://www.google.com"
        mock_context = MagicMock()
        mock_context.pages = [mock_page]
        mock_browser = MagicMock()
        mock_browser.contexts = [mock_context]

        bm._browser = mock_browser
        page = bm.get_damai_page()
        assert page is None
