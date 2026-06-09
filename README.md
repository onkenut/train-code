# PointVault — 三维点云标注与交互分析工具

![PySide6](https://img.shields.io/badge/UI-PySide6-green)
![Open3D](https://img.shields.io/badge/3D-Open3D-blue)
![SQLite](https://img.shields.io/badge/DB-SQLite-yellow)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

## 项目简介

**PointVault** 是面向研究者、开发者与学生的**个人桌面三维点云标注与交互分析工具**，定位介于专业工具（CloudCompare、SSE）与简单脚本之间。它提供：

- 📦 **项目化管理**：所有元数据、标注、操作历史持久化到 SQLite
- 📥 **多格式导入**：PLY / LAS / LAZ / XYZ / PCD / CSV
- 🖼️ **高性能 3D 渲染**：基于 Open3D，单窗口 10M 点 >30fps，支持多着色模式
- ✏️ **交互式标注**：矩形框选 / 套索 / 画笔 / RANSAC 平面，支持语义标签与实例 ID
- 🛠️ **预处理工具箱**：体素下采样、统计去噪、法向量估计、平面分割、ICP 配准
- ↩️ **命令模式撤销重做**：标注操作用 `索引+旧值`，几何操作用 `文件快照`
- 📤 **多格式导出**：带标签点云 / KITTI 风格数据集 / HTML 报告

---

## 1. 系统架构

### 1.1 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          PySide6 GUI 层                              │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  main_window.py                                               │  │
│  │  ┌──────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────┐   │  │
│  │  │菜单栏/工具│ │ 左侧 3 标签│ │ 3D 视图区  │ │ 右侧 4 标签 │   │  │
│  │  │栏/状态栏 │ │点云/标签/书签│ │(Viewer3D) │ │属性/统计/历│   │  │
│  │  └──────────┘ │            │ │            │ │史/日志     │   │  │
│  │               └────────────┘ └────────────┘ └─────────────┘   │  │
│  │                  dialogs.py (所有 QDialog 对话框)               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                               │ Signal/Slot                           │
│  ┌────────────────────────────▼───────────────────────────────────┐  │
│  │                       业务服务层 (app_service.py)               │  │
│  │  ProjectService  (项目/点云/标签集 CRUD)                         │  │
│  │  AnnotationService(分配标签/清除标注/撤销重做栈包装)              │  │
│  └────────────────────────────┬───────────────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                              │          核心逻辑层                    │
│  ┌───────────────────────────▼──────────────────────┐               │
│  │ rendering/              │  tools/                │               │
│  │   · renderer.py         │    · selection_tools.py│               │
│  │     SceneObject / PointCloudRenderer (Open3D)    │               │
│  │   · selection_pipeline  │    · preprocess.py     │               │
│  │     视锥体 6 平面+投影精筛│    体素/去噪/法向/RANSAC│               │
│  │   · color_mapper.py     │    · history.py        │               │
│  │     6 种着色模式         │    Command/CommandHistory│              │
│  │   · camera.py           │  exporter.py           │               │
│  │     6 标准视图/书签     │    带标签点云/数据集/报告│               │
│  └─────────────────────────┴────────────────────────┘               │
│                               │                                       │
│  ┌────────────────────────────▼───────────────────────────────────┐  │
│  │                       I/O 抽象层 (io/)                         │  │
│  │  · reader.py   : 多格式读（Open3D 优先 + 专用库回退）            │  │
│  │  · writer.py   : PLY/LAS/PCD/XYZ 写                            │  │
│  │  · label_file.py: .labels 二进制格式 (int32[] + PVLB footer)   │  │
│  │  · container.py: PointCloudData 纯 NumPy 容器                  │  │
│  └────────────────────────────┬───────────────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│  持久化层                     │                                       │
│  ┌───────────────────────────▼───────────────────────────────────┐  │
│  │                  db/ (SQLite + SQLAlchemy 2.0)                │  │
│  │  database.py    : 单例，WAL + mmap(256MB) + fkey_on           │  │
│  │  models.py      : 7 张核心表 (见 2 节)                         │  │
│  │  repositories.py: 5 个 Repository + RepositoryFactory          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  磁盘文件             pointclouds/*.ply        原始点云                │
│                       annotations/*.labels    标注整数数组              │
│                       snapshots/*.pcd         撤销/重做几何快照         │
│                       exports/...             导出产物                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 关键数据流（标注工作流）

```
用户拖拽矩形框选
       │
       ▼
 Viewer3DWidget.mouse_released  (Qt 信号)
       │
       ▼
 _on_viewer_mouse_released()
       │
       ▼
 SelectionPipeline.pick_rectangle(x, y, pts, w, h, ViewProj)
   ├─ 1) 构造 6 平面视锥体（近/远 + 矩形 4 边）
   ├─ 2) 逐点 AABB-SAT 粗筛 → 候选集
   └─ 3) 投影到 NDC，矩形测试 → 返回 SelectionResult(indices, count)
       │
       ▼
 _apply_selection_result()
   ├─ 构造 bool mask[N]，标记选中点
   └─ renderer.set_selection_mask(sid, mask)
       │
       ▼
 用户点击『分配给选中点』 (btn_assign_label.clicked)
       │
       ▼
 _on_assign_label()
       │
       ▼
 AnnotationService.assign_selected(sid, indices, label_id)
   ├─ 1) 从 .labels 文件读取旧值 [modified_indices]
   ├─ 2) 备份 .labels → snapshots/xxx_undo.labels
   ├─ 3) mmap .labels，写入新 label_id
   ├─ 4) 构建 AnnotationEditCommand 入 CommandHistory 栈
   ├─ 5) 更新 annotations 表 stats_json 直方图
   └─ 6) 通知 renderer.refresh_colors(sid)
       │
       ▼
 渲染器重新着色 → 屏幕上点按标签色显示
```

---

## 2. 数据库设计（SQLite + WAL）

### 2.1 核心表结构

| 表名 | 作用 | 关键字段 |
|---|---|---|
| `projects` | 项目元信息 | id, name, project_dir(唯一), description, created_at, last_opened_at |
| `pointclouds` | 点云记录与元数据 | id, project_id, name, file_path, file_format, num_points, min/max_xyz, file_size_bytes, has_colors/normals/intensity/classes(bool), transform_matrix(BLOB 4×4 float32), visible, created_at |
| `labelsets` | 标签集容器 | id, project_id, name, description, is_default |
| `label_definitions` | 标签定义（多对一 labelsets） | id, labelset_id, label_id(int), name, color_r/g/b;  UNIQUE(labelset_id, label_id) |
| `annotations` | 标注元数据 | id, pointcloud_id, labelset_id, label_file_path, stats_json(JSON), total_labeled, total_unlabeled; UNIQUE(pointcloud_id, labelset_id) |
| `operations_history` | 撤销/重做日志 | id, project_id, op_type(enum), description, timestamp, pointcloud_ids(JSON), undo_data(JSON), redo_data(JSON), snapshot_before, snapshot_after |
| `bookmarks` | 相机视图书签 | id, project_id, name, eye_xyz, lookat_xyz, up_xyz, fov_deg |

### 2.2 关键索引

```sql
CREATE INDEX ix_pc_project           ON pointclouds(project_id);
CREATE INDEX ix_pc_project_name      ON pointclouds(project_id, name);
CREATE INDEX ix_labeldef_setid       ON label_definitions(labelset_id);
CREATE INDEX ix_annot_pc_ls          ON annotations(pointcloud_id, labelset_id);
CREATE INDEX ix_history_project_time ON operations_history(project_id, timestamp DESC);
```

### 2.3 标注二进制文件格式（.labels）

为避免千万级点逐点写入 SQLite 的灾难性能，标注以**旁侧二进制文件**存储，DB 仅记录元数据。

```
文件布局：
+-----------------------------------------+
|  label array: N × int32 (LE)            |   字节 0 ~ N*4
+-----------------------------------------+
|  footer (12 byte):                      |
|  + magic b'PVLB'           (4B)         |   N*4    + 0
|  + num_points uint32 LE    (4B)         |   N*4    + 4
|  + crc32(array) uint32 LE   (4B)        |   N*4    + 8
+-----------------------------------------+
                                         = N*4 + 12 bytes 总大小
```

- **mmap 读取**：`LabelFileHandler.read_safe()` 校验 footer，1.4GB 内点云零拷贝
- **原子写入**：先写 `*.labels.tmp`，成功 `os.replace()` 覆盖
- **校验**：`zlib.crc32(array_bytes)` 防损坏
- **1千万点**：40MB / 文件，mmap 打开 <10ms

### 2.4 连接参数（性能优化）

```python
create_engine(url,
    connect_args={"check_same_thread": False},
    future=True,  # SQLAlchemy 2.0 风格
    execution_options={"isolation_level": "AUTOCOMMIT"},  # 交给 WAL
    pool_pre_ping=True,
)
# PRAGMA 初始化：
# journal_mode=WAL, synchronous=NORMAL, foreign_keys=ON
# mmap_size=268435456 (256MB), cache_size=-8000 (64MB)
```

---

## 3. 3D 交互与选择算法

### 3.1 视锥体 6 平面拾取管线（`selection_pipeline.py`）

```python
# 步骤 1：屏幕矩形 → 6 平面视锥体
def frustum_from_screen_rect(x1,y1,x2,y2, w,h, view, proj):
    # NDC: [-1,1]^3
    corners_ndc = [[-1,-1,-1], [ 1,-1,-1], [ 1, 1,-1], [-1, 1,-1],
                   [-1,-1, 1], [ 1,-1, 1], [ 1, 1, 1], [-1, 1, 1]]
    # 把用户矩形 x1,x2 映射到 NDC 的 x 轴
    # 世界空间 8 点 → 6 个平面（叉乘求平面法线，朝内）
    return Frustum(planes=[Plane, ...])

# 步骤 2：AABB vs 视锥体 SAT（Separating Axis Theorem）
class Frustum:
    def contains_points_bulk(self, xyz: (N,3)f32) -> (N,)bool:
        # 6 平面 × N 点 矩阵乘法: out = dot((xyz - p0), n) >= 0
        mask = np.ones(N, dtype=bool)
        for p in planes:
            mask &= (xyz @ p.n - p.d) >= -EPS  # 批量 dot
        return mask

# 步骤 3：逆投影精筛（矩形框选）
def refine_screen_mask(xyz_world, view_proj, w,h, x1,y1,x2,y2):
    clip = xyz_world @ view_proj.T              # (N,4)
    ndc  = clip[:,:3] / clip[:,3:4]             # 透视除法
    sx   = (ndc[:,0]*0.5+0.5) * w               # 像素 x
    sy   = (1 - (ndc[:,1]*0.5+0.5)) * h         # 像素 y（OpenGL→Qt）
    return (sx>=x1)&(sx<=x2)&(sy>=y1)&(sy<=y2)
```

复杂度：**O(N)** 向量化 NumPy；百万点 <100ms。若点云 ≥500M，可在 `contains_points_bulk` 之前插入**八叉树 BVH 粗筛**。

### 3.2 5 种选择工具

| 工具 | 拾取策略 | 典型耗时 (1M 点) |
|---|---|---|
| 矩形框选 | 视锥体 4 斜平面 + 近/远 → 矩形精筛 | ~80ms |
| 套索多边形 | 视锥体（逐边切平面）→ 屏幕 2D 射线法 | ~150ms |
| 画笔圆形 | 视锥体（锥台 6 平面）→ 屏幕圆形距离 | ~100ms |
| RANSAC 平面 | 屏幕射线 → 种子点 → 纯 NumPy SVD | ~200ms（500 迭代） |
| 单点击 | 最近点 + 球半径 5px | ~20ms |

### 3.3 选择→渲染更新

1. 渲染器每帧给每个 `SceneObject` 生成 `color[N,3]`
2. 若 `selection_mask[i]==True`，颜色 `= lerp(orig_color, HIGHLIGHT_YELLOW, 0.6)`（高亮叠加）
3. 着色模式为 `label` 时：`label[i]==UNLABELED ? height_gradient : color_map[label_id]`

---

## 4. 操作历史与撤销机制

### 4.1 Command 抽象

```python
@dataclass
class Command(ABC):
    description: str
    timestamp: datetime

    @abstractmethod
    def do(self)    -> None: ...   # 首次执行（由创建者调用）
    @abstractmethod
    def undo(self)  -> None: ...   # 撤销
    @abstractmethod
    def redo(self)  -> None: ...   # 重做
    def dispose(self) -> None: ... # 回收快照文件
```

### 4.2 两类命令（内存/磁盘折中）

| 类型 | 适用场景 | 存储方案 | 典型开销 |
|---|---|---|---|
| `AnnotationEditCommand` | 给少量点分配标签 | `modified_indices[int64[]]` + `old_labels[int32[]]` + 快照备份路径 | <1MB / 万点 |
| `PointCloudEditCommand` | 体素/去噪 (点数变化) | `snapshot_before.pcd` + `snapshot_after.pcd`（临时） | ~点云大小 ×2 |

### 4.3 CommandHistory 栈

```python
class CommandHistory:
    def __init__(self, max_commands=50, snapshot_dir: Path | None = None): ...
    def push(self, cmd: Command) -> None:     # 清空 redo 栈
    def undo(self) -> Command | None: ...     # undo→移到 redo
    def redo(self) -> Command | None: ...     # redo→移回 undo
    def _trim(self) -> None:                  # 超过 max 时 dispose 最早命令并删除快照
```

**自动清理**：超过 50 条时，最旧命令 `dispose()`，删除 `snapshots/*.pcd`。

---

## 5. UI 组件布局

### 5.1 主窗口组件树（代码式布局）

```
PointVaultMainWindow (QMainWindow)
│
├─ menuBar (QMenuBar)
│  ├─ 📁 文件    新建 / 打开 / 关闭 / 导入点云 / 导出 ▸(3项) / 退出
│  ├─ ✏️ 编辑    撤销(Ctrl+Z) / 重做(Ctrl+Y) / 清除选择(Esc)
│  ├─ 👁️ 视图    全部显示(F) / 顶 / 前 / 右 / 等轴 / 着色模式 ▸
│  ├─ 🛠️ 工具    体素下采样 / 统计去噪 / 法向量估计 / RANSAC 平面
│  └─ ❔ 帮助    关于
│
├─ toolBar (QToolBar)
│  ├─ 📄 新建·打开·导入   [文件]
│  ├─ ↶ ↷                  [撤销/重做]     ─ 分隔符 ─
│  ├─ 🔄 导航  ▭ 矩形  ⌇ 套索  ● 画笔  ▱ 平面 [QActionGroup 互斥, 快捷键1-5]
│  ├─ 画笔半径 [SpinBox 1-200px]
│  └─ 着色模式 [ComboBox: 高度/RGB/强度/标签/法向/纯色]
│
├─ CentralWidget
│  └─ Viewer3DWidget (QWidget)
│     - paintEvent(): 绘制选择预览（半透明矩形/橙色多边形/蓝色画笔圆）
│     - 占位文本提示
│     - mouse_pressed/moved/released, key_pressed 4 个 Signal
│     - 内嵌 Open3D VisualizerWithKeyCallback
│
├─ DockWidget (左, 可收放): "点云/标签/书签"
│  └─ QTabWidget
│     ├─ 点云列表   [导入/移除/重载] + QListWidget (勾选显隐)
│     ├─ 标签管理   标签集 ComboBox + 管理按钮 + QTreeWidget(ID/名称/点数) + [分配 / 清除]
│     └─ 视图书签   6 标准视图按钮网格 + 着色/点大小/渲染复选 + 书签列表
│
├─ DockWidget (右, 可收放): "属性/统计/历史/日志"
│  └─ QTabWidget
│     ├─ 属性面板   QTextEdit(富文本, Consolas 字体)
│     ├─ 标注统计   QTreeWidget(ID/名称/数量占比) + 总数QLabel
│     ├─ 操作历史   [撤销/重做] + QListWidget
│     └─ 日志面板   QTextEdit(分色 ERROR=红/WARNING=黄/INFO=黑) + 清空按钮
│
└─ statusBar
   ├─ [临时消息区]             进度条
   └─ [永久]   显示点数 N | FPS | 项目: Xxx
```

### 5.2 快捷键

| 键 | 功能 | 键 | 功能 |
|---|---|---|---|
| `1`-`5` | 切换 5 种选择工具 | `Esc` | 清除选择 |
| `F` | 全部显示 (Fit) | `Ctrl+Z` | 撤销 |
| `T/F/R/I` | 顶/前/右/等轴视图 | `Ctrl+Y` | 重做 |
| `鼠标左键拖拽` | 旋转 (导航模式) | `Shift+拖拽` | 平移 |
| `滚轮` | 缩放 | `Del` | 移除选中点云 |

---

## 6. 快速开始

### 6.1 环境准备

```bash
# Python 3.10+
git checkout PointVault
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
# 或者使用 pyproject.toml
pip install -e .
```

### 6.2 启动开发模式

```bash
python -m pointvault.main --verbose
# 或者安装后:
pointvault
```

### 6.3 打包为独立可执行文件

```bash
pip install pyinstaller
pyinstaller scripts/build.spec --clean --noconfirm
# 产物: dist/PointVault/PointVault.exe
```

---

## 7. 打包与分发策略

### 7.1 PyInstaller 要点 (见 [build.spec](scripts/build.spec))

| 问题 | 解决方案 |
|---|---|
| Open3D 体积大 (150MB+) | `excludes` 去掉 Qt Web/QML/Jupyter；UPX 压缩可再减 30% |
| 动态库 `.dll/.so` 缺失 | `collect_submodules('open3d')` + `binaries=[]` 让 PyInstaller 自动分析 |
| qt-material 主题 XML | `collect_data_files('qt_material')` |
| matplotlib 字体 | 运行时加：`matplotlib.rcParams['font.family'] = 'DejaVu Sans'` |
| Open3D 平台 .pyi 文件 | `pathex += [site-packages/open3d]` |

### 7.2 目标安装包大小

| 平台 | 预估大小 | 备注 |
|---|---|---|
| Windows x64 | 380MB (UPX) / 550MB (无) | 主要是 Open3D |
| macOS x64/arm64 | 420MB | 双架构时 ~700MB |
| Linux x64 | 360MB | |

### 7.3 CI 建议（GitHub Actions 矩阵）

```yaml
matrix:
  os: [windows-latest, macos-13, ubuntu-latest]
  python: ['3.11']
steps:
  - uses: actions/checkout; git checkout PointVault
  - pip install -r requirements.txt pyinstaller upx
  - pyinstaller scripts/build.spec
  - 上传 dist/ 到 Artifacts → Release
```

---

## 8. 目录结构

```
PointVault/
├── pointvault/
│   ├── __init__.py              # 版本 + 导出
│   ├── main.py                  # 应用入口
│   ├── constants.py             # 枚举/常量/调色板
│   ├── config.py                # SettingsManager(AppConfig/ProjectConfig)
│   ├── exporter.py              # 3 类导出
│   │
│   ├── db/
│   │   ├── database.py          # Database 单例(WAL)
│   │   ├── models.py            # 7 表 ORM
│   │   └── repositories.py      # 5 个 Repository + 工厂
│   │
│   ├── io/
│   │   ├── container.py         # PointCloudData (NumPy)
│   │   ├── reader.py            # 多格式读 (三级回退)
│   │   ├── writer.py            # PLY/LAS/PCD/XYZ 写
│   │   └── label_file.py        # .labels 二进制 (PVLB footer)
│   │
│   ├── rendering/
│   │   ├── renderer.py          # SceneObject / PointCloudRenderer (Open3D)
│   │   ├── selection_pipeline.py# 视锥体 + 精筛
│   │   ├── color_mapper.py      # 6 着色模式
│   │   └── camera.py            # CameraPose / 6 标准视图 / 书签
│   │
│   ├── tools/
│   │   ├── selection_tools.py   # 5 工具 + 工厂 (可扩展)
│   │   ├── preprocess.py        # 体素/去噪/法向/平面/ICP
│   │   └── history.py           # Command/CommandHistory
│   │
│   ├── gui/
│   │   ├── app_service.py       # ProjectService / AnnotationService
│   │   ├── dialogs.py           # 所有 QDialog (9+ 种)
│   │   └── main_window.py       # 主窗口 + Viewer3DWidget
│   │
│   └── resources/label_sets/
│       └── semantickitti.json   # 34 类标准
│
├── scripts/
│   └── build.spec               # PyInstaller 配置
│
├── pyproject.toml               # 构建 + entry_point
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 9. 可扩展性设计

### 9.1 选择工具插件化

```python
# pointvault/tools/selection_tools.py
class SelectionToolFactory:
    _registry: Dict[str, Type[SelectionTool]] = {}

    @classmethod
    def register(cls, name: str):
        def deco(klass): cls._registry[name] = klass; return klass
        return deco

# 第三方插件：
@SelectionToolFactory.register("growing_region")
class GrowingRegionTool(SelectionTool): ...
```

### 9.2 渲染器接口可替换

`renderer.py` 中 `PointCloudRenderer` 仅公开接口：`add/remove/recolor/fit/set_camera_pose/get_object/set_selection_mask`。**未来替换为 vispy/wgpu-py 只需重写此文件**。

### 9.3 自定义预处理

`tools/preprocess.py` 全部函数签名 `func(PointCloudData, **kwargs) -> ProcessResult(data, indices, mask)`，GUI 通过统一对话框调用，易扩展。

---

## 10. 许可证

PointVault 遵循 MIT License，欢迎学术与商业使用。
