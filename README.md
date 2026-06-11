# SmartLit - 智能文献管理器

SmartLit 是一款面向科研人员、学生及技术写作者的桌面应用，专注于本地 PDF 文献的管理、阅读、标注与 AI 辅助分析。

## ✨ 功能特性

### 📚 文献管理
- **多种导入方式**：手动添加、文件夹批量导入、拖放导入
- **自动元数据解析**：标题、作者、年份、DOI、期刊等
- **元数据编辑**：支持手动修正所有元数据字段
- **阅读状态**：未读 / 已读 / 精读 三级状态
- **评分系统**：1-5 星评分
- **归档功能**：支持文献归档与取消归档

### 📖 阅读与标注
- **内置 PDF 阅读器**：基于 PyMuPDF 渲染，支持缩放、翻页
- **多种标注样式**：高亮、下划线、删除线、文本框
- **自定义颜色**：多种标注颜色可选
- **标注管理**：按页码排序，点击跳转
- **标注导出**：支持 Markdown 格式导出

### 🤖 AI 辅助功能
- **自动摘要**：基于 KeyBERT 提取关键句生成摘要
- **关键词提取**：自动提取 5-10 个关键词
- **语义搜索**：基于 SentenceTransformer 的语义相似度搜索
- **引用关系发现**：自动扫描参考文献，建立引用网络
- **缓存机制**：AI 结果内存 + 数据库双层缓存

### 🏷️ 组织与分类
- **标签系统**：彩色标签，支持多标签筛选（AND/OR 逻辑）
- **笔记关联**：每篇文献可关联多个 Markdown 笔记
- **虚拟文件夹**：基于搜索条件的动态文件夹（规划中）

### 🔍 搜索功能
- **全文搜索**：基于 SQLite FTS5 的 BM25 全文检索
- **布尔运算符**：支持 AND、OR、NOT 语法
- **高级过滤**：按标签、作者、年份、状态、评分组合过滤
- **语义搜索**：自然语言查询，返回最相关文献

### 📊 统计与可视化
- **文献概览**：总文献数、阅读状态分布
- **标签分布**：饼图展示标签使用情况
- **年度发表分布**：柱状图展示文献发表年份
- **阅读状态统计**：各状态文献数量对比

### 📤 数据导出
- **BibTeX 导出**：方便导入 LaTeX / Zotero 等工具
- **标注导出**：Markdown 格式
- **笔记导出**：Markdown 格式（规划中）

## 🛠️ 技术栈

| 类别 | 技术/库 | 说明 |
|------|---------|------|
| 后端语言 | Python 3.10+ | 生态丰富，易于集成 AI 库 |
| GUI 框架 | PySide6 | Qt 原生体验，跨平台稳定 |
| 数据库 | SQLite + FTS5 | 零配置，单文件存储，支持全文检索 |
| 缓存 | cachetools | LRU/TTL 双层缓存 |
| PDF 解析 | PyMuPDF | 快速提取文本、元数据、渲染页面 |
| AI 推理 | sentence-transformers + KeyBERT | 中文友好，CPU 可运行 |
| 图表可视化 | matplotlib | 统计图表展示 |
| 打包 | PyInstaller | 打包为独立可执行文件 |

## 📋 环境要求

- **Python**: 3.10 或更高版本
- **操作系统**: Windows 10/11、macOS 12+、Linux (Ubuntu 22.04+)
- **磁盘空间**: 至少 500 MB（含模型文件）
- **建议配置**: Intel i5 或同等性能 CPU，内存 8 GB 以上

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd SmartLit
```

### 2. 创建虚拟环境

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 运行应用

```bash
python run.py
```

首次运行时，应用会自动：
- 创建数据目录（`%APPDATA%/SmartLit` 或 `~/.local/share/SmartLit`）
- 初始化 SQLite 数据库
- 创建日志文件夹

## 📁 项目结构

```
smartlit/
├── __init__.py              # 包初始化
├── main.py                  # 应用入口
├── config.py                # 配置管理
├── constants.py             # 常量定义
├── db/                      # 数据访问层
│   ├── __init__.py
│   ├── database.py          # 数据库连接与初始化
│   ├── models.py            # 数据模型
│   └── repositories.py      # 仓储模式实现
├── services/                # 服务层
│   ├── __init__.py
│   ├── library_service.py   # 文献管理服务
│   ├── pdf_service.py       # PDF 解析服务
│   ├── ai_service.py        # AI 服务（摘要/关键词/语义搜索）
│   └── search_service.py    # 搜索服务
├── infrastructure/          # 基础设施层
│   ├── __init__.py
│   ├── cache_manager.py     # 缓存管理器
│   └── logger.py            # 日志系统
└── gui/                     # UI 层
    ├── __init__.py
    ├── main_window.py       # 主窗口
    ├── sidebar_panel.py     # 左侧边栏（搜索/筛选/标签）
    ├── library_panel.py     # 文献列表面板
    ├── detail_panel.py      # 详情面板
    ├── pdf_viewer.py        # PDF 阅读器组件
    ├── stats_dashboard.py   # 统计仪表盘
    ├── dialogs.py           # 对话框
    └── workers.py           # 后台工作线程
```

## 🎯 架构设计

采用经典的四层架构：

1. **UI 层**：基于 PySide6 的窗口组件，负责交互呈现
2. **服务层**：封装业务逻辑，包括文献管理、AI、搜索等服务
3. **数据访问层**：通过仓储模式封装数据库 CRUD 操作
4. **基础设施层**：缓存管理器、日志系统、配置管理等

所有耗时操作（AI 推理、PDF 解析）均在后台线程执行，通过信号机制更新 UI。

## 💾 数据存储

所有数据存储在用户本地，遵循操作系统规范：

- **Windows**: `%APPDATA%\SmartLit`
- **macOS**: `~/Library/Application Support/SmartLit`
- **Linux**: `~/.local/share/SmartLit`

包含：
- `smartlit.db` - SQLite 数据库
- `logs/` - 运行日志
- `notes/` - 笔记文件
- `models/` - AI 模型文件

## 🔒 隐私与安全

- ✅ 所有数据本地存储，不上传云端
- ✅ 无任何遥测或匿名统计
- ✅ PDF 原文不被修改（只读）
- ✅ 用户可随时删除全部数据

## 📝 更新日志

### v1.0.0
- 初始版本发布
- 文献管理、PDF 阅读、标注功能
- AI 摘要、关键词提取、语义搜索
- 标签系统、笔记关联
- 全文搜索与高级过滤
- 统计仪表盘

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License
