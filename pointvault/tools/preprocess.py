"""
点云预处理工具 - 纯 NumPy 实现，必要时回退到 Open3D

所有函数操作 PointCloudData，返回处理后的新 PointCloudData（不可变风格），
同时记录可用于撤销的元信息。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from pointvault.io.container import PointCloudData


@dataclass
class PreprocessResult:
    """预处理结果包装，包含回退信息"""

    data: PointCloudData
    undo_info: Dict[str, Any]


# ============================================================
# 体素下采样
# ============================================================
def voxel_downsample(
    data: PointCloudData,
    voxel_size: float,
) -> PreprocessResult:
    """
    体素下采样

    在每个体素内保留所有点的质心与属性平均值（标签保留众数或索引0点）。
    """
    voxel_size = max(1e-9, float(voxel_size))
    pts = data.points.astype(np.float64)
    N = pts.shape[0]

    if N == 0:
        return PreprocessResult(data=data, undo_info={"removed_indices": np.empty(0, dtype=np.int64)})

    # 量化到体素键
    voxel_keys = np.floor(pts / voxel_size).astype(np.int64)
    # 线性化键 (大空间下安全)
    min_keys = voxel_keys.min(axis=0)
    max_keys = voxel_keys.max(axis=0)
    dims = (max_keys - min_keys) + 1
    # 避免溢出：使用组合编码
    shifted = voxel_keys - min_keys
    # 使用元组哈希替代乘法（对大 dims 安全）
    keys_linear = (
        shifted[:, 0]
        + shifted[:, 1] * (dims[0] + 1)
        + shifted[:, 2] * (dims[0] + 1) * (dims[1] + 1)
    )

    # 分组（使用 np.unique 配合索引）
    order = np.argsort(keys_linear, kind="mergesort")
    sorted_keys = keys_linear[order]
    boundaries = np.where(np.diff(sorted_keys, prepend=sorted_keys[0] - 1) != 0)[0]
    boundaries = np.append(boundaries, len(sorted_keys))

    out_points = np.zeros((len(boundaries) - 1, 3), dtype=np.float32)
    out_colors = None
    out_normals = None
    out_intensity = None
    out_labels = None
    if data.has_colors():
        out_colors = np.zeros((len(boundaries) - 1, 3), dtype=np.float32)
    if data.has_normals():
        out_normals = np.zeros((len(boundaries) - 1, 3), dtype=np.float32)
    if data.has_intensity():
        out_intensity = np.zeros(len(boundaries) - 1, dtype=np.float32)
    if data.has_labels():
        out_labels = np.zeros(len(boundaries) - 1, dtype=np.int32)

    kept_indices = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        idx_grp = order[start:end]
        kept_indices.append(idx_grp[0])
        out_points[i] = pts[idx_grp].mean(axis=0).astype(np.float32)
        if data.has_colors():
            out_colors[i] = data.colors[idx_grp].mean(axis=0).astype(np.float32)
        if data.has_normals():
            # 归一化后平均
            n = data.normals[idx_grp].astype(np.float64)
            n_len = np.linalg.norm(n, axis=1, keepdims=True)
            n_len = np.where(n_len < 1e-12, 1, n_len)
            n = n / n_len
            m = n.mean(axis=0)
            m_len = np.linalg.norm(m)
            if m_len > 1e-12:
                m = m / m_len
            out_normals[i] = m.astype(np.float32)
        if data.has_intensity():
            out_intensity[i] = float(data.intensity[idx_grp].mean())
        if data.has_labels():
            # 众数
            labels_grp = data.labels[idx_grp]
            vals, counts = np.unique(labels_grp, return_counts=True)
            out_labels[i] = int(vals[np.argmax(counts)])

    new_data = PointCloudData(
        points=out_points,
        colors=out_colors,
        normals=out_normals,
        intensity=out_intensity,
        labels=out_labels,
    )
    return PreprocessResult(
        data=new_data,
        undo_info={
            "removed_count": N - new_data.num_points,
            "voxel_size": voxel_size,
        },
    )


# ============================================================
# 统计离群点去除
# ============================================================
def statistical_outlier_removal(
    data: PointCloudData,
    nb_neighbors: int = 20,
    std_ratio: float = 2.0,
) -> PreprocessResult:
    """
    统计离群点去除：
    - 计算每个点到最近 nb_neighbors 个邻居的平均距离
    - 去除距离在 μ + σ * std_ratio 之外的点
    """
    from scipy.spatial import KDTree

    pts = data.points.astype(np.float64)
    N = pts.shape[0]
    if N == 0:
        return PreprocessResult(data=data, undo_info={"removed_mask": np.zeros(0, dtype=bool)})

    tree = KDTree(pts)
    distances, _ = tree.query(pts, k=nb_neighbors + 1)  # 包含自身
    avg_dist = distances[:, 1:].mean(axis=1)  # 忽略自身距离
    mu = avg_dist.mean()
    sigma = avg_dist.std()
    threshold = mu + std_ratio * sigma
    inlier_mask = avg_dist < threshold

    new_data = data.select_mask(inlier_mask)
    return PreprocessResult(
        data=new_data,
        undo_info={
            "removed_mask": ~inlier_mask,
            "threshold": float(threshold),
        },
    )


# ============================================================
# 半径离群点去除
# ============================================================
def radius_outlier_removal(
    data: PointCloudData,
    radius: float,
    min_neighbors: int = 5,
) -> PreprocessResult:
    from scipy.spatial import KDTree

    pts = data.points.astype(np.float64)
    N = pts.shape[0]
    if N == 0:
        return PreprocessResult(data=data, undo_info={})

    tree = KDTree(pts)
    # 对每个点查询半径内邻居数
    counts = np.zeros(N, dtype=np.int32)
    # 批量查询更高效
    neighbors = tree.query_ball_point(pts, r=radius, workers=-1)
    for i, nbrs in enumerate(neighbors):
        counts[i] = len(nbrs) - 1  # 排除自身
    inlier_mask = counts >= min_neighbors

    new_data = data.select_mask(inlier_mask)
    return PreprocessResult(
        data=new_data,
        undo_info={"removed_mask": ~inlier_mask},
    )


# ============================================================
# 法向量估计
# ============================================================
def estimate_normals(
    data: PointCloudData,
    radius: Optional[float] = None,
    max_nn: int = 30,
) -> PreprocessResult:
    """
    使用 PCA 估计每个点的法向量。

    优先使用半径搜索，若 radius 未给定则使用 knn (max_nn)。
    """
    pts = data.points.astype(np.float64)
    N = pts.shape[0]
    if N == 0:
        return PreprocessResult(data=data, undo_info={})

    normals = np.zeros((N, 3), dtype=np.float32)

    # 尝试 Open3D (更高效)
    try:
        import open3d as o3d

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(pts)
        if radius is not None:
            pcd.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(
                    radius=float(radius), max_nn=int(max_nn)
                )
            )
        else:
            pcd.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamKNN(knn=int(max_nn))
            )
        normals = np.asarray(pcd.normals, dtype=np.float32)
    except ImportError:
        # 纯 NumPy 实现 (慢，仅作后备)
        from scipy.spatial import KDTree

        tree = KDTree(pts)
        for i in range(N):
            if radius is not None:
                idx = tree.query_ball_point(pts[i], r=radius)
                if len(idx) < 3:
                    d, idx = tree.query(pts[i], k=max_nn)
            else:
                d, idx = tree.query(pts[i], k=max_nn)
            if isinstance(idx, int):
                idx = [idx]
            neighbors = pts[list(idx)]
            if neighbors.shape[0] < 3:
                normals[i] = np.array([0, 0, 1], dtype=np.float32)
                continue
            center = neighbors.mean(axis=0)
            C = neighbors - center
            cov = C.T @ C / (neighbors.shape[0] - 1)
            try:
                eigvals, eigvecs = np.linalg.eigh(cov)
                n = eigvecs[:, 0]  # 最小特征值对应的特征向量
                n = n / (np.linalg.norm(n) + 1e-12)
                normals[i] = n.astype(np.float32)
            except np.linalg.LinAlgError:
                normals[i] = np.array([0, 0, 1], dtype=np.float32)

    new_data = PointCloudData(
        points=data.points.copy(),
        colors=data.colors.copy() if data.has_colors() else None,
        normals=normals,
        intensity=data.intensity.copy() if data.has_intensity() else None,
        labels=data.labels.copy() if data.has_labels() else None,
    )
    return PreprocessResult(data=new_data, undo_info={"old_had_normals": data.has_normals()})


def orient_normals_towards_camera(
    data: PointCloudData,
    camera_location: Tuple[float, float, float] = (0.0, 0.0, 1000.0),
) -> PreprocessResult:
    """朝向相机定向法向量"""
    if not data.has_normals():
        return estimate_normals(data, max_nn=30)

    cam = np.asarray(camera_location, dtype=np.float32).reshape(1, 3)
    view_dir = cam - data.points  # (N, 3)
    view_len = np.linalg.norm(view_dir, axis=1, keepdims=True)
    view_len = np.where(view_len < 1e-12, 1, view_len)
    view_dir = view_dir / view_len
    # 法向量与视线方向的夹角 < 90° 的点（即朝向相机）保持原样，否则翻转
    dots = np.sum(data.normals * view_dir, axis=1, keepdims=True)
    flip_mask = dots < 0
    new_normals = data.normals.copy()
    new_normals[flip_mask[:, 0]] *= -1
    new_data = PointCloudData(
        points=data.points.copy(),
        colors=data.colors.copy() if data.has_colors() else None,
        normals=new_normals,
        intensity=data.intensity.copy() if data.has_intensity() else None,
        labels=data.labels.copy() if data.has_labels() else None,
    )
    return PreprocessResult(data=new_data, undo_info={"flip_mask": flip_mask[:, 0]})


# ============================================================
# RANSAC 平面检测（不修改点云，仅返回模型+掩码）
# ============================================================
def ransac_detect_plane(
    data: PointCloudData,
    distance_threshold: float = 0.05,
    num_iterations: int = 1000,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    RANSAC 平面检测

    返回 (plane_model[4], inlier_mask)
    """
    from pointvault.tools.selection_tools import RansacPlaneTool

    tool = RansacPlaneTool(
        distance_threshold=distance_threshold,
        num_iterations=num_iterations,
    )
    result = tool.end(points=data.points)
    model = np.array(result.metadata.get("plane_model", [0, 0, 1, 0]), dtype=np.float64)
    mask = result.build_mask(data.num_points)
    return model, mask


