import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.grabber import TicketGrabber, GrabResult


class TestClickBuy:
    @pytest.mark.asyncio
    async def test_click_buy_success(self):
        grabber = TicketGrabber(poll_interval_ms=10, max_retries=1, retry_interval_ms=10, confirm_timeout_ms=1000)
        page = AsyncMock()
        button = AsyncMock()
        button.is_enabled = AsyncMock(return_value=True)
        page.locator.return_value = button
        page.wait_for_selector = AsyncMock(return_value=button)

        result = await grabber.click_buy(page)
        assert result is True
        button.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_click_buy_retries_on_timeout(self):
        grabber = TicketGrabber(poll_interval_ms=10, max_retries=2, retry_interval_ms=10, confirm_timeout_ms=1000)
        page = AsyncMock()

        call_count = 0

        async def mock_wait(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("not found")
            btn = AsyncMock()
            btn.is_enabled = AsyncMock(return_value=True)
            return btn

        page.wait_for_selector = mock_wait

        result = await grabber.click_buy(page)
        assert result is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_click_buy_fails_after_max_retries(self):
        grabber = TicketGrabber(poll_interval_ms=10, max_retries=2, retry_interval_ms=10, confirm_timeout_ms=1000)
        page = AsyncMock()
        page.wait_for_selector = AsyncMock(side_effect=TimeoutError("not found"))

        result = await grabber.click_buy(page)
        assert result is False


class TestClickConfirm:
    @pytest.mark.asyncio
    async def test_click_confirm_success(self):
        grabber = TicketGrabber(poll_interval_ms=10, max_retries=1, retry_interval_ms=10, confirm_timeout_ms=1000)
        page = AsyncMock()
        button = AsyncMock()
        page.wait_for_selector = AsyncMock(return_value=button)

        result = await grabber.click_confirm(page)
        assert result is True
        button.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_click_confirm_timeout(self):
        grabber = TicketGrabber(poll_interval_ms=10, max_retries=1, retry_interval_ms=10, confirm_timeout_ms=100)
        page = AsyncMock()
        page.wait_for_selector = AsyncMock(side_effect=TimeoutError("timeout"))

        result = await grabber.click_confirm(page)
        assert result is False


class TestRunGrab:
    @pytest.mark.asyncio
    async def test_run_returns_success_when_both_steps_pass(self):
        grabber = TicketGrabber(poll_interval_ms=10, max_retries=1, retry_interval_ms=10, confirm_timeout_ms=1000)
        page = AsyncMock()
        button = AsyncMock()
        button.is_enabled = AsyncMock(return_value=True)
        page.wait_for_selector = AsyncMock(return_value=button)

        logs: list[str] = []
        result = await grabber.run(page, on_log=logs.append)
        assert result.success is True
        assert any("购买" in msg for msg in logs)

    @pytest.mark.asyncio
    async def test_run_returns_failure_when_buy_fails(self):
        grabber = TicketGrabber(poll_interval_ms=10, max_retries=1, retry_interval_ms=10, confirm_timeout_ms=1000)
        page = AsyncMock()
        page.wait_for_selector = AsyncMock(side_effect=TimeoutError("not found"))

        result = await grabber.run(page, on_log=lambda _: None)
        assert result.success is False
        assert "购买" in result.message
