# 移动端抢票模式设计（uiautomator2）

## 背景

大麦网越来越多的热门票限制为"仅APP下单"，当前项目的桌面端 Chrome + Playwright CDP 方案无法覆盖这些票。参考 [Ticket-Purchase-Root-via-Damai-version-0.1](https://github.com/aegitha1os99/Ticket-Purchase-Root-via-Damai-version-0.1) 项目的思路，新增移动端模式，通过 uiautomator2 控制真实 Android 手机上的大麦 APP 完成抢票。

## 目标

- 新增"移动端(APP)"抢票模式，与现有"桌面端(Chrome)"模式在 GUI 内切换
- 目标设备：真实 Android 手机（USB 连接）
- 功能范围：基础模式——连接设备 → NTP 校时 → 精准定时 → 点击购买 → 确认订单
- 用户提前在手机上手动完成：登录、选演出、选场次/票档/观演人
- 提供 macOS / Windows 一键部署脚本

## 架构

```
┌─────────────────────────────────────────────────┐
│                  PyQt6 GUI                       │
│  ┌──────────┐                                   │
│  │模式切换   │  ○ 桌面端(Chrome)  ● 移动端(APP)  │
│  └──────────┘                                   │
│  [开票时间]  [开始抢票]  [停止]                    │
│  [倒计时]   [日志面板]                            │
└──────────────────┬──────────────────────────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼
   GrabWorker            MobileGrabWorker
   (QThread)             (QThread)
      │                      │
      ▼                      ▼
  Playwright CDP        uiautomator2
  → Chrome 桌面          → Android 手机
      │                      │
      ▼                      ▼
  core/grabber.py       core/mobile_grabber.py
  core/browser.py       (自带设备连接逻辑)
      │                      │
      └────────┬─────────────┘
               ▼
         core/timer.py (NTP 共享)
         utils/config.py (配置共享)
```

桌面端和移动端共享 NTPTimer、配置系统、GUI 日志面板和倒计时。两个 Worker 保持独立（桌面端 async + Playwright，移动端 sync + uiautomator2），通过相同的 Qt 信号接口与 GUI 通信。

## 新增模块

### `core/mobile_grabber.py`

#### MobileDevice 类

职责：设备连接与状态检测。

```python
class MobileDevice:
    def connect(self, serial: str = "") -> None:
        # serial 为空时 u2.connect() 自动检测 USB 设备
        # serial 非空时 u2.connect(serial) 连接指定设备

    def check_damai_foreground(self) -> bool:
        # 检查 device.app_current() 包名是否包含 "damai"

    def window_size(self) -> tuple[int, int]:
        # 返回屏幕分辨率，用于坐标兜底计算
```

#### MobileGrabber 类

职责：抢票执行逻辑。

```python
class MobileGrabber:
    def __init__(self, max_retries: int = 20, click_interval_ms: int = 50,
                 confirm_clicks: int = 10):
        ...

    def click_buy(self, device, on_log) -> bool:
        # 连点策略，最多 max_retries 次，间隔 click_interval_ms
        # 每次按优先级尝试文字匹配：
        #   "立即抢购" → "立即购买" → "立即预订" → "选座购买" → "确定"
        # 找不到则坐标兜底点击 (75%, 92%)
        # 每次点击后检测是否进入订单页：
        #   device(text="提交订单").exists 或 device(textContains="¥").exists
        # 检测到则 return True

    def confirm_order(self, device, on_log) -> bool:
        # 先快速尝试文字匹配 "提交订单"（timeout=0.3s）
        # 无论是否找到，坐标连点 (80%, 92%) × confirm_clicks 次
        # 再兜底连点 confirm_clicks 次

    def run(self, device, on_log) -> GrabResult:
        # Step 1: click_buy
        # Step 2: confirm_order
        # 返回 GrabResult(success, message, elapsed_ms)
        # 复用 core/grabber.py 中的 GrabResult 数据类
```

### `gui/mobile_worker.py`

#### MobileGrabWorker 类

与 `GrabWorker` 平行的 QThread，信号接口完全一致：

```python
class MobileGrabWorker(QThread):
    log_message = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    countdown_tick = pyqtSignal(float)
    grab_finished = pyqtSignal(bool, str)

    def __init__(self, device_serial, target_time, ntp_servers,
                 ntp_timeout, grab_config):
        ...

    def run(self):
        # 1. NTP 校时（复用 NTPTimer）
        # 2. 连接手机（MobileDevice.connect）
        # 3. 检测大麦 APP 前台
        # 4. 倒计时等待（提前 advance_seconds 秒结束等待）
        # 5. 调用 MobileGrabber.run()
        # 6. 发射 grab_finished 信号
```

## GUI 改造

### MainWindow 布局变化

```
┌─ 控制面板 ──────────────────────────────────────┐
│  抢票模式:  ○ 桌面端(Chrome)   ● 移动端(APP)    │  ← 新增 QRadioButton
│                                                  │
│  [连接手机]          手机: 未连接                 │  ← 移动端模式下显示
│  [启动浏览器]        浏览器: 未启动               │  ← 桌面端模式下显示
│                                                  │
│  开票时间: [2026-05-15 20:00:00]  [开始] [停止]  │  ← 共享
│                                                  │
│  ============ 00:05:32.147 ============          │  ← 共享
└──────────────────────────────────────────────────┘
```

### 切换行为

- 切换到"移动端"：隐藏"启动浏览器"行，显示"连接手机"行
- 切换到"桌面端"：反之
- 点击"开始抢票"时，根据当前模式创建 GrabWorker 或 MobileGrabWorker
- 两个 Worker 的信号都连接到相同的 slot（_log, _on_countdown_tick, _on_grab_finished 等）

### 日志输出示例（移动端）

```
[20:00:00.000] 抢票模式: 移动端(APP)
[20:00:00.050] 正在同步NTP时间...
[20:00:00.320] NTP校时完成，偏移量: +12.3ms
[20:00:00.350] 正在连接手机...
[20:00:00.580] 已连接: Xiaomi 14 (1080×2400)
[20:00:00.600] 大麦APP已在前台
[20:00:00.610] 等待开票时间... 目标: 20:00:30
[20:00:29.500] 提前 0.5 秒开始点击
[20:00:29.500] Step 1: 疯狂点击购买按钮
[20:00:29.550] 第 1 次尝试 — 点击了「立即预订」
[20:00:29.600] 第 2 次尝试 — 点击了「立即预订」
[20:00:29.780] 第 6 次尝试 — 检测到订单页面
[20:00:29.780] Step 2: 确认订单 — 连点中
[20:00:29.830] 点击了「提交订单」
[20:00:29.880] 坐标连点 (80%, 92%) × 10
[20:00:30.120] 抢票完成！总耗时 620ms，请在手机上完成支付
```

### 错误处理日志

连接失败时提供可操作的指引：

```
[20:00:00.100] 正在连接手机...
[20:00:00.500] 连接失败: 未检测到 Android 设备
[20:00:00.500] 请检查:
[20:00:00.510]   1. 手机已通过 USB 数据线连接电脑
[20:00:00.510]   2. 手机已开启 USB 调试（开发者选项中）
[20:00:00.510]   3. 手机弹窗已点击「允许 USB 调试」
```

首次初始化时：

```
[20:00:00.600] 首次连接，正在初始化 uiautomator2 服务...
[20:00:00.610] 请在手机上允许安装辅助应用（仅首次需要）
[20:00:05.200] 初始化完成
```

## 配置扩展

### config.json

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

| 参数 | 说明 |
|------|------|
| `mode` | 上次使用的模式，启动时自动恢复。值: `"desktop"` / `"mobile"` |
| `mobile.device_serial` | 设备序列号，留空自动检测 USB 设备 |
| `mobile.max_retries` | 购买按钮连点最大次数 |
| `mobile.click_interval_ms` | 连点间隔（毫秒） |
| `mobile.confirm_clicks` | 确认订单坐标连点次数 |
| `mobile.advance_seconds` | 提前开始点击的秒数 |

### utils/config.py

`DEFAULT_CONFIG` 中新增 `mode` 和 `mobile` 段，`_deep_merge` 逻辑无需修改。

## 部署

### 依赖更新

requirements.txt 新增：

```
uiautomator2>=3.0
```

系统级依赖：ADB（android-platform-tools），由安装脚本处理。

### macOS 一键安装（`setup.command`）

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== DamaiGrabber 安装 ==="

# 1. 检测 Python3
if ! command -v python3 &>/dev/null; then
    echo "错误: 未找到 Python3，请先安装"
    exit 1
fi

# 2. 创建虚拟环境并安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. 安装 Playwright Chromium（桌面端需要）
python3 -m playwright install chromium

# 4. 检测/安装 ADB（移动端需要）
if ! command -v adb &>/dev/null; then
    echo "正在安装 ADB..."
    if command -v brew &>/dev/null; then
        brew install android-platform-tools
    else
        echo "请手动安装 ADB: brew install android-platform-tools"
    fi
fi

# 5. 检测手机连接
echo ""
echo "=== 移动端配置（可选）==="
echo "如需使用移动端抢票，请:"
echo "  1. 手机开启 USB 调试"
echo "  2. 用数据线连接电脑"
echo "  3. 手机弹窗点击「允许 USB 调试」"
if command -v adb &>/dev/null; then
    adb devices
fi

echo ""
echo "=== 安装完成！==="
echo "运行: source .venv/bin/activate && python3 main.py"
```

### Windows 安装（`setup.bat`）

```batch
@echo off
echo === DamaiGrabber 安装 ===

python3 -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
python -m playwright install chromium

where adb >nul 2>&1
if errorlevel 1 (
    echo [提示] 移动端抢票需要 ADB，请下载 Android Platform Tools 并添加到 PATH
    echo 下载地址: https://developer.android.com/tools/releases/platform-tools
)

echo === 安装完成！===
echo 运行: .venv\Scripts\activate.bat ^&^& python main.py
```

### 现有 start.command 更新

```bash
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null
python3 main.py
```

## Android 手机端准备

| 步骤 | 操作 | 频次 |
|------|------|------|
| 开启开发者模式 | 设置 → 关于手机 → 连点"版本号"7 次 | 一次性 |
| 开启 USB 调试 | 设置 → 开发者选项 → USB 调试 | 一次性 |
| USB 连接电脑 | 数据线连接，弹窗点"允许"（勾选"始终允许"） | 一次性 |
| 安装大麦 APP | 应用商店下载，登录账号 | 一次性 |
| uiautomator2 初始化 | 首次连接自动推送 atx-agent，手机点"允许安装" | 一次性/自动 |

不需要 root，不需要手动安装额外 APP。

## 项目结构变化

```
├── main.py
├── start.command             # 更新：激活 venv
├── setup.command             # 新增：macOS 一键安装
├── setup.bat                 # 新增：Windows 一键安装
├── config.json               # 更新：新增 mode + mobile 段
├── requirements.txt          # 更新：新增 uiautomator2
├── core/
│   ├── browser.py            # 不变
│   ├── timer.py              # 不变
│   ├── grabber.py            # 不变（GrabResult 被 mobile_grabber 复用）
│   └── mobile_grabber.py     # 新增：MobileDevice + MobileGrabber
├── gui/
│   ├── worker.py             # 不变
│   ├── mobile_worker.py      # 新增：MobileGrabWorker
│   └── main_window.py        # 修改：模式切换 UI + 连接手机按钮
├── utils/
│   └── config.py             # 修改：DEFAULT_CONFIG 新增 mobile 段
└── tests/
    ├── test_mobile_grabber.py # 新增
    └── ...
```

## 测试策略

- `test_mobile_grabber.py`：mock `uiautomator2.Device`，测试 click_buy / confirm_order 的重试逻辑、兜底坐标逻辑、GrabResult 返回值
- 现有测试不受影响（桌面端模块无改动）
