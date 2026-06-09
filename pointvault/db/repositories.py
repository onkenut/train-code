"""
Repository 层 - 封装所有数据库读写操作

每个 Repository 对应一个 ORM 模型，提供类型安全的 CRUD 接口。
所有操作都通过 Database.instance() 获取全局会话。
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from pointvault.constants import UNLABELED_ID
from pointvault.db.database import Database
from pointvault.db.models import (
    Annotation,
    LabelDefinition,
    LabelSet,
    OperationHistory,
    PointCloud,
    Project,
)


# ============================================================
# Base Repository
# ============================================================
class BaseRepository:
    """所有 Repository 的基类，提供会话获取和通用方法"""

    def _session(self) -> Session:
        return Database.instance().session()


# ============================================================
# Project Repository
# ============================================================
class ProjectRepository(BaseRepository):
    """项目仓库"""

    def create(
        self,
        name: str,
        project_dir: Path | str,
        db_file: Path | str,
        description: str = "",
    ) -> Project:
        project = Project(
            name=name,
            description=description,
            project_dir=str(Path(project_dir).resolve()),
            db_file=str(Path(db_file).resolve()),
        )
        with self._session() as s:
            s.add(project)
            s.commit()
            s.refresh(project)
        return project

    def get_by_id(self, project_id: int) -> Optional[Project]:
        with self._session() as s:
            return s.get(Project, project_id)

    def get_by_dir(self, project_dir: Path | str) -> Optional[Project]:
        d = str(Path(project_dir).resolve())
        with self._session() as s:
            stmt = select(Project).where(Project.project_dir == d)
            return s.execute(stmt).scalar_one_or_none()

    def list_all(self) -> List[Project]:
        with self._session() as s:
            stmt = select(Project).order_by(Project.modified_at.desc())
            return list(s.execute(stmt).scalars().all())

    def update_last_opened(self, project_id: int) -> None:
        with self._session() as s:
            p = s.get(Project, project_id)
            if p is not None:
                p.last_opened_at = datetime.utcnow()
                s.commit()

    def rename(self, project_id: int, new_name: str) -> None:
        with self._session() as s:
            p = s.get(Project, project_id)
            if p is not None:
                p.name = new_name
                s.commit()

    def delete(self, project_id: int, remove_files: bool = False) -> None:
        project_dir: Optional[Path] = None
        with self._session() as s:
            p = s.get(Project, project_id)
            if p is not None:
                if remove_files:
                    project_dir = Path(p.project_dir)
                s.delete(p)
                s.commit()
        if project_dir is not None and project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)


# ============================================================
# PointCloud Repository
# ============================================================
class PointCloudRepository(BaseRepository):
    """点云元数据仓库"""

    def create(self, project_id: int, **kwargs: Any) -> PointCloud:
        pc = PointCloud(project_id=project_id, **kwargs)
        with self._session() as s:
            s.add(pc)
            s.commit()
            s.refresh(pc)
        return pc

    def get_by_id(self, pc_id: int) -> Optional[PointCloud]:
        with self._session() as s:
            return s.get(PointCloud, pc_id)

    def list_by_project(self, project_id: int) -> List[PointCloud]:
        with self._session() as s:
            stmt = (
                select(PointCloud)
                .where(PointCloud.project_id == project_id)
                .order_by(PointCloud.created_at.asc())
            )
            return list(s.execute(stmt).scalars().all())

    def get_by_name(self, project_id: int, name: str) -> Optional[PointCloud]:
        with self._session() as s:
            stmt = select(PointCloud).where(
                and_(PointCloud.project_id == project_id, PointCloud.name == name)
            )
            return s.execute(stmt).scalar_one_or_none()

    def count_by_project(self, project_id: int) -> int:
        with self._session() as s:
            stmt = select(func.count()).select_from(PointCloud).where(
                PointCloud.project_id == project_id
            )
            return int(s.execute(stmt).scalar_one())

    def update_bounds(
        self,
        pc_id: int,
        min_xyz: Sequence[float],
        max_xyz: Sequence[float],
        num_points: int,
    ) -> None:
        with self._session() as s:
            pc = s.get(PointCloud, pc_id)
            if pc is not None:
                pc.min_x, pc.min_y, pc.min_z = float(min_xyz[0]), float(min_xyz[1]), float(min_xyz[2])
                pc.max_x, pc.max_y, pc.max_z = float(max_xyz[0]), float(max_xyz[1]), float(max_xyz[2])
                pc.num_points = int(num_points)
                s.commit()

    def set_attribute_flags(
        self,
        pc_id: int,
        colors: Optional[bool] = None,
        normals: Optional[bool] = None,
        intensity: Optional[bool] = None,
        classes: Optional[bool] = None,
    ) -> None:
        with self._session() as s:
            pc = s.get(PointCloud, pc_id)
            if pc is None:
                return
            if colors is not None:
                pc.has_colors = bool(colors)
            if normals is not None:
                pc.has_normals = bool(normals)
            if intensity is not None:
                pc.has_intensity = bool(intensity)
            if classes is not None:
                pc.has_classes = bool(classes)
            s.commit()

    def set_visible(self, pc_id: int, visible: bool) -> None:
        with self._session() as s:
            pc = s.get(PointCloud, pc_id)
            if pc is not None:
                pc.visible = bool(visible)
                s.commit()

    def set_transform(self, pc_id: int, matrix: np.ndarray) -> None:
        with self._session() as s:
            pc = s.get(PointCloud, pc_id)
            if pc is not None:
                pc.transform_matrix_np = matrix
                s.commit()

    def delete(self, pc_id: int) -> None:
        with self._session() as s:
            pc = s.get(PointCloud, pc_id)
            if pc is not None:
                s.delete(pc)
                s.commit()


# ============================================================
# LabelSet & LabelDefinition Repository
# ============================================================
class LabelSetRepository(BaseRepository):
    """标签集与标签定义仓库"""

    def create_labelset(
        self,
        project_id: int,
        name: str,
        description: str = "",
        source: str = "custom",
        is_default: bool = False,
        labels: Optional[List[Tuple[int, str, Tuple[int, int, int]]]] = None,
    ) -> LabelSet:
        with self._session() as s:
            if is_default:
                # 取消原有默认
                stmt = select(LabelSet).where(
                    and_(LabelSet.project_id == project_id, LabelSet.is_default == True)
                )
                for old_default in s.execute(stmt).scalars().all():
                    old_default.is_default = False
            ls = LabelSet(
                project_id=project_id,
                name=name,
                description=description,
                source=source,
                is_default=is_default,
            )
            s.add(ls)
            s.flush()
            if labels:
                for lid, lname, color in labels:
                    s.add(
                        LabelDefinition(
                            labelset_id=ls.id,
                            label_id=int(lid),
                            name=lname,
                            color_r=int(color[0]),
                            color_g=int(color[1]),
                            color_b=int(color[2]),
                        )
                    )
            s.commit()
            s.refresh(ls)
            # 触发 selectinload
            stmt_ls = (
                select(LabelSet)
                .options(selectinload(LabelSet.labels))
                .where(LabelSet.id == ls.id)
            )
            return s.execute(stmt_ls).scalar_one()

    def get_labelset(self, ls_id: int) -> Optional[LabelSet]:
        with self._session() as s:
            stmt = (
                select(LabelSet)
                .options(selectinload(LabelSet.labels))
                .where(LabelSet.id == ls_id)
            )
            return s.execute(stmt).scalar_one_or_none()

    def list_by_project(self, project_id: int) -> List[LabelSet]:
        with self._session() as s:
            stmt = (
                select(LabelSet)
                .options(selectinload(LabelSet.labels))
                .where(LabelSet.project_id == project_id)
                .order_by(LabelSet.created_at.asc())
            )
            return list(s.execute(stmt).scalars().all())

    def get_default(self, project_id: int) -> Optional[LabelSet]:
        with self._session() as s:
            stmt = (
                select(LabelSet)
                .options(selectinload(LabelSet.labels))
                .where(
                    and_(
                        LabelSet.project_id == project_id,
                        LabelSet.is_default == True,
                    )
                )
            )
            return s.execute(stmt).scalar_one_or_none()

    def set_default(self, ls_id: int) -> None:
        with self._session() as s:
            ls = s.get(LabelSet, ls_id)
            if ls is None:
                return
            stmt = select(LabelSet).where(
                and_(LabelSet.project_id == ls.project_id, LabelSet.is_default == True)
            )
            for old_default in s.execute(stmt).scalars().all():
                old_default.is_default = False
            ls.is_default = True
            s.commit()

    def rename_labelset(self, ls_id: int, new_name: str) -> None:
        with self._session() as s:
            ls = s.get(LabelSet, ls_id)
            if ls is not None:
                ls.name = new_name
                s.commit()

    def delete_labelset(self, ls_id: int) -> None:
        with self._session() as s:
            ls = s.get(LabelSet, ls_id)
            if ls is not None:
                s.delete(ls)
                s.commit()

    # --- Labels ---
    def add_label(
        self,
        ls_id: int,
        label_id: int,
        name: str,
        color: Tuple[int, int, int],
        description: str = "",
    ) -> Optional[LabelDefinition]:
        with self._session() as s:
            # 检查重复
            exist = s.execute(
                select(LabelDefinition).where(
                    and_(
                        LabelDefinition.labelset_id == ls_id,
                        or_(
                            LabelDefinition.label_id == int(label_id),
                            LabelDefinition.name == name,
                        ),
                    )
                )
            ).scalar_one_or_none()
            if exist is not None:
                return None
            ld = LabelDefinition(
                labelset_id=ls_id,
                label_id=int(label_id),
                name=name,
                color_r=int(color[0]),
                color_g=int(color[1]),
                color_b=int(color[2]),
                description=description,
            )
            s.add(ld)
            s.commit()
            s.refresh(ld)
            return ld

    def update_label(
        self,
        label_def_id: int,
        name: Optional[str] = None,
        color: Optional[Tuple[int, int, int]] = None,
        description: Optional[str] = None,
    ) -> None:
        with self._session() as s:
            ld = s.get(LabelDefinition, label_def_id)
            if ld is None:
                return
            if name is not None:
                ld.name = name
            if color is not None:
                ld.color_r, ld.color_g, ld.color_b = int(color[0]), int(color[1]), int(color[2])
            if description is not None:
                ld.description = description
            s.commit()

    def delete_label(self, label_def_id: int) -> None:
        with self._session() as s:
            ld = s.get(LabelDefinition, label_def_id)
            if ld is not None:
                s.delete(ld)
                s.commit()

    def get_label_map(self, ls_id: int) -> Dict[int, LabelDefinition]:
        """返回 {label_id: LabelDefinition} 映射，便于渲染着色查询"""
        ls = self.get_labelset(ls_id)
        if ls is None:
            return {}
        return {ld.label_id: ld for ld in ls.labels}


# ============================================================
# Annotation Repository
# ============================================================
class AnnotationRepository(BaseRepository):
    """标注记录仓库（管理标注文件元数据，实际标签在磁盘 .labels 文件中）"""

    def create(
        self,
        pointcloud_id: int,
        labelset_id: int,
        label_file_path: Path | str,
        name: str = "default",
        total_points: int = 0,
    ) -> Annotation:
        annot = Annotation(
            pointcloud_id=pointcloud_id,
            labelset_id=labelset_id,
            name=name,
            label_file_path=str(Path(label_file_path).resolve()),
            total_unlabeled=int(total_points),
            total_labeled=0,
        )
        annot.stats_json = {str(UNLABELED_ID): int(total_points)}
        with self._session() as s:
            s.add(annot)
            s.commit()
            s.refresh(annot)
        return annot

    def get_by_id(self, ann_id: int) -> Optional[Annotation]:
        with self._session() as s:
            return s.get(Annotation, ann_id)

    def get_for_pointcloud(self, pc_id: int, ls_id: int, name: str = "default") -> Optional[Annotation]:
        with self._session() as s:
            stmt = select(Annotation).where(
                and_(
                    Annotation.pointcloud_id == pc_id,
                    Annotation.labelset_id == ls_id,
                    Annotation.name == name,
                )
            )
            return s.execute(stmt).scalar_one_or_none()

    def list_by_pointcloud(self, pc_id: int) -> List[Annotation]:
        with self._session() as s:
            stmt = (
                select(Annotation)
                .where(Annotation.pointcloud_id == pc_id)
                .order_by(Annotation.modified_at.desc())
            )
            return list(s.execute(stmt).scalars().all())

    def list_by_project(self, project_id: int) -> List[Annotation]:
        with self._session() as s:
            stmt = (
                select(Annotation)
                .join(PointCloud, Annotation.pointcloud_id == PointCloud.id)
                .where(PointCloud.project_id == project_id)
                .order_by(Annotation.modified_at.desc())
            )
            return list(s.execute(stmt).scalars().all())

    def update_stats(self, ann_id: int, label_counts: Dict[int, int]) -> None:
        with self._session() as s:
            a = s.get(Annotation, ann_id)
            if a is not None:
                a.update_stats_from_dict(label_counts)
                a.version += 1
                s.commit()

    def set_snapshot(self, ann_id: int, snapshot_path: Path | str) -> None:
        with self._session() as s:
            a = s.get(Annotation, ann_id)
            if a is not None:
                a.last_snapshot_path = str(Path(snapshot_path).resolve())
                s.commit()

    def increment_version(self, ann_id: int) -> None:
        with self._session() as s:
            a = s.get(Annotation, ann_id)
            if a is not None:
                a.version += 1
                s.commit()

    def delete(self, ann_id: int, remove_file: bool = False) -> None:
        fp: Optional[Path] = None
        with self._session() as s:
            a = s.get(Annotation, ann_id)
            if a is not None:
                if remove_file:
                    fp = Path(a.label_file_path)
                s.delete(a)
                s.commit()
        if fp is not None and fp.exists():
            try:
                fp.unlink()
            except OSError:
                pass


# ============================================================
# Operation History Repository
# ============================================================
class OperationHistoryRepository(BaseRepository):
    """操作历史仓库"""

    def add(
        self,
        project_id: int,
        op_type: str,
        description: str = "",
        pointcloud_ids: Optional[List[int]] = None,
        undo_data: Optional[Dict[str, Any]] = None,
        redo_data: Optional[Dict[str, Any]] = None,
        snapshot_before: Optional[str] = None,
        snapshot_after: Optional[str] = None,
        can_undo: bool = True,
    ) -> OperationHistory:
        op = OperationHistory(
            project_id=project_id,
            op_type=op_type,
            description=description,
            pointcloud_ids=list(pointcloud_ids or []),
            undo_data=undo_data,
            redo_data=redo_data,
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            can_undo=can_undo,
            can_redo=False,
            is_undone=False,
        )
        with self._session() as s:
            # 新操作会使之后的重做失效
            stmt = select(OperationHistory).where(
                and_(
                    OperationHistory.project_id == project_id,
                    OperationHistory.is_undone == True,
                )
            )
            for stale in s.execute(stmt).scalars().all():
                s.delete(stale)
            s.add(op)
            s.commit()
            s.refresh(op)
        return op

    def list_recent(self, project_id: int, limit: int = 100) -> List[OperationHistory]:
        with self._session() as s:
            stmt = (
                select(OperationHistory)
                .where(OperationHistory.project_id == project_id)
                .order_by(OperationHistory.timestamp.desc())
                .limit(limit)
            )
            return list(s.execute(stmt).scalars().all())

    def get_last_undoable(self, project_id: int) -> Optional[OperationHistory]:
        """获取最新的、可撤销的、未撤销的操作"""
        with self._session() as s:
            stmt = (
                select(OperationHistory)
                .where(
                    and_(
                        OperationHistory.project_id == project_id,
                        OperationHistory.can_undo == True,
                        OperationHistory.is_undone == False,
                    )
                )
                .order_by(OperationHistory.timestamp.desc())
                .limit(1)
            )
            return s.execute(stmt).scalar_one_or_none()

    def get_next_redoable(self, project_id: int) -> Optional[OperationHistory]:
        """获取最早的、可重做的、已撤销的操作"""
        with self._session() as s:
            stmt = (
                select(OperationHistory)
                .where(
                    and_(
                        OperationHistory.project_id == project_id,
                        OperationHistory.can_redo == True,
                        OperationHistory.is_undone == True,
                    )
                )
                .order_by(OperationHistory.timestamp.asc())
                .limit(1)
            )
            return s.execute(stmt).scalar_one_or_none()

    def mark_undone(self, op_id: int) -> None:
        with self._session() as s:
            op = s.get(OperationHistory, op_id)
            if op is not None:
                op.is_undone = True
                op.can_redo = True
                s.commit()

    def mark_redone(self, op_id: int) -> None:
        with self._session() as s:
            op = s.get(OperationHistory, op_id)
            if op is not None:
                op.is_undone = False
                op.can_redo = False
                s.commit()

    def delete_by_project(self, project_id: int, keep: int = 500) -> None:
        """删除旧的历史记录以控制数据库体积"""
        with self._session() as s:
            subq = (
                select(OperationHistory.id)
                .where(OperationHistory.project_id == project_id)
                .order_by(OperationHistory.timestamp.desc())
                .offset(keep)
                .subquery()
            )
            s.execute(delete(OperationHistory).where(OperationHistory.id.in_(subq)))
            s.commit()


# ============================================================
# Repository 工厂
# ============================================================
class RepositoryFactory:
    """便捷工厂，返回各 Repository 的单例"""

    _project: Optional[ProjectRepository] = None
    _pointcloud: Optional[PointCloudRepository] = None
    _labelset: Optional[LabelSetRepository] = None
    _annotation: Optional[AnnotationRepository] = None
    _history: Optional[OperationHistoryRepository] = None

    @classmethod
    def projects(cls) -> ProjectRepository:
        if cls._project is None:
            cls._project = ProjectRepository()
        return cls._project

    @classmethod
    def pointclouds(cls) -> PointCloudRepository:
        if cls._pointcloud is None:
            cls._pointcloud = PointCloudRepository()
        return cls._pointcloud

    @classmethod
    def labelsets(cls) -> LabelSetRepository:
        if cls._labelset is None:
            cls._labelset = LabelSetRepository()
        return cls._labelset

    @classmethod
    def annotations(cls) -> AnnotationRepository:
        if cls._annotation is None:
            cls._annotation = AnnotationRepository()
        return cls._annotation

    @classmethod
    def history(cls) -> OperationHistoryRepository:
        if cls._history is None:
            cls._history = OperationHistoryRepository()
        return cls._history
