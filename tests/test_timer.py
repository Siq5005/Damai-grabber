import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from core.timer import NTPTimer


class TestNTPSync:
    def test_sync_sets_offset(self):
        timer = NTPTimer(servers=["ntp.aliyun.com"], timeout=1)
        mock_response = MagicMock()
        mock_response.offset = 0.123
        with patch("core.timer.ntplib.NTPClient") as mock_client_cls:
            mock_client_cls.return_value.request.return_value = mock_response
            offset = timer.sync()
        assert offset == 0.123
        assert timer.offset == 0.123

    def test_sync_tries_fallback_servers(self):
        timer = NTPTimer(servers=["bad1", "bad2", "good"], timeout=1)
        mock_response = MagicMock()
        mock_response.offset = 0.456

        call_count = 0

        def side_effect(server, version=3, timeout=1):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("timeout")
            return mock_response

        with patch("core.timer.ntplib.NTPClient") as mock_client_cls:
            mock_client_cls.return_value.request.side_effect = side_effect
            offset = timer.sync()

        assert offset == 0.456
        assert call_count == 3

    def test_sync_all_fail_returns_zero(self):
        timer = NTPTimer(servers=["bad1", "bad2"], timeout=1)
        with patch("core.timer.ntplib.NTPClient") as mock_client_cls:
            mock_client_cls.return_value.request.side_effect = Exception("timeout")
            offset = timer.sync()
        assert offset == 0.0
        assert timer.offset == 0.0


class TestNTPNow:
    def test_now_applies_offset(self):
        timer = NTPTimer(servers=[], timeout=1)
        timer.offset = 1.5
        before = time.time() + 1.5
        result = timer.now()
        after = time.time() + 1.5
        assert before <= result <= after


class TestWaitUntil:
    def test_wait_until_past_returns_immediately(self):
        timer = NTPTimer(servers=[], timeout=1)
        timer.offset = 0.0
        past = time.time() - 1.0
        start = time.time()
        timer.wait_until(past)
        elapsed = time.time() - start
        assert elapsed < 0.1

    def test_wait_until_short_future(self):
        timer = NTPTimer(servers=[], timeout=1)
        timer.offset = 0.0
        target = time.time() + 0.2
        timer.wait_until(target)
        elapsed = timer.now() - target
        assert -0.05 <= elapsed <= 0.05
