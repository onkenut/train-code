"""
通用对话框 - 新建/打开项目、导入点云、预处理参数、导出等
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pointvault.config import SettingsManager
from pointvault.constants import LabelColor


# ============================================================
# 新建项目
# ============================================================
class NewProjectDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建项目")
        self.setMinimumWidth(480)

        form = QFormLayout()

        self._name_edit = QLineEdit("我的点云项目")
        self._name_edit.setPlaceholderText("项目名称")

        default_dir = SettingsManager().app_config.default_projects_dir or str(
            Path.home() / "PointVaultProjects"
        )
        self._dir_edit = QLineEdit(default_dir)
        self._dir_edit.setPlaceholderText("项目文件夹路径")
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse)
        dir_w = QWidget()
        dir_w.setLayout(dir_row)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("（可选）项目描述、研究目标等")
        self._desc_edit.setMaximumHeight(80)

        form.addRow("项目名称:", self._name_edit)
        form.addRow("项目位置:", dir_w)
        form.addRow("描述:", self._desc_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btns)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择项目位置")
        if path:
            self._dir_edit.setText(str(Path(path) / self._name_edit.text()))

    def _accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入项目名称")
            return
        if not self._dir_edit.text().strip():
            QMessageBox.warning(self, "提示", "请选择项目位置")
            return
        self.accept()

    def get_values(self) -> Tuple[str, Path, str]:
        return (
            self._name_edit.text().strip(),
            Path(self._dir_edit.text().strip()),
            self._desc_edit.toPlainText().strip(),
        )


# ============================================================
# 打开项目
# ============================================================
class OpenProjectDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("打开项目")
        self.setMinimumSize(560, 400)

        self._settings = SettingsManager()

        recent = self._settings.app_config.recent_projects

        # 标签页：最近项目 / 浏览
        tabs = QTabWidget()

        # 最近
        recent_w = QWidget()
        r_layout = QVBoxLayout(recent_w)
        self._recent_list = QListWidget()
        for p in recent:
            item = QListWidgetItem(f"📁  {p}")
            item.setData(Qt.UserRole, p)
            self._recent_list.addItem(item)
        self._recent_list.itemDoubleClicked.connect(lambda _: self.accept())
        self._clear_btn = QPushButton("清空最近列表")
        self._clear_btn.clicked.connect(self._clear_recent)
        r_layout.addWidget(QLabel("最近打开的项目："), 0)
        r_layout.addWidget(self._recent_list, 1)
        r_layout.addWidget(self._clear_btn, 0)

        # 浏览
        browse_w = QWidget()
        b_layout = QVBoxLayout(browse_w)
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("选择 project.db 或项目文件夹")
        path_row = QHBoxLayout()
        path_row.addWidget(self._path_edit, 1)
        btn_browse = QPushButton("浏览…")
        btn_browse.clicked.connect(self._browse_db)
        path_row.addWidget(btn_browse)
        path_w = QWidget()
        path_w.setLayout(path_row)
        b_layout.addWidget(QLabel("手动选择项目文件/目录："))
        b_layout.addWidget(path_w)
        b_layout.addStretch(1)

        tabs.addTab(recent_w, "最近项目")
        tabs.addTab(browse_w, "手动浏览")

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs, 1)
        layout.addWidget(btns)

    def _clear_recent(self) -> None:
        self._settings.app_config.recent_projects = []
        self._settings.save_app_config()
        self._recent_list.clear()

    def _browse_db(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择项目数据库 (project.db)",
            "",
            "PointVault 数据库 (project.db);;所有文件 (*.*)",
        )
        if path:
            self._path_edit.setText(path)

    def _accept(self) -> None:
        p = self._path_edit.text().strip()
        if not p and self._recent_list.currentItem() is not None:
            p = self._recent_list.currentItem().data(Qt.UserRole) or ""
        if not p:
            QMessageBox.warning(self, "提示", "请选择项目路径")
            return
        self.accept()

    def get_selected_path(self) -> Optional[Path]:
        p = self._path_edit.text().strip()
        if not p and self._recent_list.currentItem() is not None:
            p = self._recent_list.currentItem().data(Qt.UserRole) or ""
        if not p:
            return None
        pp = Path(p)
        if pp.suffix == ".db":
            return pp.parent
        return pp


# ============================================================
# 导入点云
# ============================================================
class ImportPointCloudDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("导入点云")
        self.setMinimumWidth(520)

        self._file_paths: List[Path] = []

        form = QFormLayout()

        file_row = QHBoxLayout()
        self._file_label = QLabel("未选择文件")
        self._file_label.setStyleSheet("color:#888")
        btn_add = QPushButton("选择文件…")
        btn_add.clicked.connect(self._choose_files)
        file_row.addWidget(self._file_label, 1)
        file_row.addWidget(btn_add)
        file_w = QWidget()
        file_w.setLayout(file_row)

        self._copy_cb = QCheckBox("复制文件到项目文件夹（推荐）")
        self._copy_cb.setChecked(True)
        self._preview_cb = QCheckBox("仅预览（加载最多 50 万点，速度更快）")
        self._preview_cb.setChecked(False)

        form.addRow("点云文件:", file_w)
        form.addRow("", self._copy_cb)
        form.addRow("", self._preview_cb)

        note = QLabel("支持格式：PLY, LAS/LAZ, XYZ, PCD, TXT")
        note.setStyleSheet("color:#888;font-size:11px")
        form.addRow("", note)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btns)

    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择点云文件",
            "",
            "点云文件 (*.ply *.las *.laz *.xyz *.pcd *.xyzn *.txt);;所有文件 (*.*)",
        )
        if files:
            self._file_paths = [Path(f) for f in files]
            self._file_label.setText(f"已选择 {len(self._file_paths)} 个文件")
            self._file_label.setStyleSheet("color:#2a6;font-weight:bold")

    def _accept(self) -> None:
        if not self._file_paths:
            QMessageBox.warning(self, "提示", "请先选择点云文件")
            return
        self.accept()

    def get_values(self) -> Tuple[List[Path], bool, Optional[int]]:
        maxp: Optional[int] = 500_000 if self._preview_cb.isChecked() else None
        return self._file_paths, self._copy_cb.isChecked(), maxp


# ============================================================
# 通用参数对话框基类
# ============================================================
class _BaseParamDialog(QDialog):
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)
        self._form = QFormLayout()
        self._btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._btns.accepted.connect(self.accept)
        self._btns.rejected.connect(self.reject)
        self._main_layout = QVBoxLayout(self)
        self._main_layout.addLayout(self._form)
        self._main_layout.addWidget(self._btns)

    def add_double(self, label: str, default: float, min_: float, max_: float, step: float = 0.01, decimals: int = 3) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(min_, max_)
        sp.setValue(default)
        sp.setSingleStep(step)
        sp.setDecimals(decimals)
        self._form.addRow(label, sp)
        return sp

    def add_int(self, label: str, default: int, min_: int, max_: int, step: int = 1) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(min_, max_)
        sp.setValue(default)
        sp.setSingleStep(step)
        self._form.addRow(label, sp)
        return sp


# ============================================================
# 体素下采样
# ============================================================
class VoxelDownsampleDialog(_BaseParamDialog):
    def __init__(self, default_voxel: float = 0.1, parent: Optional[QWidget] = None) -> None:
        super().__init__("体素下采样", parent)
        self._voxel = self.add_double("体素大小 (m):", default_voxel, 1e-4, 100.0, 0.01, 4)
        note = QLabel("值越小保留的细节越多，但点数减少越少。建议根据场景尺度选择 0.01~1 米。")
        note.setWordWrap(True)
        note.setStyleSheet("color:#888;font-size:11px")
        self._form.addRow("", note)

    def get_value(self) -> float:
        return float(self._voxel.value())


# ============================================================
# 统计离群点去除
# ============================================================
class StatisticalOutlierDialog(_BaseParamDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("统计离群点去除", parent)
        self._nb = self.add_int("近邻数量:", 20, 3, 200, 1)
        self._std = self.add_double("标准差倍率:", 2.0, 0.1, 10.0, 0.1, 2)

    def get_values(self) -> Tuple[int, float]:
        return int(self._nb.value()), float(self._std.value())


# ============================================================
# 法向量估计
# ============================================================
class EstimateNormalsDialog(_BaseParamDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("法向量估计", parent)
        self._radius = self.add_double("搜索半径 (m, 0=KNN):", 0.0, 0.0, 10.0, 0.01, 4)
        self._nn = self.add_int("最大近邻数 (KNN):", 30, 3, 500, 1)
        self._orient = QCheckBox("朝向相机方向定向")
        self._orient.setChecked(True)
        self._form.addRow("", self._orient)
        note = QLabel("若搜索半径为 0，则仅使用 K=最大近邻数 方式搜索。")
        note.setWordWrap(True)
        note.setStyleSheet("color:#888;font-size:11px")
        self._form.addRow("", note)

    def get_values(self) -> Tuple[Optional[float], int, bool]:
        r = float(self._radius.value())
        return (r if r > 0 else None), int(self._nn.value()), self._orient.isChecked()


# ============================================================
# RANSAC 平面检测
# ============================================================
class RansacPlaneDialog(_BaseParamDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("RANSAC 平面分割", parent)
        self._dist = self.add_double("距离阈值 (m):", 0.05, 1e-5, 10.0, 0.001, 4)
        self._iter = self.add_int("迭代次数:", 1000, 100, 100000, 500)
        self._auto_remove = QCheckBox("检测后自动移除平面内点")
        self._auto_remove.setChecked(False)
        self._form.addRow("", self._auto_remove)

    def get_values(self) -> Tuple[float, int, bool]:
        return float(self._dist.value()), int(self._iter.value()), self._auto_remove.isChecked()


# ============================================================
# 语义分割数据集导出
# ============================================================
class ExportDatasetDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("导出语义分割数据集")
        self.setMinimumWidth(480)

        form = QFormLayout()

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit(str(Path.home() / "PointVaultDataset"))
        btn_browse = QPushButton("选择…")
        btn_browse.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(btn_browse)
        path_w = QWidget()
        path_w.setLayout(path_row)

        self._fmt = QComboBox()
        self._fmt.addItems([".ply", ".pcd", ".xyz", ".las"])

        self._label_ext = QComboBox()
        self._label_ext.addItems([".label", ".labels", ".bin"])

        self._split_cb = QCheckBox("划分训练集/验证集/测试集")
        self._split_cb.setChecked(True)

        tr_row = QHBoxLayout()
        self._tr = QDoubleSpinBox(); self._tr.setRange(0,1); self._tr.setValue(0.7); self._tr.setSingleStep(0.05)
        self._va = QDoubleSpinBox(); self._va.setRange(0,1); self._va.setValue(0.15); self._va.setSingleStep(0.05)
        self._te = QDoubleSpinBox(); self._te.setRange(0,1); self._te.setValue(0.15); self._te.setSingleStep(0.05)
        self._tr.valueChanged.connect(self._sync_splits)
        self._va.valueChanged.connect(self._sync_splits)
        self._te.valueChanged.connect(self._sync_splits)
        tr_row.addWidget(QLabel("训练:"), 0)
        tr_row.addWidget(self._tr, 1)
        tr_row.addWidget(QLabel("验证:"), 0)
        tr_row.addWidget(self._va, 1)
        tr_row.addWidget(QLabel("测试:"), 0)
        tr_row.addWidget(self._te, 1)
        self._split_hint = QLabel("")
        self._split_hint.setStyleSheet("color:#2a6;font-size:11px")
        tr_w = QWidget(); tr_w.setLayout(tr_row)
        tr_w.setEnabled(True)
        self._split_cb.toggled.connect(tr_w.setEnabled)

        form.addRow("输出目录:", path_w)
        form.addRow("点云格式:", self._fmt)
        form.addRow("标签扩展名:", self._label_ext)
        form.addRow("", self._split_cb)
        form.addRow("划分比例:", tr_w)
        form.addRow("", self._split_hint)

        self._sync_splits()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btns)

    def _sync_splits(self) -> None:
        s = self._tr.value() + self._va.value() + self._te.value()
        if abs(s - 1.0) < 1e-6:
            self._split_hint.setText("✓ 比例之和为 1.0")
            self._split_hint.setStyleSheet("color:#2a6;font-size:11px")
        else:
            self._split_hint.setText(f"⚠ 比例之和 {s:.2f}，导出时会自动归一化")
            self._split_hint.setStyleSheet("color:#d44;font-size:11px")

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self._path_edit.setText(path)

    def get_values(self) -> Dict[str, Any]:
        return {
            "output_dir": Path(self._path_edit.text().strip()),
            "pc_format": self._fmt.currentText(),
            "label_ext": self._label_ext.currentText(),
            "split": (
                (float(self._tr.value()), float(self._va.value()), float(self._te.value()))
                if self._split_cb.isChecked()
                else None
            ),
        }


# ============================================================
# 标签编辑器
# ============================================================
class LabelEditorDialog(QDialog):
    """标签管理对话框 - 增删改查标签集与标签"""

    def __init__(
        self,
        labelsets: List[Any],
        current_labelset_id: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("标签管理")
        self.setMinimumSize(720, 520)

        self._current_color: Tuple[int, int, int] = (255, 0, 0)
        self._pending_add_label: List[Tuple[int, str, Tuple[int, int, int]]] = []
        self._pending_edit_label: Dict[int, Tuple[str, Tuple[int, int, int]]] = {}
        self._pending_remove_label: List[int] = []

        # 左侧：标签集
        left_group = QGroupBox("标签集")
        left_layout = QVBoxLayout(left_group)
        self._ls_list = QComboBox()
        for ls in labelsets:
            self._ls_list.addItem(f"{ls.name}{' (默认)' if ls.is_default else ''}", userData=ls.id)
            if current_labelset_id is not None and ls.id == current_labelset_id:
                self._ls_list.setCurrentIndex(self._ls_list.count() - 1)

        ls_btn_row = QHBoxLayout()
        self._btn_new_ls = QPushButton("新建")
        self._btn_rename_ls = QPushButton("重命名")
        self._btn_default_ls = QPushButton("设为默认")
        ls_btn_row.addWidget(self._btn_new_ls)
        ls_btn_row.addWidget(self._btn_rename_ls)
        ls_btn_row.addWidget(self._btn_default_ls)

        left_layout.addWidget(QLabel("当前标签集："))
        left_layout.addWidget(self._ls_list)
        left_layout.addLayout(ls_btn_row)
        left_layout.addStretch(1)

        # 右侧：标签定义
        right_group = QGroupBox("标签定义")
        right_layout = QVBoxLayout(right_group)

        # 标签树
        self._label_tree = QTreeWidget()
        self._label_tree.setColumnCount(4)
        self._label_tree.setHeaderLabels(["ID", "名称", "颜色预览", "RGB"])
        self._label_tree.setColumnWidth(0, 60)
        self._label_tree.setColumnWidth(1, 200)
        self._label_tree.setColumnWidth(2, 80)
        self._populate_labels(labelsets, current_labelset_id)
        self._ls_list.currentIndexChanged.connect(
            lambda _: self._populate_labels(labelsets, self._ls_list.currentData())
        )

        # 编辑控件
        edit_form = QFormLayout()
        self._edit_id = QSpinBox()
        self._edit_id.setRange(0, 99999)
        self._edit_name = QLineEdit()
        self._color_preview = QLabel()
        self._color_preview.setFixedHeight(24)
        self._color_preview.setStyleSheet(
            "background: rgb(%d,%d,%d);border:1px solid #000;" % self._current_color
        )
        self._color_preview.mousePressEvent = lambda _: self._pick_color()
        btn_color = QPushButton("选择颜色…")
        btn_color.clicked.connect(self._pick_color)

        edit_form.addRow("标签 ID:", self._edit_id)
        edit_form.addRow("名称:", self._edit_name)
        color_row = QHBoxLayout()
        color_row.addWidget(self._color_preview, 1)
        color_row.addWidget(btn_color)
        color_w = QWidget(); color_w.setLayout(color_row)
        edit_form.addRow("颜色:", color_w)

        # 动作按钮
        action_row = QHBoxLayout()
        self._btn_add = QPushButton("➕ 新增标签")
        self._btn_update = QPushButton("✎ 修改选中")
        self._btn_delete = QPushButton("🗑 删除选中")
        self._btn_add.clicked.connect(self._on_add)
        self._btn_update.clicked.connect(self._on_update)
        self._btn_delete.clicked.connect(self._on_delete)
        action_row.addWidget(self._btn_add)
        action_row.addWidget(self._btn_update)
        action_row.addWidget(self._btn_delete)

        self._label_tree.itemSelectionChanged.connect(self._on_select)

        right_layout.addWidget(self._label_tree, 1)
        right_layout.addLayout(edit_form, 0)
        right_layout.addLayout(action_row, 0)

        # 左右分栏
        splitter = QHBoxLayout()
        splitter.addWidget(left_group, 1)
        splitter.addWidget(right_group, 2)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(splitter, 1)
        layout.addWidget(btns)

    # ---------- 内部 ----------
    def _populate_labels(self, labelsets: List[Any], select_ls_id: Optional[int]) -> None:
        self._label_tree.clear()
        target = None
        for ls in labelsets:
            if ls.id == (select_ls_id or self._ls_list.currentData()):
                target = ls
                break
        if target is None and labelsets:
            target = labelsets[0]
        if target is None:
            return
        for ld in target.labels:
            item = QTreeWidgetItem([
                str(ld.label_id),
                ld.name,
                "",
                f"{ld.color_r}, {ld.color_g}, {ld.color_b}",
            ])
            item.setData(0, Qt.UserRole, ld.id)
            item.setData(0, Qt.UserRole + 1, ld.label_id)
            item.setData(0, Qt.UserRole + 2, ld.name)
            item.setData(0, Qt.UserRole + 3, (ld.color_r, ld.color_g, ld.color_b))
            # 颜色预览
            color_icon = QIcon()
            pix = QSize(32, 16)
            item.setBackground(2, QColor(ld.color_r, ld.color_g, ld.color_b))
            self._label_tree.addTopLevelItem(item)

    def _on_select(self) -> None:
        items = self._label_tree.selectedItems()
        if not items:
            return
        item = items[0]
        self._edit_id.setValue(int(item.data(0, Qt.UserRole + 1)))
        self._edit_name.setText(str(item.data(0, Qt.UserRole + 2)))
        color = item.data(0, Qt.UserRole + 3) or (255, 0, 0)
        self._current_color = tuple(int(c) for c in color)
        self._update_color_preview()

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(
            QColor(*self._current_color),
            self,
            "选择标签颜色",
        )
        if c.isValid():
            self._current_color = (c.red(), c.green(), c.blue())
            self._update_color_preview()

    def _update_color_preview(self) -> None:
        self._color_preview.setStyleSheet(
            "background: rgb(%d,%d,%d);border:1px solid #000;" % self._current_color
        )

    def _on_add(self) -> None:
        name = self._edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入标签名称")
            return
        lid = int(self._edit_id.value())
        self._pending_add_label.append((lid, name, self._current_color))
        item = QTreeWidgetItem([
            str(lid), name, "",
            f"{self._current_color[0]}, {self._current_color[1]}, {self._current_color[2]}",
        ])
        item.setData(0, Qt.UserRole + 1, lid)
        item.setData(0, Qt.UserRole + 2, name)
        item.setData(0, Qt.UserRole + 3, self._current_color)
        item.setBackground(2, QColor(*self._current_color))
        self._label_tree.addTopLevelItem(item)

    def _on_update(self) -> None:
        items = self._label_tree.selectedItems()
        if not items:
            QMessageBox.information(self, "提示", "请先选中一个标签")
            return
        item = items[0]
        def_id = item.data(0, Qt.UserRole)
        lid = int(self._edit_id.value())
        name = self._edit_name.text().strip() or item.text(1)
        color = self._current_color
        if def_id is not None:
            self._pending_edit_label[int(def_id)] = (name, color)
        item.setText(0, str(lid))
        item.setText(1, name)
        item.setText(3, f"{color[0]}, {color[1]}, {color[2]}")
        item.setData(0, Qt.UserRole + 1, lid)
        item.setData(0, Qt.UserRole + 2, name)
        item.setData(0, Qt.UserRole + 3, color)
        item.setBackground(2, QColor(*color))

    def _on_delete(self) -> None:
        items = self._label_tree.selectedItems()
        if not items:
            return
        item = items[0]
        def_id = item.data(0, Qt.UserRole)
        if def_id is not None:
            self._pending_remove_label.append(int(def_id))
        self._label_tree.takeTopLevelItem(self._label_tree.indexOfTopLevelItem(item))

    # ---------- 结果获取 ----------
    def current_labelset_id(self) -> Optional[int]:
        return self._ls_list.currentData()

    def label_changes(
        self,
    ) -> Tuple[List[Tuple[int, str, Tuple[int, int, int]]], Dict[int, Tuple[str, Tuple[int, int, int]]], List[int]]:
        return self._pending_add_label, self._pending_edit_label, self._pending_remove_label
