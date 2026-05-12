import subprocess
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional

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
        self.worker: Optional[GrabWorker] = None
        self._chrome_process: Optional[subprocess.Popen] = None
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
