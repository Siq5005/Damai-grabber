import random
import subprocess
import threading
import time
from typing import Callable, Optional

import uiautomator2 as u2

from core.grabber import GrabResult

# 已知购买按钮文案（仅作参考与日后扩展）。快速路径直接连点坐标兜底，不逐个查文字——
# 每次无障碍查询 ~0.5s，且开票前按钮尚未刷新为购买文案，逐个查 6 个候选会浪费数秒。
_BUY_BUTTON_TEXTS = ["立即购票", "立即抢购", "立即购买", "立即预订", "选座购买", "确定"]

# 订单/确认页才会出现的按钮文案，用于检测是否已进入订单页
_CONFIRM_BUTTON_TEXTS = ["提交订单", "确认订单"]

# 提交订单拥堵时大麦弹出的「重试」按钮文案（弹窗，屏幕中间）
_RETRY_BUTTON_TEXTS = ["重试", "重新提交"]

_FALLBACK_BUY_POS = (0.75, 0.92)
_FALLBACK_CONFIRM_POS = (0.80, 0.92)

# 注入方式降级顺序：UiAutomation 注入 -> shell input -> adb input -> su input(root)
# 某些 uia2 服务端（如 com.wetest.uia2）对跨应用窗口使用 injectInputEventToTarget，
# 会因缺少 INJECT_EVENTS 权限被系统拒绝。新版 Android 上 adb shell input tap 同样走
# injectInputEventToTarget，shell 用户也被拒。此时仅 root 注入（su）能绕过——root 持有
# INJECT_EVENTS。若设备未 root，则属于设备侧安全限制，必须开启对应调试开关或用无障碍服务。
_CLICK_MODES = ["uia", "shell_rpc", "shell_adb", "shell_su"]

_INJECT_BLOCKED_MSG = (
    "设备禁止了 input 注入（INJECT_EVENTS）：uiautomator2、shell input、adb input、"
    "su input 均被系统拒绝，已无法通过代码绕过。\n"
    "这是设备侧的安全限制，请尝试：\n"
    "  1. 小米/红米 (MIUI/HyperOS)：开发者选项 → 开启「USB 调试（安全设置）」(需登录小米账号)\n"
    "  2. OPPO/一加/realme (ColorOS)：开启「禁止权限监控」并允许 USB 调试安全选项\n"
    "  3. vivo/iQOO (OriginOS)：开启「USB 调试（安全开关）」\n"
    "  4. 若设备已 root：在 Magisk 中对 shell 授权（已自动尝试 su 注入，仍失败请检查授权）\n"
    "  5. 终极方案：改用无障碍服务点击（dispatchGesture，不受 INJECT_EVENTS 限制）"
)


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


