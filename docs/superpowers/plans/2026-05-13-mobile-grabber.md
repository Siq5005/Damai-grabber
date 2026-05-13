# Mobile Grabber (uiautomator2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "mobile mode" to the Damai ticket grabber that controls the Damai Android APP via uiautomator2 over USB, solving the "APP-only" ticket restriction.

**Architecture:** Two parallel execution paths (desktop Chrome via Playwright CDP, mobile APP via uiautomator2) share NTPTimer, config, and GUI. A QRadioButton in MainWindow switches between them. Each path has its own Worker (QThread) and Grabber, but they emit the same Qt signals so the GUI doesn't care which is active.

**Tech Stack:** Python 3.9+, PyQt6, uiautomator2, ntplib, Playwright (existing)

**Spec:** `docs/superpowers/specs/2026-05-13-mobile-grabber-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `utils/config.py` | Add `mode` and `mobile` to DEFAULT_CONFIG |
| Modify | `config.json` | Add `mode` and `mobile` section |
| Modify | `tests/conftest.py` | Update `sample_config` fixture to include new fields |
| Create | `core/mobile_grabber.py` | `MobileDevice` (connect/check) + `MobileGrabber` (click_buy/confirm_order/run) |
| Create | `tests/test_mobile_grabber.py` | Tests for MobileDevice and MobileGrabber |
| Create | `gui/mobile_worker.py` | `MobileGrabWorker` QThread |
| Modify | `gui/main_window.py` | Mode radio buttons, connect-phone button, route to correct Worker |
| Modify | `requirements.txt` | Add `uiautomator2>=3.0` |
| Create | `setup.command` | macOS one-click install script |
| Create | `setup.bat` | Windows one-click install script |
| Modify | `start.command` | Activate venv before launch |

---

### Task 1: Expand config with mobile settings

**Files:**
- Modify: `utils/config.py:6-18`
- Modify: `config.json`
- Modify: `tests/conftest.py:7-21`
- Test: `tests/test_config.py`

- [ ] **Step 1: Update DEFAULT_CONFIG in utils/config.py**

Replace the existing `DEFAULT_CONFIG` dict (lines 6-18) with:

```python
DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "desktop",
    "chrome_path": "",
    "debug_port": 9222,
    "grab": {
        "max_retries": 3,
        "retry_interval_ms": 500,
        "poll_interval_ms": 50,
        "confirm_timeout_ms": 5000,
    },
    "mobile": {
        "device_serial": "",
        "max_retries": 20,
        "click_interval_ms": 50,
        "confirm_clicks": 10,
        "advance_seconds": 0.5,
    },
    "ntp": {
        "servers": ["ntp.aliyun.com", "ntp.tencent.com", "cn.pool.ntp.org"],
        "timeout_s": 3,
    },
}
```

- [ ] **Step 2: Update config.json**

Replace the entire file with:

```json
{
  "mode": "desktop",
  "chrome_path": "",
  "debug_port": 9222,
  "grab": {
    "max_retries": 3,
    "retry_interval_ms": 500,
    "poll_interval_ms": 50,
    "confirm_timeout_ms": 5000
  },
  "mobile": {
    "device_serial": "",
    "max_retries": 20,
    "click_interval_ms": 50,
    "confirm_clicks": 10,
    "advance_seconds": 0.5
  },
  "ntp": {
    "servers": ["ntp.aliyun.com", "ntp.tencent.com", "cn.pool.ntp.org"],
    "timeout_s": 3
  }
}
```

- [ ] **Step 3: Update conftest.py sample_config fixture**

Replace the `sample_config` fixture (lines 7-21) with:

```python
@pytest.fixture
def sample_config():
    return {
        "mode": "desktop",
        "chrome_path": "",
        "debug_port": 9222,
        "grab": {
            "max_retries": 3,
            "retry_interval_ms": 500,
            "poll_interval_ms": 50,
            "confirm_timeout_ms": 5000,
        },
        "mobile": {
            "device_serial": "",
            "max_retries": 20,
            "click_interval_ms": 50,
            "confirm_clicks": 10,
            "advance_seconds": 0.5,
        },
        "ntp": {
            "servers": ["ntp.aliyun.com", "ntp.tencent.com", "cn.pool.ntp.org"],
            "timeout_s": 3,
        },
    }
