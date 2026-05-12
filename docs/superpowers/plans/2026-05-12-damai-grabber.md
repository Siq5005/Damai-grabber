# DamaiGrabber Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a desktop GUI tool that connects to the user's Chrome browser via CDP and automatically clicks "buy" then "confirm order" at ticket release time on Damai (大麦网).

**Architecture:** PyQt6 GUI launches Chrome with `--remote-debugging-port`, a background QThread runs an asyncio event loop driving Playwright to detect and click two buttons at the NTP-synchronized target time. Signals relay status back to the GUI.

**Tech Stack:** Python 3.10+, PyQt6, Playwright (async CDP), playwright-stealth, ntplib

---

## File Map

| File | Responsibility |
|------|---------------|
| `requirements.txt` | Python dependencies |
| `config.json` | Default user configuration (ports, retries, NTP servers) |
| `main.py` | Application entry point |
| `core/__init__.py` | Package init |
| `core/timer.py` | NTP sync + precision wait |
| `core/browser.py` | Launch Chrome, connect via CDP, find Damai page |
| `core/grabber.py` | Two-step grab logic (click buy → click confirm) with retry |
| `gui/__init__.py` | Package init |
| `gui/main_window.py` | PyQt6 main window with controls + log panel |
| `gui/worker.py` | QThread wrapper running the async grab pipeline |
| `utils/__init__.py` | Package init |
| `utils/config.py` | Load/save JSON config with defaults |
| `tests/conftest.py` | Shared fixtures |
| `tests/test_config.py` | Config module tests |
| `tests/test_timer.py` | NTP timer tests |
| `tests/test_browser.py` | Browser manager tests |
| `tests/test_grabber.py` | Grabber logic tests |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `config.json`
- Create: `core/__init__.py`
- Create: `gui/__init__.py`
- Create: `utils/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `requirements.txt`**

```txt
PyQt6>=6.5
playwright>=1.40
playwright-stealth>=1.0
ntplib>=0.4
pytest>=7.0
pytest-asyncio>=0.23
```

- [ ] **Step 2: Create `config.json`**

```json
{
  "chrome_path": "",
  "debug_port": 9222,
  "grab": {
    "max_retries": 3,
    "retry_interval_ms": 500,
    "poll_interval_ms": 50,
    "confirm_timeout_ms": 5000
  },
  "ntp": {
    "servers": ["ntp.aliyun.com", "ntp.tencent.com", "cn.pool.ntp.org"],
    "timeout_s": 3
  }
}
```

- [ ] **Step 3: Create package `__init__.py` files**

Create empty `__init__.py` in `core/`, `gui/`, `utils/`, `tests/`.

- [ ] **Step 4: Create `tests/conftest.py`**

```python
import json
import pytest
from pathlib import Path


@pytest.fixture
def sample_config():
    return {
        "chrome_path": "",
        "debug_port": 9222,
        "grab": {
            "max_retries": 3,
            "retry_interval_ms": 500,
            "poll_interval_ms": 50,
            "confirm_timeout_ms": 5000,
        },
        "ntp": {
            "servers": ["ntp.aliyun.com", "ntp.tencent.com", "cn.pool.ntp.org"],
            "timeout_s": 3,
        },
    }


@pytest.fixture
def config_file(tmp_path, sample_config):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(sample_config, indent=2))
    return path
```

- [ ] **Step 5: Install dependencies and Playwright browsers**

Run:
```bash
pip install -r requirements.txt
playwright install chromium
```

- [ ] **Step 6: Verify pytest runs with no tests**

Run: `pytest --co -q`
Expected: "no tests ran"

- [ ] **Step 7: Commit**

```bash
git add requirements.txt config.json core/__init__.py gui/__init__.py utils/__init__.py tests/__init__.py tests/conftest.py
git commit -m "scaffold: project structure, dependencies, and test fixtures"
```

---

### Task 2: Config Module (`utils/config.py`)

**Files:**
- Create: `utils/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_config.py`:

```python
import json
from pathlib import Path

from utils.config import load_config, save_config, DEFAULT_CONFIG


def test_load_config_from_file(config_file, sample_config):
    config = load_config(config_file)
    assert config == sample_config


def test_load_config_missing_file_returns_defaults(tmp_path):
    path = tmp_path / "nonexistent.json"
    config = load_config(path)
    assert config == DEFAULT_CONFIG


def test_load_config_merges_partial_with_defaults(tmp_path):
    path = tmp_path / "partial.json"
    path.write_text(json.dumps({"debug_port": 9999}))
    config = load_config(path)
    assert config["debug_port"] == 9999
    assert config["grab"]["max_retries"] == DEFAULT_CONFIG["grab"]["max_retries"]
    assert config["ntp"]["servers"] == DEFAULT_CONFIG["ntp"]["servers"]


def test_save_config(tmp_path):
    path = tmp_path / "out.json"
    config = {"debug_port": 1234, "grab": {"max_retries": 5}}
    save_config(path, config)
    loaded = json.loads(path.read_text())
    assert loaded["debug_port"] == 1234
    assert loaded["grab"]["max_retries"] == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.config'`

