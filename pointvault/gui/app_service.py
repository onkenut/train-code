"""
应用服务层 - 协调 GUI 与数据层/渲染层的中间层

将数据库、渲染、I/O、命令栈等封装为统一的服务接口，
供 GUI 调用，避免 UI 与底层直接耦合。
"""

from __future__ import annotations

import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from pointvault.config import ProjectConfig, SettingsManager
from pointvault.constants import LABEL_FILE_EXT, UNLABELED_ID
from pointvault.db.database import Database, init_db
from pointvault.db.models import Annotation, LabelSet, PointCloud, Project
from pointvault.db.repositories import RepositoryFactory
from pointvault.io.container import PointCloudData
from pointvault.io.label_file import (
    compute_label_histogram,
    create_empty_label_file,
    read_labels,
    update_labels_in_range,
    write_labels,
)
from pointvault.io.reader import get_pointcloud_metadata, read_pointcloud
from pointvault.io.writer import write_pointcloud
from pointvault.rendering.renderer import PointCloudRenderer
from pointvault.tools.history import AnnotationEditCommand, CommandHistory

logger = logging.getLogger(__name__)


class ProjectService:
    """
    项目服务 - 项目生命周期管理
    """

    def __init__(self) -> None:
        self._current_project: Optional[Project] = None
        self._project_dir: Optional[Path] = None
        self._pointclouds_dir: Optional[Path] = None
        self._annotations_dir: Optional[Path] = None
        self._snapshots_dir: Optional[Path] = None
        self._settings = SettingsManager()
        self._lock = threading.RLock()
        self._project_config: Optional[ProjectConfig] = None

    # ---------- 属性 ----------
    @property
    def current_project(self) -> Optional[Project]:
        return self._current_project

    @property
    def project_dir(self) -> Optional[Path]:
        return self._project_dir

    @property
    def project_config(self) -> Optional[ProjectConfig]:
        return self._project_config

    @property
    def pointclouds_dir(self) -> Path:
        assert self._pointclouds_dir is not None
        return self._pointclouds_dir

    @property
    def annotations_dir(self) -> Path:
        assert self._annotations_dir is not None
        return self._annotations_dir

    @property
    def snapshots_dir(self) -> Path:
        assert self._snapshots_dir is not None
        return self._snapshots_dir

    # ---------- 新建 ----------
    def create_project(self, name: str, project_dir: Path | str) -> Project:
        project_dir = Path(project_dir).resolve()
        if project_dir.exists() and any(project_dir.iterdir()):
            raise FileExistsError(f"项目目录已存在且非空: {project_dir}")
        project_dir.mkdir(parents=True, exist_ok=True)

        # 子目录结构
        (project_dir / "pointclouds").mkdir(exist_ok=True)
        (project_dir / "annotations").mkdir(exist_ok=True)
        (project_dir / "snapshots").mkdir(exist_ok=True)
        (project_dir / "exports").mkdir(exist_ok=True)

        db_file = project_dir / "project.db"
        db = init_db(db_file)

        proj_repo = RepositoryFactory.projects()
        proj = proj_repo.create(name=name, project_dir=project_dir, db_file=db_file)

        # 默认标签集
        ls_repo = RepositoryFactory.labelsets()
        default_labels = [
            (0, "未标注", (128, 128, 128)),
            (1, "地面", (128, 64, 128)),
            (2, "建筑", (244, 152, 0)),
            (3, "植被", (35, 142, 35)),
            (4, "车辆", (142, 0, 0)),
            (5, "行人", (220, 20, 60)),
            (6, "道路", (175, 119, 119)),
            (7, "人行道", (153, 153, 153)),
            (8, "电线杆/杆", (156, 102, 102)),
            (9, "交通标志/灯", (220, 220, 0)),
        ]
        ls_repo.create_labelset(
            project_id=proj.id,
            name="默认标签集",
            description="PointVault 内置默认标签集",
            source="pointvault_default",
            is_default=True,
            labels=default_labels,
        )

        # 项目配置
        self._project_config = ProjectConfig(
            name=name,
            created_at=datetime.utcnow().isoformat(),
            last_modified=datetime.utcnow().isoformat(),
        )
        SettingsManager.save_project_config(project_dir, self._project_config)

        # 记录最近项目
        self._settings.load_app_config()
        self._settings.app_config.add_recent_project(str(project_dir))
        self._settings.save_app_config()

        self._bind(project_dir, proj)
        return proj

    # ---------- 打开 ----------
    def open_project(self, project_dir: Path | str) -> Project:
        project_dir = Path(project_dir).resolve()
        if not project_dir.exists():
            raise FileNotFoundError(f"项目目录不存在: {project_dir}")
        db_file = project_dir / "project.db"
        if not db_file.exists():
            raise FileNotFoundError(f"未找到项目数据库: {db_file}")

        init_db(db_file)
        proj_repo = RepositoryFactory.projects()
        proj = proj_repo.get_by_dir(project_dir)
        if proj is None:
            proj = proj_repo.create(
                name=project_dir.name,
                project_dir=project_dir,
                db_file=db_file,
                description="(自动恢复)",
            )
        proj_repo.update_last_opened(proj.id)

        # 加载项目配置
        try:
            self._project_config = SettingsManager.load_project_config(project_dir)
        except Exception:
            self._project_config = ProjectConfig(name=proj.name)
        self._project_config.last_modified = datetime.utcnow().isoformat()

        self._settings.load_app_config()
        self._settings.app_config.add_recent_project(str(project_dir))
        self._settings.save_app_config()

        self._bind(project_dir, proj)
        return proj

    def _bind(self, project_dir: Path, project: Project) -> None:
        self._current_project = project
        self._project_dir = project_dir
        self._pointclouds_dir = project_dir / "pointclouds"
        self._annotations_dir = project_dir / "annotations"
        self._snapshots_dir = project_dir / "snapshots"
        self._pointclouds_dir.mkdir(parents=True, exist_ok=True)
        self._annotations_dir.mkdir(parents=True, exist_ok=True)
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)

    # ---------- 关闭 ----------
    def close_project(self) -> None:
        if self._project_dir is not None and self._project_config is not None:
            self._project_config.last_modified = datetime.utcnow().isoformat()
            try:
                SettingsManager.save_project_config(self._project_dir, self._project_config)
            except Exception:
                pass
        self._current_project = None
        self._project_dir = None
        self._project_config = None
        Database.instance().disconnect()

    # ---------- 导入点云 ----------
    def import_pointcloud(
        self,
        src_path: Path | str,
        copy_file: bool = True,
        max_points_preview: Optional[int] = None,
    ) -> Tuple[PointCloud, PointCloudData]:
        assert self._current_project is not None
        src_path = Path(src_path).resolve()
        if not src_path.exists():
            raise FileNotFoundError(src_path)

        # 解析元数据
        meta = get_pointcloud_metadata(src_path)
        pc_name = src_path.stem

        # 避免名称冲突
        existing = RepositoryFactory.pointclouds().get_by_name(
            self._current_project.id, pc_name
        )
        suffix = 1
        base_name = pc_name
        while existing is not None:
            pc_name = f"{base_name}_{suffix}"
            existing = RepositoryFactory.pointclouds().get_by_name(
                self._current_project.id, pc_name
            )
            suffix += 1

        # 复制/引用
        dst = src_path
        if copy_file:
            dst = self.pointclouds_dir / (pc_name + src_path.suffix.lower())
            if dst.exists() and dst.resolve() != src_path:
                dst.unlink()
            if dst.resolve() != src_path:
                shutil.copy2(src_path, dst)

        # 创建数据库记录
        pc_repo = RepositoryFactory.pointclouds()
        pc = pc_repo.create(
            project_id=self._current_project.id,
            name=pc_name,
            file_path=str(dst.resolve()),
            file_format=meta.file_format,
            file_size_bytes=meta.file_size_bytes,
            file_hash=meta.file_hash,
            is_copy=copy_file,
            num_points=meta.num_points,
            min_x=meta.min_xyz[0],
            max_x=meta.max_xyz[0],
            min_y=meta.min_xyz[1],
            max_y=meta.max_xyz[1],
            min_z=meta.min_xyz[2],
            max_z=meta.max_xyz[2],
            has_colors=meta.has_colors,
            has_normals=meta.has_normals,
            has_intensity=meta.has_intensity,
            has_classes=meta.has_classes,
        )

        # 创建默认标注文件（全 0）
        label_path = (self.annotations_dir / pc_name).with_suffix(LABEL_FILE_EXT)
        label_path = create_empty_label_file(label_path, meta.num_points)

        # 获取默认标签集
        ls = RepositoryFactory.labelsets().get_default(self._current_project.id)
        if ls is None:
            labelsets = RepositoryFactory.labelsets().list_by_project(
                self._current_project.id
            )
            ls = labelsets[0] if labelsets else None
        labelset_id = ls.id if ls else 0

        annot_repo = RepositoryFactory.annotations()
        annot_repo.create(
            pointcloud_id=pc.id,
            labelset_id=labelset_id,
            label_file_path=str(label_path.resolve()),
            name="default",
            total_points=meta.num_points,
        )

        # 读取点云数据
        data = read_pointcloud(dst, max_points=max_points_preview)
        # 更新真实范围
        if max_points_preview is None:
            lo, hi = data.bounds()
            pc_repo.update_bounds(pc.id, lo, hi, data.num_points)

        return pc, data

    # ---------- 列表查询 ----------
    def list_pointclouds(self) -> List[PointCloud]:
        if self._current_project is None:
            return []
        return RepositoryFactory.pointclouds().list_by_project(self._current_project.id)

    def list_labelsets(self) -> List[LabelSet]:
        if self._current_project is None:
            return []
        return RepositoryFactory.labelsets().list_by_project(self._current_project.id)

    def get_default_labelset(self) -> Optional[LabelSet]:
        if self._current_project is None:
            return None
        return RepositoryFactory.labelsets().get_default(self._current_project.id)

    def get_annotation_for(self, pc_id: int, labelset_id: int) -> Optional[Annotation]:
        return RepositoryFactory.annotations().get_for_pointcloud(pc_id, labelset_id)

    def refresh_annotation_stats(self, annotation_id: int) -> None:
        annot = RepositoryFactory.annotations().get_by_id(annotation_id)
        if annot is None:
            return
        try:
            counts = compute_label_histogram(annot.label_file_path)
            RepositoryFactory.annotations().update_stats(annotation_id, counts)
        except Exception as e:
            logger.warning(f"刷新标注统计失败: {e}")


