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
