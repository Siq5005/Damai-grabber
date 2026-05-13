# DamaiGrabber — 大麦网抢票工具

一个桌面 GUI 工具，帮助你在大麦网开票瞬间自动完成"点击购买"和"确认订单"两个操作。其实是为了方便我抢各种二游演唱会的门票。

## 工作原理

你在自己的浏览器中完成登录、选演出、选场次/票价/观演人等准备工作，工具通过 Chrome 调试协议（CDP）连接到你的浏览器，在开票时间精准执行抢票动作。

```
你手动完成：登录 → 选演出 → 选场次/票价/观演人 → 停在购买页面
工具自动完成：NTP校时 → 精准倒计时 → 点击"立即购买" → 点击"提交订单"
你手动完成：支付
```

## 技术栈

- Python 3.9+ / PyQt6（GUI）
- Playwright（浏览器自动化，通过 CDP 协议连接）
- playwright-stealth（反检测）
- ntplib（NTP 时间同步）

## 安装

```bash
git clone https://github.com/Siq5005/Damai-grabber.git
cd Damai-grabber
pip install -r requirements.txt
playwright install chromium
```

## 使用方法

### 启动

```bash
python3 main.py
```

macOS 用户也可以直接双击 `start.command` 文件。

### 抢票流程

1. 点击"启动浏览器" — Chrome 以调试模式打开
2. 在 Chrome 中完成准备：
   - 登录大麦网
   - 进入目标演出页面
   - 选好场次、票价档位、观演人
   - 停留在演出详情页
3. 回到工具，设置开票时间，点击"开始抢票"
4. 工具自动执行：NTP 校时 → 倒计时 → 点击购买 → 确认订单
5. 在浏览器中手动完成支付

## 配置

编辑 `config.json` 自定义参数：

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

| 参数 | 说明 |
|------|------|
| `chrome_path` | Chrome 路径，留空自动检测 |
| `debug_port` | Chrome 调试端口 |
| `max_retries` | 最大重试次数 |
| `retry_interval_ms` | 重试间隔（毫秒） |
| `poll_interval_ms` | 按钮检测轮询间隔（毫秒） |
| `confirm_timeout_ms` | 确认订单页面等待超时（毫秒） |

## 项目结构

```
├── main.py              # 应用入口
├── start.command        # macOS 双击启动
├── config.json          # 用户配置
├── core/
│   ├── browser.py       # Chrome CDP 连接管理
│   ├── timer.py         # NTP 校时 + 精准等待
│   └── grabber.py       # 抢票执行器
├── gui/
│   ├── worker.py        # 异步工作线程
│   └── main_window.py   # PyQt6 主窗口
├── utils/
│   └── config.py        # 配置加载/保存
└── tests/               # 单元测试
```

## 免责声明

本项目仅供学习和个人使用，请遵守大麦网的服务条款。请勿将本工具用于商业倒票或其他违法用途。使用本工具产生的任何后果由用户自行承担。
