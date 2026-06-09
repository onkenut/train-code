"""
SQLAlchemy 2.0 数据模型定义

表设计概览：
- projects:         项目元数据
- pointclouds:      点云文件元数据（路径、点数、属性范围、变换矩阵）
- labelsets:        标签集定义（如 SemanticKITTI 标签集）
- label_definitions:每个标签集中的具体标签（名称、颜色、ID）
- annotations:      标注记录（标注文件路径，对应点云与标签集的关联）
- operations_history: 操作历史，用于撤销/重做与审计
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import (
    JSON,
    BLOB,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.utcnow()


class Base(DeclarativeBase):
    """基础声明类"""
    pass


class Project(Base):
    """projects 表 - 项目元数据"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    project_dir: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    db_file: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    last_opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    modified_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    # 关系
    pointclouds: Mapped[List["PointCloud"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="select",
    )
    labelsets: Mapped[List["LabelSet"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="select",
    )
    operations: Mapped[List["OperationHistory"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name='{self.name}'>"


class PointCloud(Base):
    """pointclouds 表 - 点云文件元数据"""

    __tablename__ = "pointclouds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_format: Mapped[str] = mapped_column(String(16), nullable=False)  # ply/las/xyz/pcd
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")  # SHA256
    is_copy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 几何属性
    num_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_x: Mapped[float] = mapped_column(Float, default=0.0)
    max_x: Mapped[float] = mapped_column(Float, default=0.0)
    min_y: Mapped[float] = mapped_column(Float, default=0.0)
    max_y: Mapped[float] = mapped_column(Float, default=0.0)
    min_z: Mapped[float] = mapped_column(Float, default=0.0)
    max_z: Mapped[float] = mapped_column(Float, default=0.0)

    # 附加属性可用性
    has_colors: Mapped[bool] = mapped_column(Boolean, default=False)
    has_normals: Mapped[bool] = mapped_column(Boolean, default=False)
    has_intensity: Mapped[bool] = mapped_column(Boolean, default=False)
    has_classes: Mapped[bool] = mapped_column(Boolean, default=False)

    # 4x4 变换矩阵 (行优先展平为 16 个浮点数)，用于配准结果存储
    transform_matrix: Mapped[Optional[bytes]] = mapped_column(BLOB, nullable=True)

    # 显示相关
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    point_size_override: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    modified_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    # 关系
    project: Mapped["Project"] = relationship(back_populates="pointclouds")
    annotations: Mapped[List["Annotation"]] = relationship(
        back_populates="pointcloud",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_pointclouds_project_name", "project_id", "name", unique=True),
    )

    @property
    def bbox_center(self) -> np.ndarray:
        return np.array(
            [
                (self.min_x + self.max_x) / 2.0,
                (self.min_y + self.max_y) / 2.0,
                (self.min_z + self.max_z) / 2.0,
            ],
            dtype=np.float32,
        )

    @property
    def bbox_size(self) -> np.ndarray:
        return np.array(
            [
                self.max_x - self.min_x,
                self.max_y - self.min_y,
                self.max_z - self.min_z,
            ],
            dtype=np.float32,
        )

    @property
    def transform_matrix_np(self) -> np.ndarray:
        if self.transform_matrix is None:
            return np.eye(4, dtype=np.float32)
        return np.frombuffer(self.transform_matrix, dtype=np.float32).reshape(4, 4)

    @transform_matrix_np.setter
    def transform_matrix_np(self, mat: np.ndarray) -> None:
        mat_f32 = np.asarray(mat, dtype=np.float32).reshape(4, 4)
        self.transform_matrix = mat_f32.tobytes()

    def __repr__(self) -> str:
        return (
            f"<PointCloud id={self.id} name='{self.name}' "
            f"n={self.num_points} fmt={self.file_format}>"
        )


class LabelSet(Base):
    """labelsets 表 - 标签集（每个项目可有多个标签集）"""

    __tablename__ = "labelsets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="custom")  # custom, SemanticKITTI, S3DIS...
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    modified_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    # 关系
    project: Mapped["Project"] = relationship(back_populates="labelsets")
    labels: Mapped[List["LabelDefinition"]] = relationship(
        back_populates="labelset",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LabelDefinition.label_id",
    )
    annotations: Mapped[List["Annotation"]] = relationship(
        back_populates="labelset",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_labelsets_project_name", "project_id", "name", unique=True),
    )

    def __repr__(self) -> str:
        return f"<LabelSet id={self.id} name='{self.name}'>"


class LabelDefinition(Base):
    """label_definitions 表 - 单个标签定义"""

    __tablename__ = "label_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    labelset_id: Mapped[int] = mapped_column(
        ForeignKey("labelsets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label_id: Mapped[int] = mapped_column(Integer, nullable=False)  # 语义 ID，写入标注文件
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    color_r: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    color_g: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    color_b: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    learning_map_ignore: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # 关系
    labelset: Mapped["LabelSet"] = relationship(back_populates="labels")

    __table_args__ = (
        UniqueConstraint("labelset_id", "label_id", name="uq_labelset_labelid"),
        UniqueConstraint("labelset_id", "name", name="uq_labelset_name"),
    )

    @property
    def color(self) -> tuple[int, int, int]:
        return (self.color_r, self.color_g, self.color_b)

    @color.setter
    def color(self, c: tuple[int, int, int]) -> None:
        self.color_r, self.color_g, self.color_b = int(c[0]), int(c[1]), int(c[2])

    @property
    def color_float(self) -> tuple[float, float, float]:
        return (self.color_r / 255.0, self.color_g / 255.0, self.color_b / 255.0)

    def __repr__(self) -> str:
        return f"<Label #{self.label_id} '{self.name}' rgb={self.color}>"


class Annotation(Base):
    """annotations 表 - 标注记录
    
    由于点云规模可能达千万点级，不逐点存储到 SQLite，
    而是在磁盘上生成一个 .labels 二进制文件（int32 数组，与点云等长）。
    本表仅记录：标注文件路径、关联的标签集、标注统计摘要。
    """

    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pointcloud_id: Mapped[int] = mapped_column(
        ForeignKey("pointclouds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    labelset_id: Mapped[int] = mapped_column(
        ForeignKey("labelsets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="default")
    label_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # 统计摘要：JSON 对象 { label_id: point_count, ... }
    stats_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    total_labeled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_unlabeled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 备份快照：用于撤销，保存为 .labels.snap_<timestamp> 文件
    last_snapshot_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    modified_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    # 关系
    pointcloud: Mapped["PointCloud"] = relationship(back_populates="annotations")
    labelset: Mapped["LabelSet"] = relationship(back_populates="annotations")

    __table_args__ = (
        Index("ix_annotation_pc_ls", "pointcloud_id", "labelset_id"),
        UniqueConstraint("pointcloud_id", "labelset_id", "name", name="uq_annotation_unique"),
    )

    def update_stats_from_dict(self, counts: Dict[int, int]) -> None:
        """从 label_id->count 字典更新统计"""
        self.stats_json = {str(k): v for k, v in counts.items()}
        self.total_labeled = sum(v for k, v in counts.items() if int(k) != 0)
        self.total_unlabeled = counts.get(0, 0)

    def get_stats_dict(self) -> Dict[int, int]:
        return {int(k): int(v) for k, v in self.stats_json.items()}

    def __repr__(self) -> str:
        return (
            f"<Annotation pc={self.pointcloud_id} ls={self.labelset_id} "
            f"labeled={self.total_labeled}/{self.total_labeled + self.total_unlabeled}>"
        )


class OperationHistory(Base):
    """operations_history 表 - 操作历史（用于撤销/重做与日志）"""

    __tablename__ = "operations_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    op_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 关联的点云 ID 列表（JSON 数组）
    pointcloud_ids: Mapped[List[int]] = mapped_column(JSON, default=list, nullable=False)

    # 撤销信息：存储恢复点云/标注所需的数据（文件路径或 BLOB）
    undo_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    redo_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # 操作影响的点云快照文件路径（临时文件，用于大状态恢复）
    snapshot_before: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    snapshot_after: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    can_undo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_redo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_undone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, index=True, nullable=False
    )

    # 关系
    project: Mapped["Project"] = relationship(back_populates="operations")

    def __repr__(self) -> str:
        return (
            f"<Op id={self.id} type={self.op_type} "
            f"undo={self.can_undo} undone={self.is_undone}>"
        )