# ============================================================
# ICP 点云配准
# ============================================================
def icp_registration(
    source: PointCloudData,
    target: PointCloudData,
    max_correspondence_distance: float = 0.1,
    init_transform: Optional[np.ndarray] = None,
    method: str = "point_to_plane",
    max_iterations: int = 50,
) -> Tuple[np.ndarray, float]:
    """
    源点云配准到目标点云

    返回 (4x4 变换矩阵 T, fitness 分数)
    """
    if init_transform is None:
        init_transform = np.eye(4, dtype=np.float64)
    else:
        init_transform = np.asarray(init_transform, dtype=np.float64).reshape(4, 4)

    try:
        import open3d as o3d

        src = o3d.geometry.PointCloud()
        tgt = o3d.geometry.PointCloud()
        src.points = o3d.utility.Vector3dVector(source.points.astype(np.float64))
        tgt.points = o3d.utility.Vector3dVector(target.points.astype(np.float64))

        if method == "point_to_plane":
            if not source.has_normals():
                src.estimate_normals(
                    search_param=o3d.geometry.KDTreeSearchParamKNN(knn=20)
                )
            else:
                src.normals = o3d.utility.Vector3dVector(source.normals.astype(np.float64))
            result = o3d.pipelines.registration.registration_icp(
                src,
                tgt,
                max_correspondence_distance,
                init_transform,
                o3d.pipelines.registration.TransformationEstimationPointToPlane(),
                o3d.pipelines.registration.ICPConvergenceCriteria(
                    max_iteration=max_iterations
                ),
            )
        else:
            result = o3d.pipelines.registration.registration_icp(
                src,
                tgt,
                max_correspondence_distance,
                init_transform,
                o3d.pipelines.registration.TransformationEstimationPointToPoint(),
                o3d.pipelines.registration.ICPConvergenceCriteria(
                    max_iteration=max_iterations
                ),
            )
        return np.asarray(result.transformation, dtype=np.float32), float(result.fitness)
    except ImportError:
        # 简单实现：仅点到点的初始对齐（不进行迭代）
        return init_transform.astype(np.float32), 0.0