class MobileGrabber:
    def __init__(
        self,
        max_retries: int = 20,
        click_interval_ms: int = 50,
        confirm_timeout_s: float = 20.0,
    ):
        self.max_retries = max_retries
        self.click_interval_ms = click_interval_ms
        self.confirm_timeout_s = confirm_timeout_s
        self._click_mode = "uia"
        self._log: Callable[[str], None] = lambda _: None

    def _jittered_interval(self) -> float:
        # 给连点间隔加 ±30% 抖动，避免完美的机械节奏被风控标记
        return self.click_interval_ms / 1000 * random.uniform(0.7, 1.3)

    def _jittered_pos(self, w: int, h: int, fx: float, fy: float) -> tuple[int, int]:
        # 坐标兜底点击时落点加几像素随机偏移，避免每次点同一个像素
        jx = int(w * fx) + random.randint(-6, 6)
        jy = int(h * fy) + random.randint(-6, 6)
        return jx, jy

    # ------------------------------------------------------------------
    # 点击注入：含自动降级
    # ------------------------------------------------------------------
    @staticmethod
    def _is_inject_error(exc) -> bool:
        s = str(exc)
        return "INJECT_EVENTS" in s or "SecurityException" in s

    def _escalate_click_mode(self) -> None:
        idx = _CLICK_MODES.index(self._click_mode)
        if idx + 1 < len(_CLICK_MODES):
            self._click_mode = _CLICK_MODES[idx + 1]
            if self._click_mode == "shell_rpc":
                self._log("⚠ UiAutomation 注入被拒 (INJECT_EVENTS)，自动切换为 shell input 点击")
            elif self._click_mode == "shell_adb":
                self._log("⚠ shell RPC 注入同样被拒，切换为 adb input 点击（稍慢）")
            elif self._click_mode == "shell_su":
                self._log("⚠ adb 注入也被拒，尝试以 root 注入（需设备已 root）")

    def _shell_rpc_tap(self, device, x: int, y: int) -> bool:
        """通过 uia2 的 shell RPC 执行 input tap（经 atx-agent，以 shell 用户运行）。

        返回 True 表示点击成功；返回 False 表示同样撞上了注入权限墙，需要继续降级。
        """
        try:
            res = device.shell(f"input tap {x} {y}")
        except Exception as e:
            if self._is_inject_error(e):
                return False
            raise
        # u2 3.x 返回 ShellResponse(output, exit_code)；旧版直接返回 str
        out = getattr(res, "output", res)
        s = str(out or "").lower()
        if "securityexception" in s or "inject_events" in s:
            return False
        return True

    def _adb_tap(self, serial: str, x: int, y: int) -> bool:
        """宿主机 adb shell input tap（以 shell 用户注入）。

        返回 True 表示点击成功；返回 False 表示同样撞上注入权限墙，需继续降级。
        其他错误（设备断开等）抛 RuntimeError。
        """
        cmd = ["adb"]
        if serial:
            cmd += ["-s", str(serial)]
        cmd += ["shell", "input", "tap", str(x), str(y)]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=8)
        except FileNotFoundError:
            raise RuntimeError(
                "未找到 adb 命令，无法执行兜底点击。请安装 android-platform-tools "
                "并确保 adb 在 PATH 中（macOS: brew install android-platform-tools）"
            )
        text = ((res.stdout or b"") + (res.stderr or b"")).decode(errors="ignore")
        low = text.lower()
        if res.returncode != 0 and ("securityexception" in low or "inject_events" in low):
            return False
        if res.returncode != 0:
            raise RuntimeError(f"adb input tap 失败: {text.strip()}")
        return True

    def _su_tap(self, serial: str, x: int, y: int) -> bool:
        """以 root 身份注入 input tap（需设备已 root，如 Magisk）。

        root 持有 INJECT_EVENTS 权限，可绕过 injectInputEventToTarget 的限制。
        返回 True 成功；返回 False 表示设备未 root 或被拒（耗尽所有注入方式）。
        """
        cmd = ["adb"]
        if serial:
            cmd += ["-s", str(serial)]
        # 单引号包住整条命令，让设备端 sh 把 'input tap x y' 作为 su -c 的单个参数
        cmd += ["shell", f"su -c 'input tap {x} {y}'"]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=10)
        except FileNotFoundError:
            raise RuntimeError(
                "未找到 adb 命令，无法执行兜底点击。请安装 android-platform-tools "
                "并确保 adb 在 PATH 中（macOS: brew install android-platform-tools）"
            )
        text = ((res.stdout or b"") + (res.stderr or b"")).decode(errors="ignore")
        low = text.lower()
        if res.returncode == 0:
            return True
        # 未 root：su 不存在 / 被拒
        if ("not found" in low or "no such file" in low
                or "permission denied" in low or "denied" in low):
            return False
        if "securityexception" in low or "inject_events" in low:
            return False
        return False

    def _click_point(self, device, x: int, y: int) -> None:
        """对坐标 (x, y) 点击，按需自动降级注入方式直到成功或耗尽。"""
        while True:
            if self._click_mode == "uia":
                try:
                    device.click(x, y)
                    return
                except Exception as e:
                    if self._is_inject_error(e):
                        self._escalate_click_mode()
                        continue
                    raise
            elif self._click_mode == "shell_rpc":
                if self._shell_rpc_tap(device, x, y):
                    return
                self._escalate_click_mode()
                continue
            elif self._click_mode == "shell_adb":
                if self._adb_tap(device.serial, x, y):
                    return
                self._escalate_click_mode()
                continue
            else:  # shell_su (root) — 最后手段
                if self._su_tap(device.serial, x, y):
                    return
                raise RuntimeError(_INJECT_BLOCKED_MSG)

    def _click_element(self, device, element) -> bool:
        """点击某个 UiObject 元素，按需自动降级注入方式。

        返回 False 表示元素在降级过程中已消失（调用方应改用坐标兜底）。
        """
        if self._click_mode == "uia":
            try:
                element.click()
                return True
            except Exception as e:
                if self._is_inject_error(e):
                    self._escalate_click_mode()
                else:
                    raise
        # 降级到 shell/adb 模式后，需要从元素中取中心点坐标
        try:
            x, y = element.center()
        except Exception:
            return False
        self._click_point(device, x, y)
        return True

    # ------------------------------------------------------------------
    # 抢票流程
    # ------------------------------------------------------------------
    def _on_order_page(self, device) -> bool:
        """检测是否已进入订单/确认页（提交订单/确认订单按钮只在该页出现）。"""
        for text in _CONFIRM_BUTTON_TEXTS:
            try:
                if device(text=text).exists(timeout=0.1):
                    return True
            except Exception:
                pass
        return False

    def click_buy(self, device, on_log: Callable[[str], None]) -> bool:
        w, h = device.window_size()
        bfx, bfy = _FALLBACK_BUY_POS
        bx, by = self._jittered_pos(w, h, bfx, bfy)

        # 订单页检测查询 ~1s/次，若同步检测会阻塞连点节奏。改用后台线程异步检测、与点击并行：
        # 开票瞬间能连续点击购买键不被查询拖慢，检测命中后立即停止。
        detected = threading.Event()
        stop = threading.Event()

        def _detect():
            while not stop.is_set() and not detected.is_set():
                try:
                    if self._on_order_page(device):
                        detected.set()
                        return
                except Exception:
                    pass
                time.sleep(0.15)

        th = threading.Thread(target=_detect, daemon=True, name="order-detect")
        th.start()
        try:
            for attempt in range(self.max_retries):
                self._click_point(device, bx, by)
                on_log(f"第 {attempt + 1} 次尝试 — 点击购买键 ({bfx:.0%}, {bfy:.0%})")
                if detected.is_set():
                    on_log(f"第 {attempt + 1} 次尝试 — 已进入订单页面")
                    return True
                time.sleep(self._jittered_interval())
        finally:
            stop.set()
            th.join(timeout=2)
        if detected.is_set():
            on_log("已进入订单页面")
            return True
        on_log(f"购买按钮点击失败，已尝试 {self.max_retries} 次")
        return False

    def _find(self, device, texts, timeout: float = 0.1):
        """返回第一个存在的元素；都不存在则返回 None。"""
        for text in texts:
            try:
                el = device(text=text)
                if el.exists(timeout=timeout):
                    return el
            except Exception:
                pass
        return None

    def confirm_order(self, device, on_log: Callable[[str], None]) -> bool:
        """点击「提交订单」并处理拥堵重试弹窗，直到提交成功或超时。

        大麦开票拥堵时，点提交订单后会弹出「重试」按钮（屏幕中间）；
        需持续点「重试」重试，直到订单提交成功（离开确认页跳转支付页）。
        返回 True=已提交，False=超时未确认（请人工检查手机）。
        """
        w, h = device.window_size()
        cfx, cfy = _FALLBACK_CONFIRM_POS
        # 先立即点一次「提交订单」（开票瞬间不先查询，避免浪费 ~2s）
        cx, cy = self._jittered_pos(w, h, cfx, cfy)
        self._click_point(device, cx, cy)
        on_log("点击「提交订单」")
        time.sleep(0.4)  # 等结果出现（重试弹窗 / 跳支付页）

        deadline = time.time() + self.confirm_timeout_s
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            # 优先处理「重试」弹窗（拥堵）；否则仍在确认页就再点提交订单；否则视为已跳支付页
            retry_btn = self._find(device, _RETRY_BUTTON_TEXTS, timeout=0.1)
            if retry_btn is not None:
                self._click_element(device, retry_btn)
                on_log(f"第 {attempt} 次重试 — 检测到「重试」弹窗，点击重试")
            elif device(text="提交订单").exists(timeout=0.1):
                cx, cy = self._jittered_pos(w, h, cfx, cfy)
                self._click_point(device, cx, cy)
                on_log(f"第 {attempt} 次重试 — 仍在确认页，再点「提交订单」")
            else:
                on_log(f"第 {attempt} 次重试 — 已离开确认页，订单已提交")
                return True
            time.sleep(self._jittered_interval())
        on_log(f"提交订单未确认成功，已重试 {attempt} 次超时（{self.confirm_timeout_s}s），请检查手机")
        return False

    def run(
        self,
        device,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> GrabResult:
        log = on_log or (lambda _: None)
        self._log = log
        start = time.time()

        log("Step 1: 疯狂点击购买按钮")
        buy_ok = self.click_buy(device, log)
        if not buy_ok:
            elapsed = (time.time() - start) * 1000
            return GrabResult(success=False, message="购买按钮点击失败", elapsed_ms=elapsed)

        buy_elapsed = (time.time() - start) * 1000
        log(f"购买按钮点击成功 (耗时 {buy_elapsed:.0f}ms) — Step 2: 确认订单")

        confirm_ok = self.confirm_order(device, log)
        elapsed = (time.time() - start) * 1000
        if confirm_ok:
            log(f"抢票完成！总耗时 {elapsed:.0f}ms，请在手机上完成支付")
            return GrabResult(success=True, message="抢票成功，请在手机上完成支付", elapsed_ms=elapsed)
        log(f"流程结束（总耗时 {elapsed:.0f}ms），提交订单未确认，请检查手机")
        return GrabResult(success=False, message="提交订单未确认成功，请检查手机", elapsed_ms=elapsed)