- [ ] **Step 3: Implement `utils/config.py`**

```python
import json
import copy
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "chrome_path": "",
    "debug_port": 9222,
    "grab": {
        "max_retries": 3,
        "retry_interval_ms": 500,
        "poll_interval_ms": 50,
        "confirm_timeout_ms": 5000,
    },
    "ntp": {
        "servers": ["ntp.aliyun.com", "ntp.tencent.com", "cn.pool.ntp.org"],
        "timeout_s": 3,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path: Path) -> dict:
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    with open(path, "r", encoding="utf-8") as f:
        user_config = json.load(f)
    return _deep_merge(DEFAULT_CONFIG, user_config)


def save_config(path: Path, config: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add utils/config.py tests/test_config.py
git commit -m "feat: config module with deep-merge defaults"
```

---

### Task 3: NTP Timer (`core/timer.py`)

**Files:**
- Create: `core/timer.py`
- Create: `tests/test_timer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_timer.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_timer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.timer'`

- [ ] **Step 3: Implement `core/timer.py`**

```python
import time

import ntplib


class NTPTimer:
    def __init__(self, servers: list[str], timeout: int = 3):
        self.servers = servers
        self.timeout = timeout
        self.offset: float = 0.0

    def sync(self) -> float:
        client = ntplib.NTPClient()
        for server in self.servers:
            try:
                response = client.request(server, version=3, timeout=self.timeout)
                self.offset = response.offset
                return self.offset
            except Exception:
                continue
        self.offset = 0.0
        return 0.0

    def now(self) -> float:
        return time.time() + self.offset

    def wait_until(self, target: float) -> None:
        while True:
            remaining = target - self.now()
            if remaining <= 0:
                return
            if remaining > 0.05:
                time.sleep(remaining - 0.05)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_timer.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add core/timer.py tests/test_timer.py
git commit -m "feat: NTP timer with multi-server fallback and precision wait"
```

---

### Task 4: Browser Manager (`core/browser.py`)

**Files:**
- Create: `core/browser.py`
- Create: `tests/test_browser.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_browser.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_browser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.browser'`

- [ ] **Step 3: Implement `core/browser.py`**

```python
import platform
import subprocess
from pathlib import Path

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
        self._browser: Browser | None = None
        self._playwright = None
        self._process: subprocess.Popen | None = None

    @property
    def cdp_url(self) -> str:
        return f"http://localhost:{self.debug_port}"

    def build_launch_command(self) -> list[str]:
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

    def get_damai_page(self) -> Page | None:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_browser.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add core/browser.py tests/test_browser.py
git commit -m "feat: browser manager with CDP connection and Damai page detection"
```

---

### Task 5: Grab Logic (`core/grabber.py`)

**Files:**
- Create: `core/grabber.py`
- Create: `tests/test_grabber.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_grabber.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_grabber.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.grabber'`

- [ ] **Step 3: Implement `core/grabber.py`**

```python
import asyncio
import time
from dataclasses import dataclass
from typing import Callable

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
        on_log: Callable[[str], None] | None = None,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_grabber.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add core/grabber.py tests/test_grabber.py
git commit -m "feat: ticket grabber with two-step click and retry logic"
```

---

### Task 6: GUI Worker Thread (`gui/worker.py`)

**Files:**
- Create: `gui/worker.py`

This is the QThread that bridges the async Playwright world with PyQt6 signals. Not unit-tested directly (integration layer), but wires together the tested core modules.

- [ ] **Step 1: Implement `gui/worker.py`**

```python
import asyncio
import time
from datetime import datetime

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
        ntp_servers: list[str],
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
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from gui.worker import GrabWorker; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add gui/worker.py
git commit -m "feat: QThread grab worker bridging async Playwright with PyQt6 signals"
```

---

### Task 7: Main Window GUI (`gui/main_window.py`)

**Files:**
- Create: `gui/main_window.py`

- [ ] **Step 1: Implement `gui/main_window.py`**

