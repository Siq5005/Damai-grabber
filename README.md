# DamaiGrabber — 大麦网抢票工具

一个桌面 GUI 工具，帮助你在大麦网开票瞬间自动完成"点击购买"和"确认订单"两个操作。支持桌面端（Chrome 浏览器）**和**移动端（Android 手机 APP）两种抢票模式。初衷是为了帮我抢音律联觉的票，不过可能ipad的台前调度更好用也说不定。本质比不过脚本操作，单纯就是校准时间加前台快速点击，脚本直接发包肯定更稳。

## 两种抢票模式

### 桌面端模式（Chrome）

通过 Chrome 调试协议（CDP）连接浏览器，适用于支持网页下单的票。

```
你手动完成：登录 → 选演出 → 选场次/票价/观演人 → 停在购买页面
工具自动完成：NTP校时 → 精准倒计时 → 点击"立即购买" → 点击"提交订单"
你手动完成：支付
```

### 移动端模式（Android APP）

通过 uiautomator2 + USB 控制手机上的大麦 APP，适用于**仅APP下单**的票。

```
你手动完成：手机登录大麦APP → 选演出 → 选场次/票价/观演人 → 停在购买页面
工具自动完成：NTP校时 → 精准倒计时 → 连点"立即购票" → 连点"提交订单"
你手动完成：在手机上支付
```

## 技术栈

