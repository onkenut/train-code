# Remote Desktop - 局域网远程桌面控制

生产级局域网远程桌面控制方案，平板通过浏览器实时观看并控制笔记本桌面。

## 特性

- **零安装**: 平板端仅需浏览器，无需 APP/插件
- **硬件加速**: NVIDIA NVENC 独显编码，零 CPU 负担
- **低延迟**: HTTP-FLV + 零缓冲配置，端到端延迟 < 200ms
- **零延迟控制**: win32api SendInput 硬件级注入，穿透 UAC
- **触控手势**: 单指点击/滑动/长按、双指滚轮、拖拽等完整手势
- **虚拟键盘**: 粘滞修饰键、组合键预设、中文文本粘贴
- **PWA 支持**: 添加到主屏幕，全屏体验

## 技术栈

### 服务端 (笔记本)
- Python 3.9+ + Flask + Flask-SocketIO (Eventlet)
- FFmpeg: ddagrab/NVENC 硬件采集编码，HTTP-FLV 推流
- pywin32: SendInput 键鼠注入，剪贴板操作

### 前端 (平板浏览器)
- flv.js: MSE 低延迟直播播放
- Socket.IO Client: 实时信令通信
- 原生触控事件: 手势识别与坐标映射

## 环境要求

### 笔记本
- Windows 10/11
- NVIDIA 独立显卡 (推荐，支持 NVENC)
- Python 3.9 - 3.12 (推荐 3.10/3.11)
- FFmpeg (已添加到系统 PATH)
- 管理员权限运行

### 平板
- Chrome 85+ / Safari 12+ (支持 MSE 和 WebSocket)
- 同一局域网

## 快速开始

### 0. 环境准备

确保已安装：
- Python 3.9 - 3.12 (推荐 3.10/3.11)
- FFmpeg (已添加到系统 PATH)

验证:
```bash
python --version
ffmpeg -version
```

### 1. 启动服务

**方式一：双击运行 (推荐)**
```
双击 run.bat
```
自动请求管理员权限，安装依赖并启动。

**方式二：命令行启动**
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 以管理员身份运行 PowerShell/CMD，然后执行：
python app.py
```

**注意**: 必须以管理员身份运行，否则键鼠控制功能受限。

### 2. 平板连接

1. 确保平板与笔记本在同一局域网
2. 打开平板浏览器，访问: `http://<笔记本IP>:8000`
3. 建议"添加到主屏幕"获得全屏体验

## 网络端口

| 端口 | 协议 | 用途 |
|------|------|------|
| 8000 | TCP | HTTP + WebSocket 服务 |
| 8081 | TCP | HTTP-FLV 视频流 |

**注意**: 请确保 Windows 防火墙放行以上端口。

## 触控手势

| 手势 | 操作 |
|------|------|
| 单指点击 | 鼠标左键单击 |
| 单指长按 (>500ms) | 鼠标右键 |
| 单指滑动 | 移动鼠标指针 |
| 单指点按并滑动 | 鼠标左键拖拽 |
| 双指滑动 | 鼠标滚轮 (纵向/横向) |

## 虚拟键盘

- **修饰键 (Ctrl/Shift/Alt/Win)**: 粘滞键设计，点击高亮保持，再点击释放
- **功能键**: Esc, Tab, Enter, Backspace, Delete, 方向键
- **快捷预设**: Alt+F4, Ctrl+W, 任务管理器, Alt+Tab, 显示桌面
- **文本输入**: 点击输入框唤起原生键盘，支持中文，自动粘贴发送

## 项目结构

```
RemoteDesktop/
├── app.py                 # Flask + SocketIO 主程序
├── run.bat                # Windows 启动脚本 (自动提权)
├── requirements.txt       # Python 依赖
├── modules/
│   ├── __init__.py
│   ├── input_control.py   # 键鼠控制 (SendInput)
│   ├── clipboard.py       # 剪贴板文本粘贴
│   └── streamer.py        # FFmpeg 推流管理
├── templates/
│   └── index.html         # 前端页面
└── static/
    ├── css/style.css      # 样式
    ├── js/app.js          # 前端逻辑 (手势/键盘/播放)
    └── manifest.json      # PWA 配置
```

## 架构说明

### 数据流向
```
[笔记本服务端]
    FFmpeg ddagrab/NVENC → HTTP-FLV (:8081) ← 平板浏览器 flv.js
    Flask-SocketIO (:8000) ← WebSocket → 平板浏览器
        ↓
    win32api SendInput → 桌面系统 (键鼠控制)
    win32clipboard + Ctrl+V → 桌面系统 (文本输入)
```

### 关键优化点
1. **NVENC 编码**: `-tune zerolatency -bf 0 -g 30` 关闭 B 帧，减小 GOP
2. **flv.js 配置**: `liveBufferLength: 0` 极小缓冲，追帧播放
3. **Eventlet 异步**: 防止高频键鼠指令阻塞 WebSocket 心跳
4. **SendInput 注入**: 硬件级扫描码，无视 UAC，零延迟执行
5. **剪贴板中转**: 中文/长文本通过剪贴板粘贴，解决输入法问题

## 注意事项

1. **必须以管理员身份运行**，否则无法穿透 UAC 窗口注入输入
2. 音频捕获依赖系统"立体声混音"或安装 VB-Cable
3. 无独显机器自动回退到 gdigrab + libx264 软编码
4. 仅限内网使用，无鉴权机制，请勿暴露到公网
5. 首次运行会自动安装 Python 依赖

## 常见问题

**Q: 启动报错 `ModuleNotFoundError: No module named 'distutils'`？**
- 这是 Python 3.12+ 的兼容性问题，请确保使用 `requirements.txt` 中的 eventlet >= 0.35.0
- 执行: `pip install --upgrade -r requirements.txt`

**Q: 导入模块失败？**
- 确保在项目根目录执行 `python app.py`
- 确保已安装所有依赖: `pip install -r requirements.txt`
- 如果 pywin32 导入失败，尝试: `pip install pywin32 --upgrade`

**Q: 视频无法播放？**
- 检查 FFmpeg 是否正确安装并添加到 PATH
- 确认防火墙放行 8081 端口
- 浏览器控制台查看具体错误

**Q: 键鼠无响应？**
- 确认以管理员身份运行
- 检查目标窗口是否为 UAC 提升权限窗口

**Q: 延迟很高？**
- 确认使用 NVENC 硬件编码 (查看启动日志)
- 降低视频码率或帧率
- 确保网络为 5G WiFi，信号良好

**Q: 中文无法输入？**
- 使用虚拟键盘的文本输入框，通过剪贴板通道发送
