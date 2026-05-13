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
