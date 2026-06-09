"""
点云数据容器 - 在 NumPy 数组之上的轻量封装

为避免强耦合 Open3D，内部以 NumPy 数组存储点、颜色、法向、强度、标签。
与 Open3D 的转换由专门的适配器完成。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np


@dataclass
class PointCloudData:
    """轻量级点云数据容器

    所有可选属性均以 numpy 数组存储，shape:
        points:    (N, 3) float32
        colors:    (N, 3) float32  [0, 1]
        normals:   (N, 3) float32
        intensity: (N,) float32
        labels:    (N,) int32     (可选，用于传递或读取原始标签)
    """

    points: np.ndarray = field(
        default_factory=lambda: np.empty((0, 3), dtype=np.float32)
    )
    colors: Optional[np.ndarray] = None
    normals: Optional[np.ndarray] = None
    intensity: Optional[np.ndarray] = None
    labels: Optional[np.ndarray] = None

    @property
    def num_points(self) -> int:
        return int(self.points.shape[0])

    def has_colors(self) -> bool:
        return self.colors is not None and self.colors.shape[0] == self.num_points

    def has_normals(self) -> bool:
        return self.normals is not None and self.normals.shape[0] == self.num_points

    def has_intensity(self) -> bool:
        return self.intensity is not None and self.intensity.shape[0] == self.num_points

    def has_labels(self) -> bool:
        return self.labels is not None and self.labels.shape[0] == self.num_points

    def bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        if self.num_points == 0:
            return np.zeros(3, dtype=np.float32), np.zeros(3, dtype=np.float32)
        return (
            self.points.min(axis=0).astype(np.float32),
            self.points.max(axis=0).astype(np.float32),
        )

    def transform(self, matrix: np.ndarray) -> None:
        """4x4 变换矩阵变换点与法向"""
        mat = np.asarray(matrix, dtype=np.float32).reshape(4, 4)
        if self.num_points == 0:
            return
        # 点
        pts_h = np.hstack(
            [self.points, np.ones((self.num_points, 1), dtype=np.float32)]
        )
        self.points = (pts_h @ mat.T)[:, :3].astype(np.float32)
        # 法向：使用 3x3 R（忽略平移）
        if self.has_normals():
            R = mat[:3, :3]
            # 若 R 含缩放，需正交化；这里做 R.T^{-1}
            try:
                R_inv_T = np.linalg.inv(R).T.astype(np.float32)
            except np.linalg.LinAlgError:
                R_inv_T = R
            self.normals = (self.normals @ R_inv_T.T).astype(np.float32)

    def select_mask(self, mask: np.ndarray) -> "PointCloudData":
        """根据布尔掩码返回子点云"""
        mask = np.asarray(mask, dtype=bool)
        out = PointCloudData(points=self.points[mask].copy())
        if self.has_colors():
            out.colors = self.colors[mask].copy()
        if self.has_normals():
            out.normals = self.normals[mask].copy()
        if self.has_intensity():
            out.intensity = self.intensity[mask].copy()
        if self.has_labels():
            out.labels = self.labels[mask].copy()
        return out

    def select_indices(self, idx: np.ndarray) -> "PointCloudData":
        """根据索引数组返回子点云"""
        idx = np.asarray(idx, dtype=np.int64)
        out = PointCloudData(points=self.points[idx].copy())
        if self.has_colors():
            out.colors = self.colors[idx].copy()
        if self.has_normals():
            out.normals = self.normals[idx].copy()
        if self.has_intensity():
            out.intensity = self.intensity[idx].copy()
        if self.has_labels():
            out.labels = self.labels[idx].copy()
        return out

    def merge(self, other: "PointCloudData") -> None:
        """合并另一个点云（原地修改）"""
        self.points = np.vstack([self.points, other.points]).astype(np.float32)
        if self.has_colors() or other.has_colors():
            a = self.colors if self.has_colors() else np.zeros_like(self.points)
            b = other.colors if other.has_colors() else np.zeros_like(other.points)
            self.colors = np.vstack([a, b]).astype(np.float32)
        if self.has_normals() or other.has_normals():
            a = self.normals if self.has_normals() else np.zeros_like(self.points)
            b = other.normals if other.has_normals() else np.zeros_like(other.points)
            self.normals = np.vstack([a, b]).astype(np.float32)
        if self.has_intensity() or other.has_intensity():
            a = self.intensity if self.has_intensity() else np.zeros(self.num_points - other.num_points, dtype=np.float32)
            b = other.intensity if other.has_intensity() else np.zeros(other.num_points, dtype=np.float32)
            self.intensity = np.concatenate([a, b]).astype(np.float32)