```python
import subprocess
import platform
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDateTimeEdit, QTextEdit, QGroupBox,
)
from PyQt6.QtCore import Qt, QDateTime, QTimer
from PyQt6.QtGui import QFont, QTextCursor

from gui.worker import GrabWorker
from utils.config import load_config, DEFAULT_CONFIG


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config(Path("config.json"))
        self.worker: GrabWorker | None = None
        self._chrome_process: subprocess.Popen | None = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("DamaiGrabber — 大麦网抢票工具")
        self.setMinimumSize(600, 500)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Control Panel ---
        control_group = QGroupBox("控制面板")
        control_layout = QVBoxLayout(control_group)

        # Row 1: Browser
        row1 = QHBoxLayout()
        self.btn_launch = QPushButton("启动浏览器")
        self.btn_launch.clicked.connect(self._on_launch_browser)
        self.label_status = QLabel("浏览器: 未启动")
        row1.addWidget(self.btn_launch)
        row1.addWidget(self.label_status)
        row1.addStretch()
        control_layout.addLayout(row1)

        # Row 2: Time + Start
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("开票时间:"))
        self.dt_edit = QDateTimeEdit()
        self.dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.dt_edit.setDateTime(QDateTime.currentDateTime())
        self.dt_edit.setCalendarPopup(True)
        row2.addWidget(self.dt_edit)
        self.btn_start = QPushButton("开始抢票")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)
        row2.addWidget(self.btn_start)
        row2.addWidget(self.btn_stop)
        control_layout.addLayout(row2)

        # Row 3: Countdown
        self.label_countdown = QLabel("--:--:--.---")
        self.label_countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        countdown_font = QFont()
        countdown_font.setPointSize(28)
        countdown_font.setBold(True)
        self.label_countdown.setFont(countdown_font)
        control_layout.addWidget(self.label_countdown)

        layout.addWidget(control_group)

        # --- Log Panel ---
        log_group = QGroupBox("实时日志")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Courier", 11))
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group)

    def _on_launch_browser(self):
        port = self.config.get("debug_port", 9222)
        chrome_path = self.config.get("chrome_path", "")
        if not chrome_path:
            system = platform.system()
            if system == "Darwin":
                chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            elif system == "Windows":
                chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            else:
                chrome_path = "google-chrome"

        if not Path(chrome_path).exists() and platform.system() != "Windows":
            self._log(f"错误: 未找到 Chrome，路径: {chrome_path}")
            self._log("请在 config.json 中设置 chrome_path")
            return

        cmd = [chrome_path, f"--remote-debugging-port={port}"]
        try:
            self._chrome_process = subprocess.Popen(cmd)
            self.label_status.setText(f"浏览器: 已启动 (端口 {port})")
            self._log(f"Chrome 已启动，调试端口: {port}")
        except Exception as e:
            self._log(f"启动 Chrome 失败: {e}")

    def _on_start(self):
        target_qdt = self.dt_edit.dateTime()
        target_dt = target_qdt.toPyDateTime()

        port = self.config.get("debug_port", 9222)
        cdp_url = f"http://localhost:{port}"

        ntp_cfg = self.config.get("ntp", DEFAULT_CONFIG["ntp"])
        grab_cfg = self.config.get("grab", DEFAULT_CONFIG["grab"])

        self.worker = GrabWorker(
            cdp_url=cdp_url,
            target_time=target_dt,
            ntp_servers=ntp_cfg["servers"],
            ntp_timeout=ntp_cfg["timeout_s"],
            grab_config=grab_cfg,
        )
        self.worker.log_message.connect(self._log)
        self.worker.status_changed.connect(self._on_status_changed)
        self.worker.countdown_tick.connect(self._on_countdown_tick)
        self.worker.grab_finished.connect(self._on_grab_finished)
        self.worker.start()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._log(f"抢票任务已启动，目标时间: {target_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    def _on_stop(self):
        if self.worker:
            self.worker.stop()
            self._log("正在停止...")

    def _on_status_changed(self, status: str):
        self.label_status.setText(status)

    def _on_countdown_tick(self, remaining: float):
        if remaining < 0:
            remaining = 0
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        millis = int((remaining * 1000) % 1000)
        self.label_countdown.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}")

    def _on_grab_finished(self, success: bool, message: str):
        if success:
            self._log(f"✅ {message}")
        else:
            self._log(f"❌ {message}")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.label_countdown.setText("--:--:--.---")
        self.worker = None

    def _log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_view.append(f"[{timestamp}] {message}")
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from gui.main_window import MainWindow; print('OK')"`
Expected: `OK` (may fail if no display — that is fine in headless environments)

- [ ] **Step 3: Commit**

```bash
git add gui/main_window.py
git commit -m "feat: PyQt6 main window with controls, countdown, and log panel"
```

---

### Task 8: Application Entry Point (`main.py`)

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement `main.py`**

```python
import sys

from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DamaiGrabber")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify app launches**

Run: `python main.py`
Expected: GUI window appears with title "DamaiGrabber — 大麦网抢票工具", showing control panel and log area.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: application entry point"
```

---

### Task 9: Full Test Suite Run + Smoke Test

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass (15 tests across 4 test files).

- [ ] **Step 2: Manual smoke test**

1. Run `python main.py` — window appears
2. Click "启动浏览器" — Chrome opens with debug port
3. In Chrome, navigate to `https://www.damai.cn`
4. Back in GUI, set a time ~10 seconds in the future
5. Click "开始抢票" — see NTP sync log, countdown ticking, then grab attempt
6. Expected: grab fails with "未找到大麦网页面" or "购买按钮点击失败" (no real show page open) — this confirms the full pipeline runs end-to-end

- [ ] **Step 3: Commit any fixes from smoke test**

```bash
git add -A
git commit -m "fix: adjustments from smoke testing"
```

- [ ] **Step 4: Final commit — tag v0.1.0**

```bash
git tag v0.1.0
```
