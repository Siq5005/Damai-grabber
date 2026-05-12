import asyncio
import time
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.timer import NTPTimer
from core.grabber import TicketGrabber, GrabResult


class GrabWorker(QThread):
    log_message = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    countdown_tick = pyqtSignal(float)
    grab_finished = pyqtSignal(bool, str)

    def __init__(
        self,
        cdp_url: str,
        target_time: datetime,
        ntp_servers: list,
        ntp_timeout: int,
        grab_config: dict,
    ):
        super().__init__()
        self.cdp_url = cdp_url
        self.target_timestamp = target_time.timestamp()
        self.ntp_servers = ntp_servers
        self.ntp_timeout = ntp_timeout
        self.grab_config = grab_config
        self._stop_flag = False

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._execute())
        except Exception as e:
            self.grab_finished.emit(False, f"异常: {e}")
        finally:
            loop.close()

    async def _execute(self):
        self.status_changed.emit("正在同步NTP时间...")
        timer = NTPTimer(servers=self.ntp_servers, timeout=self.ntp_timeout)
        offset = timer.sync()
        if offset == 0.0 and self.ntp_servers:
            self.log_message.emit("警告: NTP校时失败，使用本地时间")
        else:
            self.log_message.emit(f"NTP校时完成，偏移量: {offset*1000:.1f}ms")

        self.status_changed.emit("正在连接浏览器...")
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.connect_over_cdp(self.cdp_url)
        except Exception as e:
            self.grab_finished.emit(False, f"浏览器连接失败: {e}")
            await pw.stop()
            return

        page = None
        for ctx in browser.contexts:
            for p in ctx.pages:
                if "damai.cn" in p.url:
                    page = p
                    break
            if page:
                break

        if not page:
            self.grab_finished.emit(False, "未找到大麦网页面，请在浏览器中打开大麦网")
            await browser.close()
            await pw.stop()
            return

        self.log_message.emit(f"已连接到页面: {page.url}")

        try:
            from playwright_stealth import stealth_async
            await stealth_async(page)
            self.log_message.emit("stealth 注入完成")
        except ImportError:
            self.log_message.emit("playwright-stealth 未安装，跳过 stealth 注入")

        self.status_changed.emit("等待开票时间...")
        while not self._stop_flag:
            remaining = self.target_timestamp - timer.now()
            if remaining <= 0:
                break
            self.countdown_tick.emit(remaining)
            if remaining > 1.0:
                await asyncio.sleep(0.1)
            else:
                await asyncio.sleep(0.01)

        if self._stop_flag:
            self.grab_finished.emit(False, "用户手动停止")
            await browser.close()
            await pw.stop()
            return

        self.status_changed.emit("抢票中...")
        grabber = TicketGrabber(
            poll_interval_ms=self.grab_config.get("poll_interval_ms", 50),
            max_retries=self.grab_config.get("max_retries", 3),
            retry_interval_ms=self.grab_config.get("retry_interval_ms", 500),
            confirm_timeout_ms=self.grab_config.get("confirm_timeout_ms", 5000),
        )

        result: GrabResult = await grabber.run(
            page, on_log=lambda msg: self.log_message.emit(msg)
        )

        self.grab_finished.emit(result.success, result.message)
        await browser.close()
        await pw.stop()

    def stop(self):
        self._stop_flag = True
