import platform
import subprocess
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page


_CHROME_PATHS = {
    "Darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ],
    "Linux": [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ],
    "Windows": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
}

_DAMAI_URL_PATTERNS = ["damai.cn", "m.damai.cn"]


def _detect_chrome_path() -> str:
    system = platform.system()
    for path in _CHROME_PATHS.get(system, []):
        if Path(path).exists():
            return path
    return ""


class BrowserManager:
    def __init__(self, debug_port: int, chrome_path: str = ""):
        self.debug_port = debug_port
        self.chrome_path = chrome_path or _detect_chrome_path()
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._process: Optional[subprocess.Popen] = None

    @property
    def cdp_url(self) -> str:
        return f"http://localhost:{self.debug_port}"

    def build_launch_command(self) -> list:
        return [
            self.chrome_path,
            f"--remote-debugging-port={self.debug_port}",
        ]

    def launch_browser(self) -> subprocess.Popen:
        cmd = self.build_launch_command()
        self._process = subprocess.Popen(cmd)
        return self._process

    async def connect(self) -> Browser:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)
        return self._browser

    def get_damai_page(self) -> Optional[Page]:
        if not self._browser:
            return None
        for context in self._browser.contexts:
            for page in context.pages:
                if any(pattern in page.url for pattern in _DAMAI_URL_PATTERNS):
                    return page
        return None

    def is_connected(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
