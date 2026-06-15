# PixelVault - 本地多媒体资产管理与智能检索中枢

面向摄影师、设计师及数字内容收藏者的本地多媒体资产管理系统。零数据上云，支持语义检索、智能去重、AI 视觉理解与沉浸式浏览。

## 核心特性

- **自然语言语义检索**：输入"落日下的海滩"、"红色的车"等自然语言即可搜索图片，基于 CLIP 零样本学习
- **智能去重**：MD5 精准去重 + pHash 感知哈希相似图检测，支持连拍/微调构图/不同分辨率版本识别
- **AI 视觉理解**：本地 CLIP 模型编码、InsightFace 人脸检测聚类、自动场景标签
- **深度元数据解析**：EXIF 全量提取、GPS 坐标、视频编码信息、主色调分析
- **沉浸式浏览**：三栏布局，虚拟列表渲染，支持十万级图片丝滑滚动
- **绝对私有**：AI 推理全在本地完成，无任何数据上云
- **混合检索引擎**：语义 + FTS5 全文检索 + 结构化过滤，倒数秩融合重排

## 技术栈

| 层级 | 技术 |
|------|------|
| 桌面 GUI | PySide6 (Qt for Python) |
| 后端语言 | Python 3.10+ |
| 图像处理 | Pillow, OpenCV |
| 视频处理 | ffmpeg-python |
| 元数据 | Pillow EXIF, PyExifTool (可选) |
| 向量检索 | ONNX Runtime + CLIP |
| 人脸引擎 | InsightFace + scikit-learn DBSCAN |
| 数据库 | SQLite (WAL 模式) + FTS5 |
| 缓存 | cachetools LRUCache |
| 打包 | PyInstaller |
| 依赖管理 | Poetry |

## 项目结构

```
pixelvault/
├── __main__.py          # CLI 入口
├── app.py               # 应用调度：CLI 参数解析、GUI 启动
├── config.py            # 全局配置常量
├── database/            # 数据层
│   ├── connection.py    # SQLite 连接管理、建表、FTS5 触发器
│   ├── models.py        # 9 个数据模型 dataclass
│   └── dao.py           # 完整 DAO 层 + 向量检索
├── core/                # 核心业务
│   ├── scanner.py       # 文件扫描器 (ScannerOrchestrator)
│   ├── hasher.py        # MD5/SHA256 + pHash/dHash
│   ├── dedup.py         # 精准 + 感知去重 + 清理策略
│   ├── metadata.py      # EXIF/视频元数据提取
│   ├── thumbnail.py     # 多级缩略图生成缓存
│   ├── face_cluster.py  # DBSCAN 人脸聚类
│   ├── color.py         # KMeans 主色调提取
│   └── watcher.py       # 文件系统监听 (watchdog)
├── ai/                  # AI 引擎
│   ├── clip_engine.py   # CLIP ONNX 图像/文本编码
│   ├── face_engine.py   # InsightFace 人脸检测特征提取
│   ├── orchestrator.py  # AI 批量处理编排
│   └── tagger.py        # 零样本自动打标
├── search/              # 混合检索
│   ├── parser.py        # 查询语法解析器
│   ├── rank.py          # RRF + 加权融合排序
│   └── engine.py        # 混合检索引擎
├── gui/                 # PySide6 桌面界面
│   ├── main_window.py   # 主窗口 (三栏 Lightroom 布局)
│   ├── navigation.py    # 左栏：媒体库 + 人物群组
│   ├── browser.py       # 中栏：缩略图网格 + 列表 + 胶片条
│   ├── inspect.py       # 右栏：大图预览 + EXIF/标签/人脸
│   ├── search_bar.py    # 顶部搜索栏
│   └── workers.py       # 后台 QThread 工作线程
├── utils/               # 工具
│   ├── image.py         # 图像工具
│   ├── video.py         # 视频工具
│   └── cache.py         # LRU 内存 + 磁盘缓存
models/                  # ONNX 模型目录 (运行时放置)
build_scripts/           # PyInstaller 打包脚本
```

## 环境搭建

### 1. 前置要求

- Python 3.10+
- [Poetry](https://python-poetry.org/) 依赖管理
- FFmpeg 二进制 (PATH 中可用，视频功能用)

### 2. 安装依赖

```bash
# 克隆仓库并切换分支
git checkout PixelVault

# 安装核心依赖 (PySide6, SQLite, Pillow, OpenCV 等)
poetry install

# 安装 AI 功能依赖 (可选，本地 GPU/CPU 推理)
poetry install -E ai      # GPU 版本 (onnxruntime-gpu + insightface)
# 或 CPU 版本
poetry install -E cpu-ai  # CPU 版本 (onnxruntime + insightface)
```

### 3. 准备模型权重

将 ONNX 格式的 CLIP 模型和 InsightFace 模型放入 `models/` 目录。

开发环境可运行以下命令：

```bash
# 数据库初始化
poetry run pixelvault db upgrade
```

## 使用方法

### GUI 模式

```bash
# 开发模式 (带调试日志)
poetry run pixelvault run --dev

# 正常模式
poetry run pixelvault run
```

### CLI 模式

```bash
# 添加目录并扫描
poetry run pixelvault scan /path/to/photos

# 强制重建索引
poetry run pixelvault scan --force /path/to/photos

# 扫描所有媒体库
poetry run pixelvault scan

# 仅初始化数据库
poetry run pixelvault db upgrade
```

### 搜索语法

搜索栏同时支持自然语言和结构化过滤：

| 语法 | 示例 | 说明 |
|------|------|------|
| 自然语言 | `sunset beach` | 语义检索 |
| `type:` | `type:jpg` | 文件类型 (image/video/audio) |
| `year:` | `year:2024` | 按年份 |
| `after:` / `before:` | `after:2024-01-01` | 日期范围 |
| `camera:` | `camera:Canon` | 相机型号 |
| `color:` | `color:#FF0000` | 主色调 |
| `person:` | `person:张三` | 按人物 |
| `tag:` | `tag:landscape` | 按标签 |
| `minw:` / `minh:` | `minw:1920` | 最小分辨率 |

可自由组合，例如：`sunset beach year:2024 camera:Canon minw:1920`

## 打包分发

```bash
python build_scripts/build.py
```

PyInstaller 将自动打包 Python 环境、PySide6、ONNX 模型到独立可执行目录。

输出位置：`dist/PixelVault/`

## 性能指标

| 指标 | 目标值 |
|------|--------|
| 纯元数据扫描速度 | > 1000 张/分钟 (SSD) |
| 含 AI 向量化速度 | > 50 张/分钟 (视 CPU/GPU) |
| 十万级混合检索延迟 | < 300ms |
| 缩略图滚动帧率 | ≥ 60fps |
| 常驻内存 | < 500MB |
| AI 推理峰值内存 | < 2GB |

## 数据文件位置

| 内容 | 路径 |
|------|------|
| 数据库 | `~/.pixelvault/pixelvault.db` |
| 缩略图缓存 | `<系统临时目录>/pixelvault_thumbnails/` |
| 可覆盖配置 | `PIXELVAULT_DATA_DIR`, `PIXELVAULT_MODEL_DIR` 环境变量 |

## 许可证

本项目仅供个人使用与学习。
