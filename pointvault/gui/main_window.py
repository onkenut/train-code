"""
PointVault 主窗口 - PySide6 实现（第一部分：UI构建与项目操作）
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from PySide6.QtCore import Qt, QSize, QTimer, QPoint, QRect, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QKeySequence,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pointvault.config import SettingsManager
from pointvault.constants import (
    AnnotationMode,
    ColorMode,
    LabelColor,
    UNLABELED_ID,
)
from pointvault.db.models import LabelSet, PointCloud
from pointvault.gui.app_service import AnnotationService, ProjectService
from pointvault.gui.dialogs import (
    EstimateNormalsDialog,
    ExportDatasetDialog,
    ImportPointCloudDialog,
    LabelEditorDialog,
    NewProjectDialog,
    OpenProjectDialog,
    RansacPlaneDialog,
    StatisticalOutlierDialog,
    VoxelDownsampleDialog,
)
from pointvault.io.container import PointCloudData
from pointvault.io.label_file import compute_label_histogram, read_labels
from pointvault.io.reader import read_pointcloud
from pointvault.rendering.camera import CameraPose, StandardView
from pointvault.rendering.color_mapper import ColorMapper
from pointvault.rendering.renderer import PointCloudRenderer
from pointvault.tools.history import CommandHistory

logger = logging.getLogger(__name__)


# ============================================================
# 日志 Handler
# ============================================================
class QtLogHandler(logging.Handler):
    def __init__(self, widget: QTextEdit) -> None:
        super().__init__()
        self._widget = widget

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            color = "#d44" if record.levelno >= logging.ERROR else (
                "#d94" if record.levelno >= logging.WARNING else "#48a"
            )
            self._widget.append(f'<span style="color:{color}">[{record.levelname}]</span> {msg}')
        except Exception:
            pass


# ============================================================
# 3D 视图容器
# ============================================================
class Viewer3DWidget(QWidget):
    mouse_pressed = Signal(object)
    mouse_moved = Signal(object)
    mouse_released = Signal(object)
    key_pressed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 480)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._preview_rect: Optional[QRect] = None
        self._preview_polygon: List[QPoint] = []
        self._preview_circle: Optional[Tuple[QPoint, float]] = None
        self._brush_radius: float = 30.0
        self._placeholder_text = "PointVault 3D 视图\n\n[新建项目] → [导入点云] 开始使用"

    def set_preview_rect(self, rect: Optional[Tuple[float, float, float, float]]) -> None:
        if rect is None:
            self._preview_rect = None
        else:
            x0, y0, x1, y1 = rect
            self._preview_rect = QRect(QPoint(int(x0), int(y0)), QPoint(int(x1), int(y1)))
        self.update()

    def set_preview_polygon(self, pts: List[Tuple[float, float]]) -> None:
        self._preview_polygon = [QPoint(int(x), int(y)) for x, y in pts]
        self.update()

    def set_preview_circle(self, center: Optional[Tuple[float, float]], radius: float) -> None:
        if center is None:
            self._preview_circle = None
        else:
            self._preview_circle = (QPoint(int(center[0]), int(center[1])), float(radius))
        self._brush_radius = float(radius)
        self.update()

    def clear_placeholder(self) -> None:
        self._placeholder_text = ""
        self.update()

    def viewport_size(self) -> Tuple[int, int]:
        return self.width(), self.height()

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QPolygon

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._placeholder_text:
            p.fillRect(self.rect(), QColor(20, 22, 28))
            p.setPen(QColor(180, 200, 220))
            font = p.font()
            font.setPointSize(14)
            p.setFont(font)
            p.drawText(self.rect(), Qt.AlignCenter, self._placeholder_text)
        if self._preview_rect is not None:
            pen = QPen(QColor(0, 220, 120, 220), 2, Qt.DashLine)
            p.setPen(pen)
            p.setBrush(QColor(0, 220, 120, 40))
            p.drawRect(self._preview_rect)
        if len(self._preview_polygon) > 1:
            pen = QPen(QColor(255, 170, 0, 240), 2, Qt.SolidLine)
            p.setPen(pen)
            p.setBrush(QColor(255, 170, 0, 35))
            p.drawPolygon(QPolygon(self._preview_polygon))
        if self._preview_circle is not None:
            center, r = self._preview_circle
            pen = QPen(QColor(130, 200, 255, 240), 2, Qt.SolidLine)
            p.setPen(pen)
            p.setBrush(QColor(130, 200, 255, 30))
            p.drawEllipse(center, int(r), int(r))
        p.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.mouse_pressed.emit(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self.mouse_moved.emit(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self.mouse_released.emit(event)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        self.key_pressed.emit(event.key())
        super().keyPressEvent(event)


# ============================================================
# PointVault 主窗口
# ============================================================
class PointVaultMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PointVault - 三维点云标注与交互分析工具")
        self.resize(1440, 900)

        self._project = ProjectService()
        self._renderer = PointCloudRenderer()
        self._history = CommandHistory(max_commands=50)
        self._annotation = AnnotationService(self._project, self._renderer, self._history)
        self._settings = SettingsManager()

        self._annotation_mode = AnnotationMode.NAVIGATE
        self._selection_tool = None
        self._is_dragging = False
        self._selected_mask: Optional[np.ndarray] = None
        self._selected_indices: Optional[np.ndarray] = None
        self._pcid_to_sceneid: Dict[int, int] = {}
        self._sceneid_to_pcid: Dict[int, int] = {}
        self._color_mapper = ColorMapper()
        self._view_proj_matrix = np.eye(4, dtype=np.float64)
        self._frame_count = 0
        self._fps = 0.0

        self._render_timer = QTimer(self); self._render_timer.setInterval(33)
        self._render_timer.timeout.connect(self._tick_render)
        self._autosave_timer = QTimer(self); self._autosave_timer.setInterval(120_000)
        self._autosave_timer.timeout.connect(self._autosave)
        self._fps_timer = QTimer(self); self._fps_timer.setInterval(1000)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start()

        self._build_ui()
        self._build_menus()
        self._build_statusbar()
        self._build_toolbar()
        self._update_ui_state()

    # ============================================================
    # UI 构建
    # ============================================================
    def _build_ui(self) -> None:
        self._viewer = Viewer3DWidget()
        self._viewer.mouse_pressed.connect(self._on_viewer_mouse_pressed)
        self._viewer.mouse_moved.connect(self._on_viewer_mouse_moved)
        self._viewer.mouse_released.connect(self._on_viewer_mouse_released)
        self._viewer.key_pressed.connect(self._on_viewer_key)

        left_dock = QDockWidget("项目资源", self)
        left_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        left_tabs = QTabWidget()
        left_tabs.addTab(self._build_pc_list_panel(), "📚 点云")
        left_tabs.addTab(self._build_label_panel(), "🏷️ 标签")
        left_tabs.addTab(self._build_bookmark_panel(), "📷 视图")
        left_dock.setWidget(left_tabs)
        self.addDockWidget(Qt.LeftDockWidgetArea, left_dock)

        right_dock = QDockWidget("信息与属性", self)
        right_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        right_tabs = QTabWidget()
        right_tabs.addTab(self._build_property_panel(), "🔎 属性")
        right_tabs.addTab(self._build_stats_panel(), "📊 标注统计")
        right_tabs.addTab(self._build_history_panel(), "⏳ 历史")
        right_tabs.addTab(self._build_log_panel(), "📜 日志")
        right_dock.setWidget(right_tabs)
        self.addDockWidget(Qt.RightDockWidgetArea, right_dock)
        self.setCentralWidget(self._viewer)

    def _build_pc_list_panel(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        btn_row = QHBoxLayout()
        self._btn_import = QPushButton("📥 导入点云"); self._btn_import.clicked.connect(self._on_import)
        self._btn_remove_pc = QPushButton("❌ 移除"); self._btn_remove_pc.clicked.connect(self._on_remove_pc)
        self._btn_reload = QPushButton("🔄 重载"); self._btn_reload.clicked.connect(self._fit_view)
        btn_row.addWidget(self._btn_import); btn_row.addWidget(self._btn_remove_pc); btn_row.addWidget(self._btn_reload)
        v.addLayout(btn_row)
        self._pc_list = QListWidget()
        self._pc_list.itemChanged.connect(self._on_pc_list_item_changed)
        self._pc_list.itemSelectionChanged.connect(self._on_pc_selection_changed)
        v.addWidget(self._pc_list, 1)
        info = QLabel("提示：勾选复选框控制显隐。双击选中并设为标注目标。")
        info.setWordWrap(True); info.setStyleSheet("color:#888;font-size:11px")
        v.addWidget(info)
        return w

    def _build_label_panel(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        ls_row = QHBoxLayout()
        self._labelset_combo = QComboBox(); self._labelset_combo.currentIndexChanged.connect(self._on_labelset_changed)
        self._btn_edit_labels = QPushButton("✎ 管理…"); self._btn_edit_labels.clicked.connect(self._on_edit_labels)
        ls_row.addWidget(QLabel("标签集:"), 0); ls_row.addWidget(self._labelset_combo, 1); ls_row.addWidget(self._btn_edit_labels, 0)
        v.addLayout(ls_row)
        self._label_tree = QTreeWidget()
        self._label_tree.setColumnCount(3); self._label_tree.setHeaderLabels(["ID", "名称", "点数量"])
        self._label_tree.setColumnWidth(0, 50); self._label_tree.setColumnWidth(1, 140)
        self._label_tree.itemSelectionChanged.connect(self._on_label_tree_selection)
        v.addWidget(self._label_tree, 1)
        action_row = QHBoxLayout()
        self._btn_assign = QPushButton("🖍️ 分配给选中点"); self._btn_assign.clicked.connect(self._on_assign_label)
        self._btn_clear = QPushButton("🗑️ 清除标注"); self._btn_clear.clicked.connect(self._on_clear_labels)
        action_row.addWidget(self._btn_assign); action_row.addWidget(self._btn_clear)
        v.addLayout(action_row)
        return w

    def _build_bookmark_panel(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        sv_box = QGroupBox("标准视图"); sv_layout = QGridLayout(sv_box)
        self._btn_top = QPushButton("⬆ 顶视"); self._btn_top.clicked.connect(lambda: self._apply_std_view(StandardView.TOP))
        self._btn_front = QPushButton("⬅ 前视"); self._btn_front.clicked.connect(lambda: self._apply_std_view(StandardView.FRONT))
        self._btn_right = QPushButton("➡ 右视"); self._btn_right.clicked.connect(lambda: self._apply_std_view(StandardView.RIGHT))
        self._btn_iso = QPushButton("🧭 透视"); self._btn_iso.clicked.connect(lambda: self._apply_std_view(StandardView.ISO))
        self._btn_fit = QPushButton("🔍 全部显示"); self._btn_fit.clicked.connect(self._fit_view)
        sv_layout.addWidget(self._btn_top, 0, 0); sv_layout.addWidget(self._btn_front, 0, 1)
        sv_layout.addWidget(self._btn_right, 1, 0); sv_layout.addWidget(self._btn_iso, 1, 1)
        sv_layout.addWidget(self._btn_fit, 2, 0, 1, 2); v.addWidget(sv_box)

        render_box = QGroupBox("渲染设置"); r_form = QFormLayout(render_box)
        self._cmb_color_mode = QComboBox()
        self._cmb_color_mode.addItems(["高度 (Height)", "原始颜色 (RGB)", "强度 (Intensity)", "标签 (Label)", "法向量 (Normal)", "纯色 (Uniform)"])
        self._cmb_color_mode.setCurrentIndex(0); self._cmb_color_mode.currentIndexChanged.connect(self._on_color_mode_changed)
        self._sp_point_size = QDoubleSpinBox(); self._sp_point_size.setRange(0.5, 20.0); self._sp_point_size.setValue(3.0); self._sp_point_size.setSingleStep(0.5)
        self._sp_point_size.valueChanged.connect(self._on_point_size_changed)
        self._cb_grid = QCheckBox("显示网格地面"); self._cb_grid.setChecked(True)
        self._cb_axes = QCheckBox("显示坐标轴"); self._cb_axes.setChecked(True)
        self._cb_persp = QCheckBox("透视投影"); self._cb_persp.setChecked(True)
        r_form.addRow("着色模式:", self._cmb_color_mode); r_form.addRow("点大小:", self._sp_point_size)
        r_form.addRow("", self._cb_grid); r_form.addRow("", self._cb_axes); r_form.addRow("", self._cb_persp)
        v.addWidget(render_box)

        bm_box = QGroupBox("相机书签"); bm_layout = QVBoxLayout(bm_box)
        self._bm_list = QListWidget()
        self._bm_list.itemDoubleClicked.connect(lambda _: self._on_apply_bookmark())
        bm_btn_row = QHBoxLayout()
        self._btn_add_bm = QPushButton("➕ 保存当前视图"); self._btn_add_bm.clicked.connect(self._on_add_bookmark)
        self._btn_apply_bm = QPushButton("📌 跳转"); self._btn_apply_bm.clicked.connect(self._on_apply_bookmark)
        self._btn_del_bm = QPushButton("❌ 删除"); self._btn_del_bm.clicked.connect(self._on_del_bookmark)
        bm_btn_row.addWidget(self._btn_add_bm); bm_btn_row.addWidget(self._btn_apply_bm); bm_btn_row.addWidget(self._btn_del_bm)
        bm_layout.addWidget(self._bm_list, 1); bm_layout.addLayout(bm_btn_row); v.addWidget(bm_box, 1)
        return w

    def _build_property_panel(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        self._prop_text = QLabel("请选择一个点云以查看属性。")
        self._prop_text.setWordWrap(True); self._prop_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._prop_text.setStyleSheet("font-family: Consolas, monospace;")
        v.addWidget(self._prop_text, 1)
        return w

    def _build_stats_panel(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        self._stats_tree = QTreeWidget()
        self._stats_tree.setColumnCount(3); self._stats_tree.setHeaderLabels(["标签", "点数", "比例"])
        self._stats_tree.setColumnWidth(0, 160); v.addWidget(self._stats_tree, 1)
        summary_row = QFormLayout()
        self._lbl_total_pts = QLabel("-"); self._lbl_labeled_pts = QLabel("-"); self._lbl_pct = QLabel("-")
        summary_row.addRow("总点数:", self._lbl_total_pts)
        summary_row.addRow("已标注:", self._lbl_labeled_pts)
        summary_row.addRow("标注率:", self._lbl_pct); v.addLayout(summary_row)
        return w

    def _build_history_panel(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        btn_row = QHBoxLayout()
        self._btn_undo = QPushButton("↶ 撤销"); self._btn_undo.clicked.connect(self._on_undo)
        self._btn_redo = QPushButton("↷ 重做"); self._btn_redo.clicked.connect(self._on_redo)
        btn_row.addWidget(self._btn_undo); btn_row.addWidget(self._btn_redo); v.addLayout(btn_row)
        self._history_list = QListWidget(); v.addWidget(self._history_list, 1)
        return w

    def _build_log_panel(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)
        self._log_text = QTextEdit(); self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; background:#1e2027;color:#ddd;")
        handler = QtLogHandler(self._log_text)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(handler); logging.getLogger().setLevel(logging.INFO)
        clear_btn = QPushButton("清空日志"); clear_btn.clicked.connect(self._log_text.clear)
        v.addWidget(self._log_text, 1); v.addWidget(clear_btn)
        logger.info("PointVault 启动完成")
        return w

    # ============================================================
    # 菜单 / 工具栏 / 状态栏
    # ============================================================
    def _build_menus(self) -> None:
        mb = self.menuBar()
        f = mb.addMenu("文件(&F)")
        self._act_new = QAction("新建项目…", self); self._act_new.setShortcut(QKeySequence.New); self._act_new.triggered.connect(self._on_new_project)
        self._act_open = QAction("打开项目…", self); self._act_open.setShortcut(QKeySequence.Open); self._act_open.triggered.connect(self._on_open_project)
        self._act_close = QAction("关闭项目", self); self._act_close.triggered.connect(self._on_close_project)
        self._act_import = QAction("导入点云…", self); self._act_import.setShortcut("Ctrl+I"); self._act_import.triggered.connect(self._on_import)
        f.addAction(self._act_new); f.addAction(self._act_open); f.addAction(self._act_close); f.addSeparator(); f.addAction(self._act_import); f.addSeparator()
        exp = f.addMenu("导出")
        self._act_export_lpc = QAction("带标签点云…", self); self._act_export_lpc.triggered.connect(self._on_export_labeled)
        self._act_export_ds = QAction("语义分割数据集…", self); self._act_export_ds.triggered.connect(self._on_export_dataset)
        self._act_export_rpt = QAction("项目报告 (HTML)…", self); self._act_export_rpt.triggered.connect(self._on_export_report)
        exp.addAction(self._act_export_lpc); exp.addAction(self._act_export_ds); exp.addAction(self._act_export_rpt)
        f.addSeparator(); self._act_quit = QAction("退出", self); self._act_quit.setShortcut(QKeySequence.Quit); self._act_quit.triggered.connect(self.close); f.addAction(self._act_quit)

        e = mb.addMenu("编辑(&E)")
        self._act_undo = QAction("撤销", self); self._act_undo.setShortcut(QKeySequence.Undo); self._act_undo.triggered.connect(self._on_undo)
        self._act_redo = QAction("重做", self); self._act_redo.setShortcut(QKeySequence.Redo); self._act_redo.triggered.connect(self._on_redo)
        self._act_clear_sel = QAction("清除选择", self); self._act_clear_sel.setShortcut("Esc"); self._act_clear_sel.triggered.connect(self._clear_selection)
        e.addAction(self._act_undo); e.addAction(self._act_redo); e.addSeparator(); e.addAction(self._act_clear_sel)

        vw = mb.addMenu("视图(&V)")
        self._act_fit = QAction("全部显示", self); self._act_fit.setShortcut("F"); self._act_fit.triggered.connect(self._fit_view)
        self._act_top = QAction("顶视", self); self._act_top.triggered.connect(lambda: self._apply_std_view(StandardView.TOP))
        self._act_front = QAction("前视", self); self._act_front.triggered.connect(lambda: self._apply_std_view(StandardView.FRONT))
        self._act_right = QAction("右视", self); self._act_right.triggered.connect(lambda: self._apply_std_view(StandardView.RIGHT))
        self._act_iso = QAction("等轴侧", self); self._act_iso.triggered.connect(lambda: self._apply_std_view(StandardView.ISO))
        vw.addAction(self._act_fit); vw.addSeparator(); vw.addAction(self._act_top); vw.addAction(self._act_front); vw.addAction(self._act_right); vw.addAction(self._act_iso)

        tl = mb.addMenu("工具(&T)")
        self._act_voxel = QAction("体素下采样…", self); self._act_voxel.triggered.connect(self._on_tool_voxel)
        self._act_sor = QAction("统计离群点去除…", self); self._act_sor.triggered.connect(self._on_tool_sor)
        self._act_normal = QAction("法向量估计…", self); self._act_normal.triggered.connect(self._on_tool_normal)
        self._act_ransac = QAction("RANSAC 平面分割…", self); self._act_ransac.triggered.connect(self._on_tool_ransac)
        tl.addAction(self._act_voxel); tl.addAction(self._act_sor); tl.addAction(self._act_normal); tl.addAction(self._act_ransac)

        h = mb.addMenu("帮助(&H)")
        self._act_about = QAction("关于 PointVault", self); self._act_about.triggered.connect(self._on_about); h.addAction(self._act_about)

    def _build_toolbar(self) -> None:
        tb = self.addToolBar("主工具栏"); tb.setIconSize(QSize(20, 20)); tb.setMovable(False)
        tb.addAction(self._act_new); tb.addAction(self._act_open); tb.addAction(self._act_import); tb.addSeparator()
        tb.addAction(self._act_undo); tb.addAction(self._act_redo); tb.addSeparator()
        self._tool_group = QActionGroup(self); self._tool_group.setExclusive(True)

        def make_tool(text, mode, shortcut):
            act = QAction(text, self, checkable=True); act.setShortcut(shortcut)
            act.toggled.connect(lambda c, m=mode: c and self._set_annotation_mode(m))
            self._tool_group.addAction(act); return act

        self._act_tool_nav = make_tool("🖱️ 导航", AnnotationMode.NAVIGATE, "1")
        self._act_tool_rect = make_tool("⬛ 矩形框选", AnnotationMode.RECTANGLE, "2")
        self._act_tool_lasso = make_tool("🪢 套索", AnnotationMode.LASSO, "3")
        self._act_tool_brush = make_tool("🖌️ 画笔", AnnotationMode.PAINT_BRUSH, "4")
        self._act_tool_plane = make_tool("📐 RANSAC平面", AnnotationMode.PLANE_RANSAC, "5")
        for a in (self._act_tool_nav, self._act_tool_rect, self._act_tool_lasso, self._act_tool_brush, self._act_tool_plane):
            tb.addAction(a)
        tb.addSeparator(); tb.addWidget(QLabel(" 笔刷: "))
        self._sp_brush = QSpinBox(); self._sp_brush.setRange(2, 500); self._sp_brush.setValue(30); self._sp_brush.setSuffix(" px")
        self._sp_brush.valueChanged.connect(self._on_brush_size_changed); tb.addWidget(self._sp_brush); tb.addSeparator()
        tb.addWidget(QLabel(" 着色: "))
        self._tb_color_mode = QComboBox(); self._tb_color_mode.addItems(["高度", "RGB", "强度", "标签", "法向", "纯色"])
        self._tb_color_mode.setCurrentIndex(0); self._tb_color_mode.currentIndexChanged.connect(self._on_tb_color_changed); tb.addWidget(self._tb_color_mode)
        self._act_tool_nav.setChecked(True)

    def _build_statusbar(self) -> None:
        sb: QStatusBar = self.statusBar()
        self._sb_msg = QLabel("就绪"); self._sb_fps = QLabel("FPS: 0"); self._sb_fps.setStyleSheet("color:#8ad")
        self._sb_points = QLabel("点数: -"); self._sb_project = QLabel("(无项目)"); self._sb_project.setStyleSheet("color:#fa4; font-weight:bold")
        self._progress = QProgressBar(); self._progress.setMaximumWidth(200); self._progress.setVisible(False)
        sb.addWidget(self._sb_msg, 1); sb.addPermanentWidget(self._progress); sb.addPermanentWidget(self._sb_points)
        sb.addPermanentWidget(self._sb_fps); sb.addPermanentWidget(self._sb_project)

    # ============================================================
    # 状态辅助
    # ============================================================
    def _update_ui_state(self) -> None:
        has_project = self._project.current_project is not None
        for act in (self._act_close, self._act_import, self._act_export_lpc, self._act_export_ds, self._act_export_rpt,
                    self._act_voxel, self._act_sor, self._act_normal, self._act_ransac):
            act.setEnabled(has_project)
        self._btn_import.setEnabled(has_project)

    def _input_dialog(self, title: str, label: str, default: str) -> Tuple[str, bool]:
        return QInputDialog.getText(self, title, label, text=default)

    def _tick_render(self) -> None:
        try:
            self._renderer.update_render()
            self._frame_count += 1
        except Exception:
            logger.exception("渲染循环 tick 异常")

    def _update_fps(self) -> None:
        try:
            self._fps = float(self._frame_count)
            self._sb_fps.setText(f"FPS: {self._fps:.0f}")
            self._frame_count = 0
        except Exception:
            logger.exception("FPS 更新异常")

    def _autosave(self) -> None:
        try:
            if self._project.project_dir is None:
                return
            logger.debug("自动保存周期触发")
        except Exception:
            logger.exception("自动保存异常")

    def _add_history_entry(self, description: str) -> None:
        self._history_list.insertItem(0, description)

    def _on_about(self) -> None:
        from pointvault import __version__
        QMessageBox.information(
            self,
            "关于 PointVault",
            f"<b>PointVault</b><br/>三维点云标注与交互分析工具<br/>"
            f"<br/>版本: {__version__}<br/>"
            f"基于 Python + PySide6 + Open3D + SQLite<br/>"
            f"<br/>© PointVault Team"
        )

    # ============================================================
    # 项目操作
    # ============================================================
    def _on_new_project(self) -> None:
        dlg = NewProjectDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        name, pdir, desc = dlg.get_values()
        try:
            self._project.create_project(name, pdir)
            self._on_project_opened()
            self._sb_msg.setText(f"项目已创建：{name}")
            logger.info(f"项目创建成功: {pdir}")
        except Exception as e:
            QMessageBox.critical(self, "创建失败", str(e))
            logger.exception("创建项目失败")

    def _on_open_project(self) -> None:
        dlg = OpenProjectDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        pdir = dlg.get_selected_path()
        if pdir is None:
            return
        try:
            self._project.open_project(pdir)
            self._on_project_opened()
            self._sb_msg.setText(f"项目已打开")
            logger.info(f"项目打开: {pdir}")
        except Exception as e:
            QMessageBox.critical(self, "打开失败", str(e))
            logger.exception("打开项目失败")

    def _on_close_project(self) -> None:
        if self._project.current_project is None:
            return
        ret = QMessageBox.question(self, "确认", "关闭当前项目？未保存的标注已自动保存到数据库。")
        if ret != QMessageBox.Yes:
            return
        self._history.clear(); self._history_list.clear(); self._pc_list.clear()
        self._label_tree.clear(); self._bm_list.clear(); self._stats_tree.clear()
        self._prop_text.setText("请选择一个点云以查看属性。")
        self._project.close_project()
        self._pcid_to_sceneid.clear(); self._sceneid_to_pcid.clear()
        self._viewer._placeholder_text = "PointVault 3D 视图\n\n[新建项目] → [导入点云] 开始使用"
        self._viewer.update()
        self._render_timer.stop(); self._autosave_timer.stop()
        self._sb_project.setText("(无项目)"); self.setWindowTitle("PointVault - 三维点云标注与交互分析工具")
        self._update_ui_state()

    def _on_project_opened(self) -> None:
        proj = self._project.current_project
        assert proj is not None
        self._sb_project.setText(proj.name)
        self.setWindowTitle(f"PointVault - {proj.name}")
        ok = self._renderer.initialize(parent_widget=self._viewer, width=1024, height=768)
        if not ok:
            QMessageBox.warning(
                self,
                "渲染器初始化",
                "无法初始化 OpenGL 渲染上下文（可能为 headless/远程桌面环境）。\n"
                "程序仍可进行项目管理、数据库操作，但 3D 视图将显示占位界面。"
            )
        self._render_timer.start(); self._autosave_timer.start()
        self._reload_labelsets()
        pcs = self._project.list_pointclouds()
        for pc in pcs:
            try:
                data = read_pointcloud(pc.file_path)
                self._add_pc_to_scene(pc, data)
            except Exception as ex:
                logger.warning(f"加载点云 {pc.name} 失败: {ex}")
        self._refresh_pc_list(); self._fit_view(); self._viewer.clear_placeholder()
        self._update_ui_state()

    def _on_import(self) -> None:
        if self._project.current_project is None:
            QMessageBox.information(self, "提示", "请先新建或打开项目。"); return
        dlg = ImportPointCloudDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        files, copy, maxp = dlg.get_values()
        total = len(files); self._progress.setVisible(True); self._progress.setRange(0, total)
        for i, f in enumerate(files):
            self._progress.setValue(i); self._sb_msg.setText(f"正在导入 {f.name} …")
            QApplication.processEvents()
            try:
                pc, data = self._project.import_pointcloud(f, copy_file=copy, max_points_preview=maxp)
                self._add_pc_to_scene(pc, data)
                logger.info(f"导入点云: {pc.name} ({data.num_points:,} 点)")
            except Exception as e:
                QMessageBox.warning(self, "导入失败", f"{f.name}:\n{e}")
                logger.exception(f"导入失败 {f}")
        self._progress.setValue(total); self._progress.setVisible(False)
        self._refresh_pc_list(); self._fit_view()
        self._sb_msg.setText(f"导入完成，共 {total} 个文件"); self._update_ui_state()

    def _add_pc_to_scene(self, pc_meta: PointCloud, data: PointCloudData) -> int:
        ls = self._project.get_default_labelset()
        annot = self._project.get_annotation_for(pc_meta.id, ls.id) if ls is not None else None
        label_path = annot.label_file_path if annot is not None else None
        obj_id = self._renderer.add_pointcloud(
            name=pc_meta.name, data=data, label_file=label_path,
            point_size=self._sp_point_size.value(), visible=pc_meta.visible,
        )
        self._pcid_to_sceneid[pc_meta.id] = obj_id
        self._sceneid_to_pcid[obj_id] = pc_meta.id
        return obj_id

    # ============================================================
    # 点云列表
    # ============================================================
    def _refresh_pc_list(self) -> None:
        self._pc_list.blockSignals(True); self._pc_list.clear()
        for pc in self._project.list_pointclouds():
            item = QListWidgetItem(f"📄 {pc.name}   [{pc.num_points:,} pts, {pc.file_format.upper()}]")
            item.setData(Qt.UserRole, pc.id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if pc.visible else Qt.Unchecked)
            self._pc_list.addItem(item)
        self._pc_list.blockSignals(False)

    def _on_pc_list_item_changed(self, item: QListWidgetItem) -> None:
        from pointvault.db.repositories import RepositoryFactory
        pc_id = int(item.data(Qt.UserRole))
        visible = item.checkState() == Qt.Checked
        RepositoryFactory.pointclouds().set_visible(pc_id, visible)
        sid = self._pcid_to_sceneid.get(pc_id)
        if sid is not None: self._renderer.set_object_visible(sid, visible)

    def _on_pc_selection_changed(self) -> None:
        from pointvault.db.repositories import RepositoryFactory
        items = self._pc_list.selectedItems()
        if not items: return
        pc_id = int(items[0].data(Qt.UserRole))
        pc = RepositoryFactory.pointclouds().get_by_id(pc_id)
        if pc is None: return
        ls = self._project.get_default_labelset()
        if ls is not None:
            self._annotation.set_active_pointcloud(pc_id)
            self._annotation.set_active_labelset(ls.id)
        self._show_property(pc); self._refresh_stats(pc_id); self._update_total_points()

    def _on_remove_pc(self) -> None:
        from pointvault.db.repositories import RepositoryFactory
        items = self._pc_list.selectedItems()
        if not items:
            QMessageBox.information(self, "提示", "请先选择要移除的点云。"); return
        ret = QMessageBox.question(self, "确认", f"确定移除 {len(items)} 个点云？不会删除原始文件。")
        if ret != QMessageBox.Yes: return
        for item in items:
            pc_id = int(item.data(Qt.UserRole))
            sid = self._pcid_to_sceneid.pop(pc_id, None)
            if sid is not None:
                self._renderer.remove_object(sid); self._sceneid_to_pcid.pop(sid, None)
            RepositoryFactory.pointclouds().delete(pc_id)
        self._refresh_pc_list()

    def _show_property(self, pc: PointCloud) -> None:
        txt = f"""<b>点云属性</b><br/><hr/>