```

- [ ] **Step 4: Run existing config tests to verify nothing breaks**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: All 4 tests PASS. The `test_load_config_from_file` test may fail because the fixture now includes `mode` and `mobile` but the config file written from `sample_config` will also include them — so it should still match. The `test_load_config_merges_partial_with_defaults` test verifies that partial configs merge with the new defaults.

- [ ] **Step 5: Commit**

```bash
git add utils/config.py config.json tests/conftest.py
git commit -m "feat: add mobile config section to DEFAULT_CONFIG and config.json"
```

---

### Task 2: Create MobileDevice class with tests

**Files:**
- Create: `core/mobile_grabber.py`
- Create: `tests/test_mobile_grabber.py`

- [ ] **Step 1: Write failing tests for MobileDevice**

Create `tests/test_mobile_grabber.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


class TestMobileDeviceConnect:
    @patch("core.mobile_grabber.u2")
    def test_connect_auto_detect(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_device = MagicMock()
        mock_device.info = {"productName": "Xiaomi 14"}
        mock_device.window_size.return_value = (1080, 2400)
        mock_u2.connect.return_value = mock_device

        device = MobileDevice()
        device.connect()

        mock_u2.connect.assert_called_once_with()
        assert device.device is mock_device

    @patch("core.mobile_grabber.u2")
    def test_connect_with_serial(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_device = MagicMock()
        mock_device.info = {"productName": "Pixel 8"}
        mock_device.window_size.return_value = (1080, 2340)
        mock_u2.connect.return_value = mock_device

        device = MobileDevice()
        device.connect(serial="abc123")

        mock_u2.connect.assert_called_once_with("abc123")

    @patch("core.mobile_grabber.u2")
    def test_connect_failure_raises(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_u2.connect.side_effect = RuntimeError("no device")

        device = MobileDevice()
        with pytest.raises(RuntimeError, match="no device"):
            device.connect()


class TestMobileDeviceCheck:
    @patch("core.mobile_grabber.u2")
    def test_check_damai_foreground_true(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_device = MagicMock()
        mock_device.info = {"productName": "Test"}
        mock_device.window_size.return_value = (1080, 2400)
        mock_u2.connect.return_value = mock_device
        mock_device.app_current.return_value = {"package": "cn.damai"}

        device = MobileDevice()
        device.connect()
        assert device.check_damai_foreground() is True

    @patch("core.mobile_grabber.u2")
    def test_check_damai_foreground_false(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_device = MagicMock()
        mock_device.info = {"productName": "Test"}
        mock_device.window_size.return_value = (1080, 2400)
        mock_u2.connect.return_value = mock_device
        mock_device.app_current.return_value = {"package": "com.tencent.mm"}

        device = MobileDevice()
        device.connect()
        assert device.check_damai_foreground() is False

    @patch("core.mobile_grabber.u2")
    def test_window_size(self, mock_u2):
        from core.mobile_grabber import MobileDevice

        mock_device = MagicMock()
        mock_device.info = {"productName": "Test"}
        mock_device.window_size.return_value = (1080, 2400)
        mock_u2.connect.return_value = mock_device

        device = MobileDevice()
        device.connect()
        assert device.window_size() == (1080, 2400)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_mobile_grabber.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.mobile_grabber'`

- [ ] **Step 3: Implement MobileDevice**

Create `core/mobile_grabber.py`:

```python
import time
from typing import Callable, Optional

import uiautomator2 as u2

from core.grabber import GrabResult

_BUY_BUTTON_TEXTS = ["立即抢购", "立即购买", "立即预订", "选座购买", "确定"]

_ORDER_DETECTED_TEXTS = ["提交订单"]

_CONFIRM_BUTTON_TEXTS = ["提交订单", "确认订单"]

_FALLBACK_BUY_POS = (0.75, 0.92)
_FALLBACK_CONFIRM_POS = (0.80, 0.92)


class MobileDevice:
    def __init__(self):
        self.device = None

    def connect(self, serial: str = "") -> None:
        if serial:
            self.device = u2.connect(serial)
        else:
            self.device = u2.connect()

    def check_damai_foreground(self) -> bool:
        current = self.device.app_current()
        return "damai" in current.get("package", "").lower()

    def window_size(self) -> tuple[int, int]:
        return self.device.window_size()
```

- [ ] **Step 4: Run MobileDevice tests**

Run: `python3 -m pytest tests/test_mobile_grabber.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/mobile_grabber.py tests/test_mobile_grabber.py
git commit -m "feat: add MobileDevice class with uiautomator2 connection"
```

---

### Task 3: Create MobileGrabber class with tests

**Files:**
- Modify: `core/mobile_grabber.py`
- Modify: `tests/test_mobile_grabber.py`

- [ ] **Step 1: Write failing tests for MobileGrabber.click_buy**

Append to `tests/test_mobile_grabber.py`:

```python
class TestMobileGrabberClickBuy:
    def test_click_buy_finds_text_button(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()
        # First text "立即抢购" — not found
        btn_not_found = MagicMock()
        btn_not_found.exists.return_value = False
        # Second text "立即购买" — not found
        btn_not_found2 = MagicMock()
        btn_not_found2.exists.return_value = False
        # Third text "立即预订" — found
        btn_found = MagicMock()
        btn_found.exists.return_value = True

        def mock_selector(text=None, textContains=None):
            if text == "立即抢购":
                return btn_not_found
            if text == "立即购买":
                return btn_not_found2
            if text == "立即预订":
                return btn_found
            # Order page detection
            if text == "提交订单":
                found = MagicMock()
                found.exists.return_value = True
                return found
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.side_effect = None
        mock_device.__call__ = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=3, click_interval_ms=1, confirm_clicks=1)
        logs = []
        result = grabber.click_buy(mock_device, logs.append)
        assert result is True
        btn_found.click.assert_called()

    def test_click_buy_uses_coordinate_fallback(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()
        call_count = {"n": 0}

        def mock_selector(text=None, textContains=None):
            m = MagicMock()
            # All text buttons not found
            m.exists.return_value = False
            # After coordinate fallback on 2nd attempt, detect order page
            if text == "提交订单":
                call_count["n"] += 1
                found = MagicMock()
                found.exists.return_value = call_count["n"] >= 2
                return found
            return m

        mock_device.__call__ = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=5, click_interval_ms=1, confirm_clicks=1)
        logs = []
        result = grabber.click_buy(mock_device, logs.append)
        assert result is True
        mock_device.click.assert_called()

    def test_click_buy_fails_after_max_retries(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()

        def mock_selector(text=None, textContains=None):
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.__call__ = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=3, click_interval_ms=1, confirm_clicks=1)
        logs = []
        result = grabber.click_buy(mock_device, logs.append)
        assert result is False


class TestMobileGrabberConfirmOrder:
    def test_confirm_order_finds_text_then_coordinate_clicks(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()
        btn_found = MagicMock()
        btn_found.exists.return_value = True

        def mock_selector(text=None, textContains=None):
            if text == "提交订单":
                return btn_found
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.__call__ = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=3, click_interval_ms=1, confirm_clicks=5)
        logs = []
        result = grabber.confirm_order(mock_device, logs.append)
        assert result is True
        btn_found.click.assert_called()
        # Coordinate clicks: 5 (confirm) + 5 (fallback) = 10
        assert mock_device.click.call_count == 10

    def test_confirm_order_coordinate_only_when_text_not_found(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()

        def mock_selector(text=None, textContains=None):
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.__call__ = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=3, click_interval_ms=1, confirm_clicks=5)
        logs = []
        result = grabber.confirm_order(mock_device, logs.append)
        assert result is True
        assert mock_device.click.call_count == 10


class TestMobileGrabberRun:
    def test_run_success(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()
        btn_found = MagicMock()
        btn_found.exists.return_value = True

        def mock_selector(text=None, textContains=None):
            if text in ("立即抢购", "提交订单"):
                return btn_found
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.__call__ = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=3, click_interval_ms=1, confirm_clicks=2)
        logs = []
        result = grabber.run(mock_device, logs.append)
        assert result.success is True
        assert result.elapsed_ms > 0
        assert any("Step 1" in msg for msg in logs)
        assert any("Step 2" in msg for msg in logs)

    def test_run_failure_when_buy_fails(self):
        from core.mobile_grabber import MobileGrabber

        mock_device = MagicMock()

        def mock_selector(text=None, textContains=None):
            m = MagicMock()
            m.exists.return_value = False
            return m

        mock_device.__call__ = mock_selector
        mock_device.window_size.return_value = (1080, 2400)

        grabber = MobileGrabber(max_retries=2, click_interval_ms=1, confirm_clicks=1)
        logs = []
        result = grabber.run(mock_device, logs.append)
        assert result.success is False
        assert "购买" in result.message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_mobile_grabber.py::TestMobileGrabberClickBuy -v`
Expected: FAIL — `ImportError: cannot import name 'MobileGrabber'`

- [ ] **Step 3: Implement MobileGrabber**

Append to `core/mobile_grabber.py` (after the `MobileDevice` class):

```python
class MobileGrabber:
    def __init__(
        self,
        max_retries: int = 20,
        click_interval_ms: int = 50,
        confirm_clicks: int = 10,
    ):
        self.max_retries = max_retries
        self.click_interval_ms = click_interval_ms
        self.confirm_clicks = confirm_clicks

    def click_buy(self, device, on_log: Callable[[str], None]) -> bool:
        w, h = device.window_size()
        for attempt in range(self.max_retries):
            clicked = False
            for text in _BUY_BUTTON_TEXTS:
                btn = device(text=text)
                if btn.exists(timeout=0.3):
                    btn.click()
                    on_log(f"第 {attempt + 1} 次尝试 — 点击了「{text}」")
                    clicked = True
                    break

            if not clicked:
                fx, fy = _FALLBACK_BUY_POS
                device.click(int(w * fx), int(h * fy))
                on_log(f"第 {attempt + 1} 次尝试 — 坐标兜底点击 ({fx:.0%}, {fy:.0%})")

            for det_text in _ORDER_DETECTED_TEXTS:
                if device(text=det_text).exists(timeout=0.1):
                    on_log(f"第 {attempt + 1} 次尝试 — 检测到订单页面")
                    return True
            if device(textContains="¥").exists(timeout=0.1):
                on_log(f"第 {attempt + 1} 次尝试 — 检测到订单页面")
                return True

            time.sleep(self.click_interval_ms / 1000)

        on_log(f"购买按钮点击失败，已尝试 {self.max_retries} 次")
        return False

    def confirm_order(self, device, on_log: Callable[[str], None]) -> bool:
        w, h = device.window_size()

        for text in _CONFIRM_BUTTON_TEXTS:
            btn = device(text=text)
            if btn.exists(timeout=0.3):
                btn.click()
                on_log(f"点击了「{text}」")
                break

        fx, fy = _FALLBACK_CONFIRM_POS
        on_log(f"坐标连点 ({fx:.0%}, {fy:.0%}) × {self.confirm_clicks}")
        for _ in range(self.confirm_clicks):
            device.click(int(w * fx), int(h * fy))

        on_log(f"兜底连点 ({fx:.0%}, {fy:.0%}) × {self.confirm_clicks}")
        for _ in range(self.confirm_clicks):
            device.click(int(w * fx), int(h * fy))

        return True

    def run(
        self,
        device,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> GrabResult:
        log = on_log or (lambda _: None)
        start = time.time()

        log("Step 1: 疯狂点击购买按钮")
        buy_ok = self.click_buy(device, log)
        if not buy_ok:
            elapsed = (time.time() - start) * 1000
            return GrabResult(success=False, message="购买按钮点击失败", elapsed_ms=elapsed)

        buy_elapsed = (time.time() - start) * 1000
        log(f"购买按钮点击成功 (耗时 {buy_elapsed:.0f}ms) — Step 2: 确认订单")

        self.confirm_order(device, log)
        elapsed = (time.time() - start) * 1000
        log(f"抢票完成！总耗时 {elapsed:.0f}ms，请在手机上完成支付")
        return GrabResult(success=True, message="抢票成功，请在手机上完成支付", elapsed_ms=elapsed)
```

- [ ] **Step 4: Run all mobile grabber tests**

Run: `python3 -m pytest tests/test_mobile_grabber.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/mobile_grabber.py tests/test_mobile_grabber.py
git commit -m "feat: add MobileGrabber with click_buy, confirm_order, and run"
```

---

### Task 4: Create MobileGrabWorker

**Files:**
- Create: `gui/mobile_worker.py`

- [ ] **Step 1: Create gui/mobile_worker.py**

```python
import time
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.timer import NTPTimer
from core.mobile_grabber import MobileDevice, MobileGrabber, GrabResult


class MobileGrabWorker(QThread):
    log_message = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    countdown_tick = pyqtSignal(float)
    grab_finished = pyqtSignal(bool, str)

    def __init__(
        self,
        device_serial: str,
        target_time: datetime,
        ntp_servers: list,
        ntp_timeout: int,
        grab_config: dict,
    ):
        super().__init__()
        self.device_serial = device_serial
        self.target_timestamp = target_time.timestamp()
        self.ntp_servers = ntp_servers
        self.ntp_timeout = ntp_timeout
        self.grab_config = grab_config
        self._stop_flag = False

    def run(self):
        try:
            self._execute()
        except Exception as e:
            self.grab_finished.emit(False, f"异常: {e}")

    def _execute(self):
        self.log_message.emit("抢票模式: 移动端(APP)")

        self.status_changed.emit("正在同步NTP时间...")
        timer = NTPTimer(servers=self.ntp_servers, timeout=self.ntp_timeout)
        offset = timer.sync()
        if offset == 0.0 and self.ntp_servers:
            self.log_message.emit("警告: NTP校时失败，使用本地时间")
        else:
            self.log_message.emit(f"NTP校时完成，偏移量: {offset*1000:.1f}ms")

        self.status_changed.emit("正在连接手机...")
        self.log_message.emit("正在连接手机...")
        mobile = MobileDevice()
        try:
            mobile.connect(serial=self.device_serial)
        except Exception as e:
            self.log_message.emit(f"连接失败: {e}")
            self.log_message.emit("请检查:")
            self.log_message.emit("  1. 手机已通过 USB 数据线连接电脑")
            self.log_message.emit("  2. 手机已开启 USB 调试（开发者选项中）")
            self.log_message.emit("  3. 手机弹窗已点击「允许 USB 调试」")
            self.grab_finished.emit(False, f"手机连接失败: {e}")
            return

        w, h = mobile.window_size()
        info_name = mobile.device.info.get("productName", "Unknown")
        self.log_message.emit(f"已连接: {info_name} ({w}×{h})")

        if mobile.check_damai_foreground():
            self.log_message.emit("大麦APP已在前台")
        else:
            self.log_message.emit("警告: 当前前台不是大麦APP，请手动切换")

        advance = self.grab_config.get("advance_seconds", 0.5)

        self.status_changed.emit("等待开票时间...")
        while not self._stop_flag:
            remaining = self.target_timestamp - timer.now()
            if remaining <= advance:
                break
            self.countdown_tick.emit(remaining)
            if remaining > 1.0:
                time.sleep(0.1)
            else:
                time.sleep(0.01)

        if self._stop_flag:
            self.grab_finished.emit(False, "用户手动停止")
            return

        if advance > 0:
            self.log_message.emit(f"提前 {advance} 秒开始点击")

        self.status_changed.emit("抢票中...")
        grabber = MobileGrabber(
            max_retries=self.grab_config.get("max_retries", 20),
            click_interval_ms=self.grab_config.get("click_interval_ms", 50),
            confirm_clicks=self.grab_config.get("confirm_clicks", 10),
        )

        result: GrabResult = grabber.run(
            mobile.device, on_log=lambda msg: self.log_message.emit(msg)
        )

        self.grab_finished.emit(result.success, result.message)

    def stop(self):
        self._stop_flag = True
```

- [ ] **Step 2: Verify import works**

Run: `python3 -c "from gui.mobile_worker import MobileGrabWorker; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add gui/mobile_worker.py
git commit -m "feat: add MobileGrabWorker QThread for mobile grab execution"
```

---

### Task 5: Update MainWindow with mode switching

**Files:**
- Modify: `gui/main_window.py`

- [ ] **Step 1: Replace gui/main_window.py with mode-switching version**

Replace the entire file with:

```python
import subprocess
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDateTimeEdit, QTextEdit, QGroupBox,
    QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtGui import QFont, QTextCursor

from gui.worker import GrabWorker
from gui.mobile_worker import MobileGrabWorker
from utils.config import load_config, save_config, DEFAULT_CONFIG


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._config_path = Path("config.json")
        self.config = load_config(self._config_path)
        self.worker: Optional[Union[GrabWorker, MobileGrabWorker]] = None
        self._chrome_process: Optional[subprocess.Popen] = None
        self._init_ui()
        self._apply_mode(self.config.get("mode", "desktop"))

    def _init_ui(self):
        self.setWindowTitle("DamaiGrabber — 大麦网抢票工具")
        self.setMinimumSize(600, 500)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Control Panel ---
        control_group = QGroupBox("控制面板")
        control_layout = QVBoxLayout(control_group)

        # Row 0: Mode Switch
        row0 = QHBoxLayout()
        row0.addWidget(QLabel("抢票模式:"))
        self.radio_desktop = QRadioButton("桌面端(Chrome)")
        self.radio_mobile = QRadioButton("移动端(APP)")
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.radio_desktop)
        self.mode_group.addButton(self.radio_mobile)
        self.radio_desktop.toggled.connect(self._on_mode_toggled)
        row0.addWidget(self.radio_desktop)
        row0.addWidget(self.radio_mobile)
        row0.addStretch()
        control_layout.addLayout(row0)

        # Row 1a: Desktop — Browser
        self.row_desktop = QWidget()
        row1a_layout = QHBoxLayout(self.row_desktop)
        row1a_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_launch = QPushButton("启动浏览器")
        self.btn_launch.clicked.connect(self._on_launch_browser)
        self.label_browser_status = QLabel("浏览器: 未启动")
        row1a_layout.addWidget(self.btn_launch)
        row1a_layout.addWidget(self.label_browser_status)
        row1a_layout.addStretch()
        control_layout.addWidget(self.row_desktop)

        # Row 1b: Mobile — Phone
        self.row_mobile = QWidget()
        row1b_layout = QHBoxLayout(self.row_mobile)
        row1b_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_connect_phone = QPushButton("连接手机")
        self.btn_connect_phone.clicked.connect(self._on_connect_phone)
        self.label_phone_status = QLabel("手机: 未连接")
        row1b_layout.addWidget(self.btn_connect_phone)
        row1b_layout.addWidget(self.label_phone_status)
        row1b_layout.addStretch()
        control_layout.addWidget(self.row_mobile)

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

        # Status label (shared)
        self.label_status = QLabel("")

        layout.addWidget(control_group)

        # --- Log Panel ---
        log_group = QGroupBox("实时日志")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Courier", 11))
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group)

    def _apply_mode(self, mode: str):
        is_mobile = mode == "mobile"
        if is_mobile:
            self.radio_mobile.setChecked(True)
        else:
            self.radio_desktop.setChecked(True)
        self.row_desktop.setVisible(not is_mobile)
        self.row_mobile.setVisible(is_mobile)

    def _on_mode_toggled(self, checked: bool):
        is_mobile = self.radio_mobile.isChecked()
        self.row_desktop.setVisible(not is_mobile)
        self.row_mobile.setVisible(is_mobile)
        mode = "mobile" if is_mobile else "desktop"
        self.config["mode"] = mode
        save_config(self._config_path, self.config)

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
            self.label_browser_status.setText(f"浏览器: 已启动 (端口 {port})")
            self._log(f"Chrome 已启动，调试端口: {port}")
        except Exception as e:
            self._log(f"启动 Chrome 失败: {e}")

    def _on_connect_phone(self):
        self._log("正在检测手机连接...")
        try:
            import uiautomator2 as u2
            serial = self.config.get("mobile", {}).get("device_serial", "")
            if serial:
                device = u2.connect(serial)
            else:
                device = u2.connect()
            info_name = device.info.get("productName", "Unknown")
            w, h = device.window_size()
            self.label_phone_status.setText(f"手机: {info_name} ({w}×{h})")
            self._log(f"手机已连接: {info_name} ({w}×{h})")
            current = device.app_current()
            if "damai" in current.get("package", "").lower():
                self._log("大麦APP已在前台")
            else:
                self._log("警告: 当前前台不是大麦APP，请手动切换到大麦APP的演出详情页")
        except Exception as e:
            self.label_phone_status.setText("手机: 连接失败")
            self._log(f"连接失败: {e}")
            self._log("请检查:")
            self._log("  1. 手机已通过 USB 数据线连接电脑")
            self._log("  2. 手机已开启 USB 调试（开发者选项中）")
            self._log("  3. 手机弹窗已点击「允许 USB 调试」")

    def _on_start(self):
        target_qdt = self.dt_edit.dateTime()
        target_dt = target_qdt.toPyDateTime()
        ntp_cfg = self.config.get("ntp", DEFAULT_CONFIG["ntp"])

        if self.radio_mobile.isChecked():
            mobile_cfg = self.config.get("mobile", DEFAULT_CONFIG["mobile"])
            self.worker = MobileGrabWorker(
                device_serial=mobile_cfg.get("device_serial", ""),
                target_time=target_dt,
                ntp_servers=ntp_cfg["servers"],
                ntp_timeout=ntp_cfg["timeout_s"],
                grab_config=mobile_cfg,
            )
        else:
            port = self.config.get("debug_port", 9222)
            cdp_url = f"http://localhost:{port}"
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

- [ ] **Step 2: Verify GUI launches**

Run: `python3 main.py` (close manually after verifying the mode radio buttons appear and toggle correctly)

- [ ] **Step 3: Commit**

```bash
git add gui/main_window.py
git commit -m "feat: add mobile/desktop mode switching to MainWindow"
```

---

### Task 6: Update dependencies and deploy scripts

**Files:**
- Modify: `requirements.txt`
- Modify: `start.command`
- Create: `setup.command`
- Create: `setup.bat`

- [ ] **Step 1: Update requirements.txt**

Replace the entire file with:

```
PyQt6>=6.5
playwright>=1.40
playwright-stealth>=1.0
ntplib>=0.4
uiautomator2>=3.0
pytest>=7.0
pytest-asyncio>=0.23
```

- [ ] **Step 2: Update start.command**

Replace the entire file with:

```bash
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null
python3 main.py
```

- [ ] **Step 3: Create setup.command (macOS)**

Create `setup.command`:

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== DamaiGrabber 安装 ==="

# 1. 检测 Python3
if ! command -v python3 &>/dev/null; then
    echo "错误: 未找到 Python3，请先安装"
    echo "  推荐: brew install python3"
    exit 1
fi

echo "Python3: $(python3 --version)"

# 2. 创建虚拟环境并安装依赖
if [ ! -d .venv ]; then
    echo "正在创建虚拟环境..."
    python3 -m venv .venv
fi
source .venv/bin/activate
echo "正在安装 Python 依赖..."
pip install -r requirements.txt

# 3. 安装 Playwright Chromium（桌面端需要）
echo "正在安装 Playwright Chromium..."
python3 -m playwright install chromium

# 4. 检测/安装 ADB（移动端需要）
if ! command -v adb &>/dev/null; then
    echo ""
    echo "正在安装 ADB（移动端抢票需要）..."
    if command -v brew &>/dev/null; then
        brew install android-platform-tools
    else
        echo "请手动安装 ADB: brew install android-platform-tools"
    fi
else
    echo "ADB: $(adb version | head -1)"
fi

# 5. 提示移动端配置
echo ""
echo "=== 移动端配置（可选）==="
echo "如需使用移动端抢票，请:"
echo "  1. 手机开启 USB 调试（设置→开发者选项）"
echo "  2. 用数据线连接电脑"
echo "  3. 手机弹窗点击「允许 USB 调试」"
if command -v adb &>/dev/null; then
    echo ""
    echo "当前已连接的设备:"
    adb devices
fi

echo ""
echo "=== 安装完成！==="
echo "启动方式: 双击 start.command 或执行:"
echo "  source .venv/bin/activate && python3 main.py"
```

- [ ] **Step 4: Create setup.bat (Windows)**

Create `setup.bat`:

```batch
@echo off
chcp 65001 >nul
echo === DamaiGrabber 安装 ===

where python3 >nul 2>&1
if errorlevel 1 (
    where python >nul 2>&1
    if errorlevel 1 (
        echo 错误: 未找到 Python，请先安装 Python 3.9+
        pause
        exit /b 1
    )
    set PY=python
) else (
    set PY=python3
)

if not exist .venv (
    echo 正在创建虚拟环境...
    %PY% -m venv .venv
)
call .venv\Scripts\activate.bat

echo 正在安装 Python 依赖...
pip install -r requirements.txt

echo 正在安装 Playwright Chromium...
python -m playwright install chromium

where adb >nul 2>&1
if errorlevel 1 (
    echo.
    echo [提示] 移动端抢票需要 ADB，请下载 Android Platform Tools 并添加到 PATH
    echo 下载地址: https://developer.android.com/tools/releases/platform-tools
)

echo.
echo === 安装完成！===
echo 启动方式: 运行 start.bat 或执行:
echo   .venv\Scripts\activate.bat ^&^& python main.py
pause
```

- [ ] **Step 5: Make scripts executable**

```bash
chmod +x setup.command start.command
```

- [ ] **Step 6: Install the new dependency**

Run: `pip install uiautomator2>=3.0`

- [ ] **Step 7: Run all tests to verify nothing is broken**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add requirements.txt start.command setup.command setup.bat
git commit -m "feat: add uiautomator2 dependency and one-click setup scripts"
```

---

### Task 7: Final integration test

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS (config, timer, browser, grabber, mobile_grabber)

- [ ] **Step 2: Launch GUI and verify mode switching**

Run: `python3 main.py`

Manually verify:
1. Radio buttons "桌面端(Chrome)" and "移动端(APP)" appear
2. Switching to mobile hides "启动浏览器", shows "连接手机"
3. Switching to desktop hides "连接手机", shows "启动浏览器"
4. Mode selection persists in config.json after switching
5. Log panel and countdown are visible in both modes

- [ ] **Step 3: Commit any fixes if needed, then tag**

```bash
git add -A
git commit -m "feat: mobile grabber integration complete"
```
