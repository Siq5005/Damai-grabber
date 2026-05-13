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