<b>名称：</b>{pc.name}<br/><b>ID：</b>{pc.id}<br/>
<b>格式：</b>{pc.file_format.upper()}<br/>
<b>文件：</b><span style="color:#888">{pc.file_path}</span><br/>
<b>文件大小：</b>{pc.file_size_bytes/1024/1024:.2f} MB<hr/>
<b>点数：</b>{pc.num_points:,}<br/>
<b>X 范围：</b>[{pc.min_x:.3f}, {pc.max_x:.3f}]<br/>
<b>Y 范围：</b>[{pc.min_y:.3f}, {pc.max_y:.3f}]<br/>
<b>Z 范围：</b>[{pc.min_z:.3f}, {pc.max_z:.3f}]<br/>
<b>包围盒尺寸：</b>{pc.max_x-pc.min_x:.3f} × {pc.max_y-pc.min_y:.3f} × {pc.max_z-pc.min_z:.3f} m<hr/>
<b>RGB 颜色：</b>{'✅ 有' if pc.has_colors else '❌ 无'}<br/>
<b>法向量：</b>{'✅ 有' if pc.has_normals else '❌ 无'}<br/>
<b>强度：</b>{'✅ 有' if pc.has_intensity else '❌ 无'}<br/>
<b>内置分类：</b>{'✅ 有' if pc.has_classes else '❌ 无'}<br/>"""
        self._prop_text.setText(txt)

    def _refresh_stats(self, pc_id: int) -> None:
        self._stats_tree.clear()
        ls = self._project.get_default_labelset()
        if ls is None: return
        annot = self._project.get_annotation_for(pc_id, ls.id)
        if annot is None: return
        counts = compute_label_histogram(annot.label_file_path)
        total = sum(counts.values()); label_map = {ld.label_id: ld for ld in ls.labels}
        labeled = 0; rows = []
        for lid in sorted(counts.keys()):
            c = counts[lid]; pct = 100.0 * c / max(1, total)
            if lid == UNLABELED_ID:
                name = "(未标注)"; color = (128, 128, 128)
            else:
                ld = label_map.get(lid)
                if ld is not None: name = ld.name; color = ld.color
                else: name = f"(未知 #{lid})"; color = LabelColor.get(lid)
            rows.append((lid, name, c, pct, color))
            if lid != UNLABELED_ID: labeled += c
        rows.sort(key=lambda x: -x[2])
        for lid, name, c, pct, color in rows:
            it = QTreeWidgetItem([str(lid), name, f"{c:,} ({pct:.2f}%)"])
            it.setBackground(1, QColor(color[0], color[1], color[2], 80))
            self._stats_tree.addTopLevelItem(it)
        self._lbl_total_pts.setText(f"{total:,}"); self._lbl_labeled_pts.setText(f"{labeled:,}")
        self._lbl_pct.setText(f"{100.0*labeled/max(1,total):.2f}%")

    def _update_total_points(self) -> None:
        total = sum(pc.num_points for pc in self._project.list_pointclouds() if pc.visible)
        self._sb_points.setText(f"显示点数: {total:,}")

    # ============================================================
    # 标签集
    # ============================================================
    def _reload_labelsets(self) -> None:
        self._labelset_combo.blockSignals(True); self._labelset_combo.clear()
        lss = self._project.list_labelsets(); current_ls = None
        for ls in lss:
            self._labelset_combo.addItem(f"{ls.name}{' (默认)' if ls.is_default else ''}", userData=ls.id)
            if ls.is_default:
                current_ls = ls; self._labelset_combo.setCurrentIndex(self._labelset_combo.count() - 1)
        self._labelset_combo.blockSignals(False)
        self._refresh_label_tree(current_ls)
        if current_ls is not None:
            self._annotation.set_active_labelset(current_ls.id)
            label_map = {ld.label_id: ld for ld in current_ls.labels}
            self._color_mapper.label_map = label_map; self._renderer.mapper.label_map = label_map

    def _refresh_label_tree(self, ls: Optional[LabelSet]) -> None:
        self._label_tree.clear()
        if ls is None: return
        sel_items = self._pc_list.selectedItems()
        pc_id = int(sel_items[0].data(Qt.UserRole)) if sel_items else None
        counts: Dict[int, int] = {}
        if pc_id is not None:
            annot = self._project.get_annotation_for(pc_id, ls.id)
            if annot is not None: counts = compute_label_histogram(annot.label_file_path)
        for ld in ls.labels:
            c = counts.get(ld.label_id, 0)
            it = QTreeWidgetItem([str(ld.label_id), ld.name, f"{c:,}"])
            it.setData(0, Qt.UserRole, ld.label_id); it.setData(0, Qt.UserRole + 1, ld.id)
            it.setBackground(1, QColor(ld.color_r, ld.color_g, ld.color_b, 90))
            self._label_tree.addTopLevelItem(it)

    def _on_labelset_changed(self) -> None:
        from pointvault.db.repositories import RepositoryFactory
        ls_id = self._labelset_combo.currentData()
        if ls_id is None: return
        ls = RepositoryFactory.labelsets().get_labelset(ls_id)
        self._refresh_label_tree(ls); self._annotation.set_active_labelset(ls_id)
        if ls is not None:
            label_map = {ld.label_id: ld for ld in ls.labels}
            self._color_mapper.label_map = label_map; self._renderer.mapper.label_map = label_map
            self._on_color_mode_changed()

    def _on_edit_labels(self) -> None:
        from pointvault.db.repositories import RepositoryFactory
        lss = self._project.list_labelsets()
        current_id = self._labelset_combo.currentData()
        dlg = LabelEditorDialog(lss, current_id, self)
        if dlg.exec() != QDialog.Accepted: return
        adds, edits, deletes = dlg.label_changes(); ls_id = dlg.current_labelset_id()
        for lid, name, color in adds: RepositoryFactory.labelsets().add_label(ls_id, lid, name, color)
        for def_id, (name, color) in edits.items(): RepositoryFactory.labelsets().update_label(def_id, name=name, color=color)
        for def_id in deletes: RepositoryFactory.labelsets().delete_label(def_id)
        self._reload_labelsets()

    def _on_label_tree_selection(self) -> None:
        items = self._label_tree.selectedItems()
        if not items: return
        label_id = int(items[0].data(0, Qt.UserRole))
        self._annotation.set_active_label(label_id)
        self._sb_msg.setText(f"当前活动标签: {items[0].text(1)} (#{label_id})")

    # ============================================================
    # 着色/渲染
    # ============================================================
    def _on_color_mode_changed(self) -> None:
        idx = self._cmb_color_mode.currentIndex()
        mode_map = {0:"height",1:"rgb",2:"intensity",3:"label",4:"normal",5:"uniform"}
        self._tb_color_mode.blockSignals(True); self._tb_color_mode.setCurrentIndex(idx if idx < self._tb_color_mode.count() else 0); self._tb_color_mode.blockSignals(False)
        self._color_mapper.mode = mode_map.get(idx, "height")
        self._renderer.mapper.mode = self._color_mapper.mode; self._renderer.recolor_all()
        self._sb_msg.setText(f"着色模式: {self._color_mapper.mode}")

    def _on_tb_color_changed(self, idx: int) -> None:
        self._cmb_color_mode.blockSignals(True); self._cmb_color_mode.setCurrentIndex(idx); self._cmb_color_mode.blockSignals(False)
        self._on_color_mode_changed()

    def _on_point_size_changed(self, v: float) -> None:
        for sid in self._pcid_to_sceneid.values(): self._renderer.set_point_size(sid, v)

    def _apply_std_view(self, view: StandardView) -> None:
        pcs = self._project.list_pointclouds()
        if not pcs: return
        center = np.mean(np.array([[(pc.min_x+pc.max_x)/2,(pc.min_y+pc.max_y)/2,(pc.min_z+pc.max_z)/2] for pc in pcs]), axis=0)
        sz = np.max(np.array([[pc.max_x-pc.min_x,pc.max_y-pc.min_y,pc.max_z-pc.min_z] for pc in pcs]), axis=0)
        pose = self._renderer.camera.standard_view(view, tuple(center.tolist()), tuple(sz.tolist()), fov=60.0, perspective=self._cb_persp.isChecked())
        self._renderer.set_camera_pose(pose); self._viewer.clear_placeholder()

    def _fit_view(self) -> None:
        self._renderer.fit_view(); self._viewer.clear_placeholder()

    # ============================================================
    # 书签
    # ============================================================
    def _on_add_bookmark(self) -> None:
        pose = self._renderer.get_camera_pose()
        name, ok = self._input_dialog("保存视图", "视图名称:", f"视图 {self._bm_list.count()+1}")
        if not ok or not name: return
        bm = self._renderer.camera.add_bookmark(name, pose)
        item = QListWidgetItem(f"📷 {bm.name}"); item.setData(Qt.UserRole, bm.id); self._bm_list.addItem(item)

    def _on_apply_bookmark(self) -> None:
        item = self._bm_list.currentItem()
        if item is None: return
        bm = self._renderer.camera.get_bookmark(int(item.data(Qt.UserRole)))
        if bm is not None: self._renderer.set_camera_pose(bm.pose)

    def _on_del_bookmark(self) -> None:
        item = self._bm_list.currentItem()
        if item is None: return
        self._renderer.camera.remove_bookmark(int(item.data(Qt.UserRole)))
        self._bm_list.takeItem(self._bm_list.row(item))

    # ============================================================
    # 预处理工具
    # ============================================================
    def _current_pc_data(self) -> Tuple[Optional[PointCloud], Optional[PointCloudData]]:
        from pointvault.db.repositories import RepositoryFactory
        if self._project.current_project is None:
            QMessageBox.information(self, "提示", "请先打开项目并导入点云。"); return None, None
        items = self._pc_list.selectedItems()
        if not items:
            QMessageBox.information(self, "提示", "请在点云列表中选择要处理的点云。"); return None, None
        pc_id = int(items[0].data(Qt.UserRole))
        pc_meta = RepositoryFactory.pointclouds().get_by_id(pc_id)
        if pc_meta is None: return None, None
        try: data = read_pointcloud(pc_meta.file_path)
        except Exception as e: QMessageBox.critical(self, "读取失败", str(e)); return None, None
        return pc_meta, data

    def _on_tool_voxel(self) -> None:
        from pointvault.tools.preprocess import voxel_downsample
        from pointvault.io.writer import write_pointcloud
        from pointvault.db.repositories import RepositoryFactory
        from pointvault.io.label_file import create_empty_label_file
        pc_meta, data = self._current_pc_data();
        if pc_meta is None: return
        sz = max(pc_meta.max_x-pc_meta.min_x, pc_meta.max_y-pc_meta.min_y, pc_meta.max_z-pc_meta.min_z)
        dlg = VoxelDownsampleDialog(default_voxel=max(0.01, sz / 500.0), parent=self)
        if dlg.exec() != QDialog.Accepted: return
        v = dlg.get_value(); self._sb_msg.setText(f"体素下采样 (voxel={v}m) …"); QApplication.processEvents()
        try: result = voxel_downsample(data, v)
        except Exception as e: QMessageBox.critical(self, "处理失败", str(e)); return
        self._apply_pc_edit(pc_meta, result.data, f"体素下采样 voxel={v}m")
        self._sb_msg.setText(f"体素下采样完成：{data.num_points:,} → {result.data.num_points:,}")

    def _on_tool_sor(self) -> None:
        from pointvault.tools.preprocess import statistical_outlier_removal
        pc_meta, data = self._current_pc_data()
        if pc_meta is None: return
        dlg = StatisticalOutlierDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        nb, sr = dlg.get_values(); self._sb_msg.setText("统计离群点去除 …"); QApplication.processEvents()
        try: result = statistical_outlier_removal(data, nb_neighbors=nb, std_ratio=sr)
        except Exception as e: QMessageBox.critical(self, "处理失败", str(e)); return
        removed = data.num_points - result.data.num_points
        self._apply_pc_edit(pc_meta, result.data, f"统计离群点去除 (removed {removed:,})")

    def _on_tool_normal(self) -> None:
        from pointvault.tools.preprocess import estimate_normals, orient_normals_towards_camera
        from pointvault.db.repositories import RepositoryFactory
        pc_meta, data = self._current_pc_data()
        if pc_meta is None: return
        dlg = EstimateNormalsDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        r, nn, orient = dlg.get_values(); self._sb_msg.setText("法向量估计中 …"); QApplication.processEvents()
        try:
            result = estimate_normals(data, radius=r, max_nn=nn)
            if orient:
                pose = self._renderer.get_camera_pose()
                result = orient_normals_towards_camera(result.data, camera_location=pose.eye)
        except Exception as e: QMessageBox.critical(self, "处理失败", str(e)); return
        data.normals = result.data.normals; pc_meta.has_normals = True
        self._reload_pc_in_renderer(pc_meta, data)
        RepositoryFactory.pointclouds().set_attribute_flags(pc_meta.id, normals=True)
        self._on_color_mode_changed(); self._sb_msg.setText("法向量估计完成")

    def _on_tool_ransac(self) -> None:
        from pointvault.tools.preprocess import ransac_detect_plane
        pc_meta, data = self._current_pc_data()
        if pc_meta is None: return
        dlg = RansacPlaneDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        dist, iters, remove = dlg.get_values(); self._sb_msg.setText("RANSAC 平面分割 …"); QApplication.processEvents()
        try: model, mask = ransac_detect_plane(data, distance_threshold=dist, num_iterations=iters)
        except Exception as e: QMessageBox.critical(self, "处理失败", str(e)); return
        inliers = int(mask.sum())
        plane_eq = f"{model[0]:.3f}x + {model[1]:.3f}y + {model[2]:.3f}z + {model[3]:.3f} = 0"
        self._sb_msg.setText(f"检测到平面，内点 {inliers:,} / {data.num_points:,} ({100.0*inliers/max(1,data.num_points):.1f}%)  |  {plane_eq}")
        self._apply_selection_mask(mask)
        if remove:
            ret = QMessageBox.question(self, "确认", f"移除平面内 {inliers:,} 个点？")
            if ret == QMessageBox.Yes:
                new_data = data.select_mask(~mask)
                self._apply_pc_edit(pc_meta, new_data, f"移除RANSAC平面点 ({inliers}点)")

    def _apply_pc_edit(self, pc_meta: PointCloud, new_data: PointCloudData, description: str) -> None:
        from pointvault.io.writer import write_pointcloud
        from pointvault.db.repositories import RepositoryFactory
        from pointvault.io.label_file import create_empty_label_file
        out_path = Path(pc_meta.file_path)
        try: write_pointcloud(new_data, out_path, format=out_path.suffix.lower())
        except Exception as e: QMessageBox.critical(self, "保存失败", str(e)); return
        lo, hi = new_data.bounds()
        RepositoryFactory.pointclouds().update_bounds(pc_meta.id, lo, hi, new_data.num_points)
        RepositoryFactory.pointclouds().set_attribute_flags(
            pc_meta.id, colors=new_data.has_colors(), normals=new_data.has_normals(),
            intensity=new_data.has_intensity(), classes=new_data.has_labels(),
        )
        annot = self._project.get_annotation_for(pc_meta.id, self._annotation.active_labelset_id or 0)
        if annot is not None and annot.total_labeled + annot.total_unlabeled != new_data.num_points:
            create_empty_label_file(annot.label_file_path, new_data.num_points)
            RepositoryFactory.annotations().update_stats(annot.id, {UNLABELED_ID: new_data.num_points})
        self._reload_pc_in_renderer(pc_meta, new_data); self._refresh_pc_list()
        self._add_history_entry(description)

    def _reload_pc_in_renderer(self, pc_meta: PointCloud, new_data: PointCloudData) -> None:
        sid = self._pcid_to_sceneid.get(pc_meta.id)
        if sid is not None: self._renderer.remove_object(sid)
        annot = self._project.get_annotation_for(pc_meta.id, self._annotation.active_labelset_id or 0)
        label_path = annot.label_file_path if annot is not None else None
        new_sid = self._renderer.add_pointcloud(
            name=pc_meta.name, data=new_data, label_file=label_path, point_size=self._sp_point_size.value(),
        )
        self._pcid_to_sceneid[pc_meta.id] = new_sid; self._sceneid_to_pcid[new_sid] = pc_meta.id

    # ============================================================
    # 撤销/重做
    # ============================================================
    def _on_undo(self) -> None:
        cmd = self._history.undo()
        if cmd is not None:
            self._sb_msg.setText(f"已撤销: {cmd.description}")
            logger.info(f"撤销: {cmd.description}")
        else:
            self._sb_msg.setText("(没有可撤销的操作)")

    def _on_redo(self) -> None:
        cmd = self._history.redo()
        if cmd is not None:
            self._sb_msg.setText(f"已重做: {cmd.description}")
            logger.info(f"重做: {cmd.description}")
        else:
            self._sb_msg.setText("(没有可重做的操作)")

    # ============================================================
    # 选择/标注
    # ============================================================
    def _set_annotation_mode(self, mode: AnnotationMode) -> None:
        self._annotation_mode = mode; self._selection_tool = None
        self._viewer.set_preview_rect(None); self._viewer.set_preview_polygon([]); self._viewer.set_preview_circle(None, self._sp_brush.value())
        names = {AnnotationMode.NAVIGATE:"导航",AnnotationMode.RECTANGLE:"矩形框选",AnnotationMode.LASSO:"套索选择",
                 AnnotationMode.PAINT_BRUSH:"画笔选择",AnnotationMode.PLANE_RANSAC:"RANSAC 平面"}
        self._sb_msg.setText(f"模式: {names.get(mode,'未知')}")

    def _on_brush_size_changed(self, v: int) -> None:
        if self._selection_tool is not None and hasattr(self._selection_tool, "radius"):
            self._selection_tool.radius = float(v)

    def _run_selection(self, tool_fn, x: float, y: float) -> Optional[Any]:
        """执行选择工具调用，传入当前活动点云的点坐标"""
        from pointvault.tools.selection_tools import SelectionResult
        items = self._pc_list.selectedItems()
        if not items: return SelectionResult()
        pc_id = int(items[0].data(Qt.UserRole)); sid = self._pcid_to_sceneid.get(pc_id)
        obj = self._renderer.get_object(sid) if sid is not None else None
        if obj is None or obj.data is None: return SelectionResult()
        pts = obj.data.points; w, h = self._viewer.viewport_size()
        try:
            return tool_fn(x=x, y=y, points=pts, width=w, height=h, view_proj=self._view_proj_matrix)
        except TypeError:
            try: return tool_fn(x, y, pts, w, h, self._view_proj_matrix)
            except Exception: return SelectionResult()

    def _apply_selection_result(self, result: Any) -> None:
        from pointvault.tools.selection_tools import SelectionResult
        if not isinstance(result, SelectionResult) or result.count == 0:
            self._clear_selection(clear_ui=False); return
        items = self._pc_list.selectedItems()
        if not items: return
        pc_id = int(items[0].data(Qt.UserRole)); sid = self._pcid_to_sceneid.get(pc_id)
        if sid is None: return
        obj = self._renderer.get_object(sid);
        if obj is None or obj.data is None: return
        mask = result.build_mask(obj.data.num_points)
        self._selected_mask = mask; self._selected_indices = result.indices
        self._renderer.set_selection_mask(sid, mask)

    def _apply_selection_mask(self, mask: np.ndarray) -> None:
        items = self._pc_list.selectedItems()
        if not items: return
        pc_id = int(items[0].data(Qt.UserRole)); sid = self._pcid_to_sceneid.get(pc_id)
        if sid is None: return
        self._selected_mask = np.asarray(mask, dtype=bool).ravel()
        self._selected_indices = np.where(self._selected_mask)[0].astype(np.int64)
        self._renderer.set_selection_mask(sid, self._selected_mask)

    def _clear_selection(self, clear_ui: bool = True) -> None:
        self._selected_mask = None; self._selected_indices = None
        for sid in self._pcid_to_sceneid.values(): self._renderer.set_selection_mask(sid, None)
        if clear_ui: self._sb_msg.setText("已清除选择")

    def _on_viewer_mouse_pressed(self, event) -> None:
        if event.button() != Qt.LeftButton or self._annotation_mode == AnnotationMode.NAVIGATE: return
        w, h = self._viewer.viewport_size(); x, y = event.position().x(), event.position().y()
        self._is_dragging = True
        from pointvault.tools.selection_tools import (RectangleSelectTool,LassoSelectTool,PaintBrushTool,RansacPlaneTool)
        try:
            if self._annotation_mode == AnnotationMode.RECTANGLE:
                self._selection_tool = RectangleSelectTool(); self._selection_tool.begin(x, y, None, w, h, self._view_proj_matrix)
            elif self._annotation_mode == AnnotationMode.LASSO:
                self._selection_tool = LassoSelectTool(); self._selection_tool.begin(x, y)
            elif self._annotation_mode == AnnotationMode.PAINT_BRUSH:
                self._selection_tool = PaintBrushTool(radius=float(self._sp_brush.value()))
                r = self._run_selection(self._selection_tool.begin, x, y)
                if isinstance(r, RectangleSelectTool) or r is None: pass
                self._viewer.set_preview_circle((x, y), self._sp_brush.value())
                # 立即执行一次 update 以应用第一次选择
                res = self._run_selection(self._selection_tool.update, x, y)
                self._apply_selection_result(res)
            elif self._annotation_mode == AnnotationMode.PLANE_RANSAC:
                self._selection_tool = RansacPlaneTool(); self._selection_tool.begin(x, y, None, w, h, self._view_proj_matrix)
        except Exception as e: logger.exception(f"选择工具 begin 失败: {e}")

    def _on_viewer_mouse_moved(self, event) -> None:
        if not self._is_dragging or self._selection_tool is None:
            if self._annotation_mode == AnnotationMode.PAINT_BRUSH:
                x, y = event.position().x(), event.position().y()
                self._viewer.set_preview_circle((x, y), self._sp_brush.value())
            return
        x, y = event.position().x(), event.position().y()
        if self._annotation_mode == AnnotationMode.RECTANGLE:
            if hasattr(self._selection_tool, "draw_preview"):
                self._viewer.set_preview_rect(self._selection_tool.draw_preview())
            res = self._run_selection(self._selection_tool.update, x, y)
            self._apply_selection_result(res)
        elif self._annotation_mode == AnnotationMode.LASSO:
            res = self._run_selection(self._selection_tool.update, x, y)
            if hasattr(self._selection_tool, "polygon_path"):
                self._viewer.set_preview_polygon(self._selection_tool.polygon_path)
            self._apply_selection_result(res)
        elif self._annotation_mode == AnnotationMode.PAINT_BRUSH:
            res = self._run_selection(self._selection_tool.update, x, y)
            self._viewer.set_preview_circle((x, y), self._sp_brush.value())
            self._apply_selection_result(res)

    def _on_viewer_mouse_released(self, event) -> None:
        if not self._is_dragging or self._selection_tool is None:
            self._is_dragging = False; return
        x, y = event.position().x(), event.position().y()
        try:
            res = self._run_selection(self._selection_tool.end, x, y)
            self._apply_selection_result(res)
            if isinstance(res, object) and hasattr(res, "count") and res.count > 0:
                self._sb_msg.setText(f"已选择 {res.count:,} 个点 — 请选择标签并点击『分配给选中点』")
        except Exception as e: logger.exception(f"选择工具 end 失败: {e}")
        self._is_dragging = False
        self._viewer.set_preview_rect(None); self._viewer.set_preview_polygon([]); self._viewer.set_preview_circle(None, self._sp_brush.value())
        self._selection_tool = None

    def _on_viewer_key(self, key: int) -> None:
        if key == Qt.Key_Escape: self._clear_selection()
        elif key == Qt.Key_Delete: self._on_remove_pc()

    def _on_assign_label(self) -> None:
        if self._selected_indices is None or self._selected_indices.size == 0:
            QMessageBox.information(self, "提示", "请先使用选择工具在点云上选中一些点。"); return
        items = self._label_tree.selectedItems()
        if not items: QMessageBox.information(self, "提示", "请先在标签面板中选择目标标签。"); return
        label_id = int(items[0].data(0, Qt.UserRole)); label_name = items[0].text(1)
        pc_items = self._pc_list.selectedItems()
        if not pc_items: return
        pc_id = int(pc_items[0].data(Qt.UserRole)); sid = self._pcid_to_sceneid.get(pc_id)
        if sid is None: return
        n = self._annotation.assign_selected(sid, self._selected_indices, label_id, description=f"标注 {label_name} (#{label_id})")
        self._add_history_entry(f"给 {n:,} 点分配标签 {label_name}")
        self._sb_msg.setText(f"已给 {n:,} 个点分配标签 {label_name} (#{label_id})")
        self._refresh_stats(pc_id); self._refresh_label_tree(self._project.get_default_labelset())
        self._clear_selection(clear_ui=False)

    def _on_clear_labels(self) -> None:
        pc_items = self._pc_list.selectedItems()
        if not pc_items: return
        ret = QMessageBox.question(self, "确认", "清除当前点云的所有标注？")
        if ret != QMessageBox.Yes: return
        pc_id = int(pc_items[0].data(Qt.UserRole)); sid = self._pcid_to_sceneid.get(pc_id)
        if sid is None: return
        self._annotation.clear_all_labels(sid)
        self._add_history_entry(f"清除点云所有标注")
        self._sb_msg.setText("标注已清除"); self._refresh_stats(pc_id)

    # ============================================================
    # 导出
    # ============================================================
    def _on_export_labeled(self) -> None:
        from pointvault.exporter import export_labeled_pointcloud
        from pointvault.db.repositories import RepositoryFactory
        pc_meta, data = self._current_pc_data()
        if pc_meta is None: return
        ls = self._project.get_default_labelset()
        if ls is None: QMessageBox.information(self, "提示", "标签集不存在。"); return
        annot = self._project.get_annotation_for(pc_meta.id, ls.id)
        if annot is None: QMessageBox.information(self, "提示", "标注数据不存在。"); return
        default_name = f"{pc_meta.name}_labeled.ply"
        path, _ = QFileDialog.getSaveFileName(self, "导出带标签点云", default_name,
                                               "PLY 点云 (*.ply);;LAS 点云 (*.las);;PCD 点云 (*.pcd);;所有文件 (*.*)")
        if not path: return
        try:
            labels = read_labels(annot.label_file_path)
            label_map = {ld.label_id: ld for ld in ls.labels}
            out = export_labeled_pointcloud(data, labels, path, label_map=label_map, use_label_color=True)
            self._sb_msg.setText(f"已导出到: {out}"); logger.info(f"导出带标签点云: {out}")
            QMessageBox.information(self, "完成", f"导出成功：\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e)); logger.exception("导出失败")

    def _on_export_dataset(self) -> None:
        from pointvault.exporter import export_semantic_dataset, DatasetExportConfig
        from pointvault.db.repositories import RepositoryFactory
        if self._project.current_project is None: return
        dlg = ExportDatasetDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        v = dlg.get_values()
        pcs = self._project.list_pointclouds(); ls = self._project.get_default_labelset()
        if ls is None: return
        items = []
        for pc in pcs:
            try:
                data = read_pointcloud(pc.file_path); annot = self._project.get_annotation_for(pc.id, ls.id)
                if annot is not None: items.append((pc, data, annot, ls))
            except Exception as ex: logger.warning(f"跳过 {pc.name}: {ex}")
        if not items: QMessageBox.warning(self, "无数据", "没有可导出的点云/标注数据。"); return
        cfg = DatasetExportConfig(output_dir=Path(v["output_dir"]), pointcloud_format=v["pc_format"],
                                   label_extension=v["label_ext"], split_ratio=v["split"], dataset_name=self._project.current_project.name)
        try:
            out_dir, stats = export_semantic_dataset(items, cfg)
            self._sb_msg.setText(f"数据集导出完成：{out_dir}"); logger.info(f"数据集导出: {out_dir}")
            QMessageBox.information(self, "完成", f"导出 {stats.get('num_samples',0)} 个样本到：\n{out_dir}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e)); logger.exception("数据集导出失败")

    def _on_export_report(self) -> None:
        from pointvault.exporter import generate_project_report_html
        from pointvault.db.repositories import RepositoryFactory
        if self._project.current_project is None: return
        default_path = f"{self._project.current_project.name}_report.html"
        path, _ = QFileDialog.getSaveFileName(self, "导出项目报告", default_path, "HTML 报告 (*.html)")
        if not path: return
        try:
            pcs = self._project.list_pointclouds(); ls = self._project.get_default_labelset()
            label_map = {ld.label_id: ld for ld in ls.labels} if ls is not None else {}
            annots = []
            for pc in pcs:
                if ls is not None:
                    a = self._project.get_annotation_for(pc.id, ls.id)
                    if a is not None: annots.append(a)
            out = generate_project_report_html(self._project.current_project.name, pcs, annots, label_map, path)
            self._sb_msg.setText(f"报告已生成：{out}"); logger.info(f"报告导出: {out}")
            QMessageBox.information(self, "完成", f"HTML 报告已生成：\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e)); logger.exception("报告导出失败")