- Python 3.9+ / PyQt6（GUI）
- Playwright（桌面端浏览器自动化，通过 CDP 协议连接）
- 内联 JS 反检测（去自动化指纹，无第三方依赖）
- uiautomator2 2.16.26（移动端 Android 设备控制；钉在 2.x — 3.x 在 HyperOS 2 / Android 15 等系统上点击会被 `INJECT_EVENTS` 拦截，详见下方[故障排查](#故障排查)）
- ntplib（NTP 时间同步）

## 安装

### 一键安装（推荐）

**macOS**：双击 `setup.command`

**Windows**：双击 `setup.bat`

安装脚本会自动完成：创建虚拟环境 → 安装 Python 依赖 → 安装 Playwright Chromium → 检测/安装 ADB

### 手动安装

```bash
git clone https://github.com/Siq5005/Damai-grabber.git
cd Damai-grabber
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate.bat
pip install -r requirements.txt
python3 -m playwright install chromium
```

移动端还需要 ADB：
```bash
# macOS
brew install android-platform-tools

# Windows: 下载 Android Platform Tools 并添加到 PATH
# https://developer.android.com/tools/releases/platform-tools
```

## 使用方法

### 启动

```bash
python3 main.py
```

macOS 用户也可以直接双击 `start.command`。

### 桌面端抢票流程

1. 选择"桌面端(Chrome)"模式
2. 点击"启动浏览器" — Chrome 以调试模式打开
3. 在 Chrome 中完成准备：登录大麦网、进入演出页面、选好场次/票价/观演人
4. 回到工具，设置开票时间，点击"开始抢票"
5. 工具自动执行：NTP 校时 → 倒计时 → 点击购买 → 确认订单
6. 在浏览器中手动完成支付

### 移动端抢票流程

1. 手机开启 USB 调试（设置 → 关于手机 → 连点版本号 7 次 → 开发者选项 → USB 调试）
2. 用数据线连接电脑，手机弹窗点"允许 USB 调试"
3. 选择"移动端(APP)"模式，点击"连接手机"确认连接成功
4. 在手机上打开大麦 APP，完成准备：登录、进入演出页面、选好场次/票价/观演人
5. 设置开票时间，点击"开始抢票"
6. 工具自动执行：NTP 校时 → 倒计时 → 连点购买 → 连点确认
7. 在手机上完成支付

> HyperOS / MIUI 等系统限制「程序从后台拉起其他 App」，本工具不会自动启动大麦——**抢票前请手动把大麦开到购票页并保持前台**，工具只负责到点点击（开始前会检查前台是否为大麦并提示）。
>
> 提交订单遇拥堵时大麦会弹「请重试」弹窗，工具会自动持续点弹窗里的「重试」按钮直到提交成功（跳支付页）或超时（`mobile.confirm_timeout_s`，默认 20s）。

## 故障排查

### 移动端点击报 `INJECT_EVENTS` / `SecurityException`

**现象**：移动端抢票点击时（或日志里）出现

```
java.lang.SecurityException: Injecting input events requires the caller ... to have the INJECT_EVENTS permission
```

**原因**：HyperOS 2（小米 15 等）/ Android 15 等系统在 `injectInputEventToTarget`（定向输入注入 API）处拒绝跨应用注入。`uiautomator2` **3.x** 的 WeTest jar 服务端、以及 `adb shell input tap` 都走这个定向 API，所以全部失败——这是系统级拦截，与「USB 调试（安全设置）」开关**无关**，开了也拦。未 root 的设备（bootloader 锁定）连 `su` 兜底也用不上。

**解决**：本工具已把 `uiautomator2` 钉在 **2.16.26**（见 `requirements.txt`）。2.x 用经典**非定向** `UiAutomation.injectInputEvent`（UiAutomation 的特权注入路径，不需要 `INJECT_EVENTS`），可正常点击。若你的环境被升级到了 3.x，降回即可：

```bash
pip install uiautomator2==2.16.26
```

`core/mobile_grabber.py` 内还内置了注入降级兜底：uia 注入若仍失败，会自动依次尝试 `shell input` → `adb input` → `su input`（需 root），并打印清晰提示。正常设备上走 uia 层即可，不会触发兜底。

### 大麦无法被自动切到前台

HyperOS / MIUI 限制后台拉起 App。请**手动**把大麦开到购票页并保持前台（见上文移动端流程的提示）。

## 配置

编辑 `config.json` 自定义参数：

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
    "confirm_timeout_s": 20,
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
| `mode` | 上次使用的模式（`desktop` / `mobile`），启动时自动恢复 |
| `chrome_path` | Chrome 路径，留空自动检测 |
| `debug_port` | Chrome 调试端口 |
| `grab.max_retries` | 桌面端最大重试次数 |
| `grab.poll_interval_ms` | 桌面端按钮检测间隔（毫秒） |
| `mobile.device_serial` | Android 设备序列号，留空自动检测 |
| `mobile.max_retries` | 移动端购买按钮连点次数 |
| `mobile.click_interval_ms` | 移动端连点间隔（毫秒） |
| `mobile.confirm_timeout_s` | 移动端提交订单重试超时（秒，默认 20）；拥堵弹「重试」时持续重试到此超时 |
| `mobile.advance_seconds` | 提前开始点击的秒数 |

## 反检测说明

本工具的核心是「人工登录 + 人工选好 + 程序在开票瞬间帮你点击」，连接的是你自己登录的真实浏览器/手机，账号行为均由真人产生，并非传统意义上的爬虫。为降低被风控误判、保护账号，做了以下处理：

- **桌面端去自动化指纹**：启动 Chrome 时带 `--disable-blink-features=AutomationControlled`，消除最明显的 `navigator.webdriver` 标志。
- **stealth 注入双途径**：`core/stealth.py` 用内联 JS 抹掉常见自动化特征（`chrome.runtime`、`navigator.languages`、`plugins` 等）。既通过 `add_init_script` 覆盖「点击购买后跳转的订单页」，也对当前已加载页面立即 `evaluate` 打补丁。
- **移动端随机抖动**：连点间隔加 ±30% 抖动、坐标落点加 ±6 像素偏移，避免完美的机械节奏被标记，也更像真人操作。

> 注意：滑块验证码、二次校验、服务端排队/库存分配等属于硬限制，工具无法绕过。请合理使用，遵守大麦网服务条款。

## 项目结构

```
├── main.py              # 应用入口
├── start.command        # macOS 双击启动
├── setup.command        # macOS 一键安装
├── setup.bat            # Windows 一键安装
├── config.json          # 用户配置
├── core/
│   ├── browser.py       # Chrome CDP 连接管理
│   ├── timer.py         # NTP 校时 + 精准等待
│   ├── grabber.py       # 桌面端抢票执行器
│   ├── mobile_grabber.py # 移动端抢票执行器（uiautomator2）
│   └── stealth.py       # 反检测注入（去自动化指纹）
├── gui/
│   ├── worker.py        # 桌面端工作线程
│   ├── mobile_worker.py # 移动端工作线程
│   └── main_window.py   # PyQt6 主窗口（模式切换）
├── utils/
│   └── config.py        # 配置加载/保存
└── tests/               # 单元测试
```

## 免责声明

本项目仅供学习和个人使用，请遵守大麦网的服务条款。请勿将本工具用于商业倒票或其他违法用途。使用本工具产生的任何后果由用户自行承担。