class AnnotationService:
    """标注服务 - 管理标签分配、标注修改"""

    def __init__(
        self,
        project_service: ProjectService,
        renderer: PointCloudRenderer,
        history: CommandHistory,
    ) -> None:
        self._project = project_service
        self._renderer = renderer
        self._history = history
        self._active_pc_id: Optional[int] = None
        self._active_labelset_id: Optional[int] = None
        self._active_label_id: int = UNLABELED_ID
        self._active_annot_id: Optional[int] = None

    # ---------- 活动对象 ----------
    @property
    def active_pointcloud_id(self) -> Optional[int]:
        return self._active_pc_id

    @property
    def active_labelset_id(self) -> Optional[int]:
        return self._active_labelset_id

    @property
    def active_label_id(self) -> int:
        return self._active_label_id

    @property
    def active_annotation_id(self) -> Optional[int]:
        return self._active_annot_id

    def set_active_pointcloud(self, pc_id: int) -> None:
        self._active_pc_id = int(pc_id)
        self._refresh_active_annotation()

    def set_active_labelset(self, ls_id: int) -> None:
        self._active_labelset_id = int(ls_id)
        self._refresh_active_annotation()

    def set_active_label(self, label_id: int) -> None:
        self._active_label_id = int(label_id)

    def _refresh_active_annotation(self) -> None:
        if self._active_pc_id is None or self._active_labelset_id is None:
            self._active_annot_id = None
            return
        annot = self._project.get_annotation_for(
            self._active_pc_id, self._active_labelset_id
        )
        self._active_annot_id = annot.id if annot is not None else None

    # ---------- 标注写入 ----------
    def assign_selected(
        self,
        obj_id: int,
        selected_indices: np.ndarray,
        new_label_id: int,
        description: str = "分配标签",
    ) -> int:
        """
        将所选点索引分配为新标签，通过 CommandHistory 支持撤销。
        返回被修改的点数。
        """
        if selected_indices.size == 0:
            return 0
        annot = RepositoryFactory.annotations().get_by_id(self._active_annot_id or 0)
        if annot is None:
            return 0
        labels_path = annot.label_file_path

        # 读取当前值，构造 old_labels
        cur = read_labels(labels_path)
        idx_clip = np.clip(
            np.asarray(selected_indices, dtype=np.int64).ravel(),
            0,
            cur.size - 1,
        )
        old_labels = cur[idx_clip].copy()

        # 过滤没变化的点
        changed_mask = old_labels != int(new_label_id)
        if not changed_mask.any():
            return 0
        idx_changed = idx_clip[changed_mask]
        old_changed = old_labels[changed_mask]

        cmd = AnnotationEditCommand(
            op_type="annotate_labels",
            description=description,
            label_file_path=labels_path,
            total_points=cur.size,
            modified_indices=idx_changed,
            old_labels=old_changed,
            new_label=int(new_label_id),
            pointcloud_id=annot.pointcloud_id,
            labelset_id=annot.labelset_id,
            post_change_callback=lambda: self._on_annotation_changed(
                obj_id, annot.id
            ),
        )
        self._history.execute(cmd)
        return int(idx_changed.size)

    def clear_all_labels(self, obj_id: int) -> None:
        """清空所有标注为 UNLABELED_ID"""
        annot = RepositoryFactory.annotations().get_by_id(self._active_annot_id or 0)
        if annot is None:
            return
        labels_path = annot.label_file_path
        cur = read_labels(labels_path)
        changed_idx = np.where(cur != UNLABELED_ID)[0]
        if changed_idx.size == 0:
            return
        old_labels = cur[changed_idx].copy()
        cmd = AnnotationEditCommand(
            op_type="clear_annotations",
            description="清除所有标注",
            label_file_path=labels_path,
            total_points=cur.size,
            modified_indices=changed_idx,
            old_labels=old_labels,
            new_label=UNLABELED_ID,
            pointcloud_id=annot.pointcloud_id,
            labelset_id=annot.labelset_id,
            post_change_callback=lambda: self._on_annotation_changed(
                obj_id, annot.id
            ),
        )
        self._history.execute(cmd)

    # ---------- 变化回调 ----------
    def _on_annotation_changed(self, obj_id: int, annot_id: int) -> None:
        # 更新数据库统计
        annot = RepositoryFactory.annotations().get_by_id(annot_id)
        if annot is not None:
            try:
                counts = compute_label_histogram(annot.label_file_path)
                RepositoryFactory.annotations().update_stats(annot_id, counts)
            except Exception:
                pass
            # 更新渲染器颜色
            try:
                new_labels = read_labels(annot.label_file_path)
                self._renderer.update_labels(obj_id, new_labels)
            except Exception:
                pass
