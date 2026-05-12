import asyncio
import time
from dataclasses import dataclass
from typing import Callable, Optional

from playwright.async_api import Page


_BUY_BUTTON_SELECTORS = [
    'button:has-text("立即购买")',
    'button:has-text("立即预订")',
    'button:has-text("立即抢购")',
]

_CONFIRM_BUTTON_SELECTORS = [
    'button:has-text("提交订单")',
    'button:has-text("确认订单")',
]


@dataclass
class GrabResult:
    success: bool
    message: str
    elapsed_ms: float = 0.0


class TicketGrabber:
    def __init__(
        self,
        poll_interval_ms: int = 50,
        max_retries: int = 3,
        retry_interval_ms: int = 500,
        confirm_timeout_ms: int = 5000,
    ):
        self.poll_interval_ms = poll_interval_ms
        self.max_retries = max_retries
        self.retry_interval_ms = retry_interval_ms
        self.confirm_timeout_ms = confirm_timeout_ms

    async def click_buy(self, page: Page) -> bool:
        for attempt in range(self.max_retries):
            for selector in _BUY_BUTTON_SELECTORS:
                try:
                    button = await page.wait_for_selector(
                        selector, timeout=self.poll_interval_ms, state="visible"
                    )
                    if button and await button.is_enabled():
                        await button.click()
                        return True
                except (TimeoutError, Exception):
                    continue
            await asyncio.sleep(self.retry_interval_ms / 1000)
        return False

    async def click_confirm(self, page: Page) -> bool:
        for selector in _CONFIRM_BUTTON_SELECTORS:
            try:
                button = await page.wait_for_selector(
                    selector, timeout=self.confirm_timeout_ms, state="visible"
                )
                if button:
                    await button.click()
                    return True
            except (TimeoutError, Exception):
                continue
        return False

    async def run(
        self,
        page: Page,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> GrabResult:
        log = on_log or (lambda _: None)
        start = time.time()

        log("开始执行抢票 — Step 1: 点击购买按钮")
        buy_ok = await self.click_buy(page)
        if not buy_ok:
            elapsed = (time.time() - start) * 1000
            log("购买按钮点击失败，已达最大重试次数")
            return GrabResult(success=False, message="购买按钮点击失败", elapsed_ms=elapsed)

        buy_elapsed = (time.time() - start) * 1000
        log(f"购买按钮点击成功 (耗时 {buy_elapsed:.0f}ms) — Step 2: 等待确认订单页面")

        confirm_ok = await self.click_confirm(page)
        elapsed = (time.time() - start) * 1000
        if not confirm_ok:
            log("提交订单按钮点击失败")
            return GrabResult(success=False, message="提交订单按钮点击失败", elapsed_ms=elapsed)

        log(f"提交订单成功！总耗时 {elapsed:.0f}ms，请在浏览器中完成支付")
        return GrabResult(success=True, message="抢票成功，请完成支付", elapsed_ms=elapsed)
