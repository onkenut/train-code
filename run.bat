@echo off
chcp 65001 >nul
title Remote Desktop Server

:: 检查管理员权限
fltmc >nul 2>&1 || (
    echo 正在请求管理员权限...
    powershell -Command "Start-Process cmd -ArgumentList '/c cd /d %~dp0 && %~nx0' -Verb RunAs"
    exit /b
)

echo ========================================
echo   远程桌面控制服务端
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

:: 检查 FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 未找到 FFmpeg，请确保 FFmpeg 已添加到系统 PATH
    echo.
)

:: 安装依赖
echo [1/3] 检查并安装依赖...
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

:: 启动服务
echo [2/3] 启动服务...
echo.
echo ========================================
echo   服务启动中...
echo   HTTP 服务: http://0.0.0.0:8000
echo   视频流:   http://0.0.0.0:8081/live.flv
echo ========================================
echo.
echo 提示: 请确保防火墙放行 TCP 8000 和 8081 端口
echo.

python app.py

pause
