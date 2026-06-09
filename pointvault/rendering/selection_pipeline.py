"""
选择/拾取管线

实现屏幕空间到 3D 点的映射：

1. 屏幕坐标 (sx, sy) -> 归一化设备坐标 (NDC) (-1, 1)
2. NDC -> 视图-投影矩阵逆变换 -> 世界坐标射线
3. 射线/视锥体内点测试 -> 选中点索引

对于大规模点云（>50M），实现 CPU 端的八叉树剔除以加速：
- 点预先索引存入 BVH（使用 scipy.spatial.cKDTree 或 nanoflann）
- 视锥体平面方程 -> 与八叉树节点盒子做相交测试
- 对通过剔除的节点做逐点测试

本模块同时支持：
- 矩形框选
- 套索（多边形）
- 圆形画笔（按半径）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


# ============================================================
# 基础坐标转换
# ============================================================
def screen_to_ndc(
    sx: float,
    sy: float,
    width: int,
    height: int,
    flip_y: bool = True,
) -> Tuple[float, float]:
    """
    屏幕像素坐标 -> 归一化设备坐标 [-1, 1]

    flip_y: 屏幕左上角 (0,0) 到 OpenGL 左下角 (0,0) 的翻转
    """
    x = (2.0 * sx / max(width, 1)) - 1.0
    y = 1.0 - (2.0 * sy / max(height, 1)) if flip_y else (2.0 * sy / max(height, 1)) - 1.0
    return x, y


def ndc_to_world_ray(
    ndc_x: float,
    ndc_y: float,
    view_proj_inv: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    NDC 坐标 -> 世界坐标射线

    输入 4x4 的 (projection * view) 的逆矩阵
    返回: (origin, direction normalized)
    """
    inv = np.asarray(view_proj_inv, dtype=np.float64).reshape(4, 4)
    # 近平面
    near = np.array([ndc_x, ndc_y, -1.0, 1.0], dtype=np.float64)
    far = np.array([ndc_x, ndc_y, 1.0, 1.0], dtype=np.float64)
    near_w = inv @ near
    far_w = inv @ far
    near_w /= near_w[3]
    far_w /= far_w[3]
    origin = near_w[:3]
    direction = far_w[:3] - origin
    direction /= np.linalg.norm(direction) + 1e-12
    return origin.astype(np.float32), direction.astype(np.float32)


# ============================================================
# 视锥体（6 个平面）
# ============================================================
@dataclass
class Frustum:
    """6 个平面方程，每个平面 (a, b, c, d) 满足 ax + by + cz + d >= 0 表示在内部"""

    planes: np.ndarray  # (6, 4) float32

    def contains_point(self, p: np.ndarray) -> bool:
        ph = np.concatenate([np.asarray(p, dtype=np.float32), np.ones(1, dtype=np.float32)])
        return bool(np.all(self.planes @ ph >= -1e-4))

    def contains_points_batch(self, pts: np.ndarray) -> np.ndarray:
        """批量测试 (N, 3)，返回 (N,) bool"""
        pts = np.asarray(pts, dtype=np.float32)
        N = pts.shape[0]
        hom = np.hstack([pts, np.ones((N, 1), dtype=np.float32)])  # (N,4)
        # planes: (6,4) → 右乘需要 (4,6)，因此只转置一次
        dists = hom @ self.planes.astype(np.float32).T  # (N,4) @ (4,6) = (N,6)
        return np.all(dists >= -1e-4, axis=1)

    def intersects_aabb(
        self,
        min_corner: np.ndarray,
        max_corner: np.ndarray,
    ) -> bool:
        """视锥体与 AABB 相交判定（SAT 简化版）"""
        mins = np.asarray(min_corner, dtype=np.float32)
        maxs = np.asarray(max_corner, dtype=np.float32)
        # 对每个平面，取 AABB 中最靠近平面负侧的顶点
        for plane in self.planes:
            a, b, c, d = plane
            # 选择角点
            corner = np.array(
                [
                    maxs[0] if a < 0 else mins[0],
                    maxs[1] if b < 0 else mins[1],
                    maxs[2] if c < 0 else mins[2],
                    1.0,
                ],
                dtype=np.float32,
            )
            if plane.dot(corner) < -1e-4:
                return False
        return True


def frustum_from_screen_rect(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    width: int,
    height: int,
    view_proj_inv: np.ndarray,
) -> Frustum:
    """
    根据屏幕矩形构造视锥体

    (x0,y0), (x1,y1) 为屏幕对角顶点（像素）
    """
    # 归一化
    xa, ya = min(x0, x1), min(y0, y1)
    xb, yb = max(x0, x1), max(y0, y1)
    # 4 个近平面角
    corners_ndc = [
        screen_to_ndc(xa, ya, width, height),
        screen_to_ndc(xb, ya, width, height),
        screen_to_ndc(xb, yb, width, height),
        screen_to_ndc(xa, yb, width, height),
    ]
    near_points = []
    far_points = []
    for nx, ny in corners_ndc:
        o, d = ndc_to_world_ray(nx, ny, view_proj_inv)
        near_points.append(o)
        far_points.append(o + d * 1e4)  # 10km 远

    near_points = np.array(near_points, dtype=np.float32)
    far_points = np.array(far_points, dtype=np.float32)
    # 构造 6 个平面：左、右、下、上、近、远
    # 使用三个点求平面方程
    def _plane_from_three(p0, p1, p2):
        v1 = p1 - p0
        v2 = p2 - p0
        n = np.cross(v1, v2)
        n = n / (np.linalg.norm(n) + 1e-12)
        d = -np.dot(n, p0)
        return np.array([n[0], n[1], n[2], d], dtype=np.float32)

    ray_orig = np.mean(near_points, axis=0)  # 近似相机位置

    def _orient(plane, interior_pt):
        if np.dot(plane[:3], interior_pt) + plane[3] < 0:
            return -plane
        return plane

    left = _plane_from_three(ray_orig, near_points[0], near_points[3])
    right = _plane_from_three(ray_orig, near_points[2], near_points[1])
    bottom = _plane_from_three(ray_orig, near_points[1], near_points[2])
    top = _plane_from_three(ray_orig, near_points[3], near_points[0])
    near_plane = _plane_from_three(near_points[0], near_points[1], near_points[2])
    far_plane = _plane_from_three(far_points[2], far_points[1], far_points[0])

    # 朝向内部
    interior = (np.mean(near_points, axis=0) + np.mean(far_points, axis=0)) * 0.5
    planes = np.stack(
        [
            _orient(left, interior),
            _orient(right, interior),
            _orient(bottom, interior),
            _orient(top, interior),
            _orient(near_plane, interior),
            _orient(far_plane, interior),
        ]
    )
    return Frustum(planes=planes)


def frustum_from_polygon(
    polygon_xy: List[Tuple[float, float]],
    width: int,
    height: int,
    view_proj_inv: np.ndarray,
) -> Frustum:
    """套索多边形构造视锥体（使用凸包或取包围盒简化）"""
    if len(polygon_xy) < 3:
        x0 = polygon_xy[0][0] if polygon_xy else 0
        y0 = polygon_xy[0][1] if polygon_xy else 0
        return frustum_from_screen_rect(x0, y0, x0 + 1, y0 + 1, width, height, view_proj_inv)
    # 简化：取多边形 bbox 做视锥体，再逐点做多边形测试
    xs = [p[0] for p in polygon_xy]
    ys = [p[1] for p in polygon_xy]
    return frustum_from_screen_rect(
        min(xs), min(ys), max(xs), max(ys), width, height, view_proj_inv
    )


# ============================================================
# 屏幕空间点内测试（多边形）
# ============================================================
def point_in_polygon(
    pts_xy: np.ndarray,
    polygon_xy: List[Tuple[float, float]],
) -> np.ndarray:
    """
    射线法点在多边形内判定

    pts_xy: (N, 2) 屏幕坐标点
    polygon_xy: [(x,y), ...] 多边形顶点
    返回: (N,) bool
    """
    poly = np.array(polygon_xy, dtype=np.float32)
    if poly.shape[0] < 3:
        return np.zeros(pts_xy.shape[0], dtype=bool)

    n = poly.shape[0]
    inside = np.zeros(pts_xy.shape[0], dtype=bool)
    x = pts_xy[:, 0]
    y = pts_xy[:, 1]
    for i in range(n):
        j = (i + 1) % n
        xi, yi = poly[i]
        xj, yj = poly[j]
        intersect = ((yi > y) != (yj > y)) & (
            x < (xj - xi) * (y - yi) / ((yj - yi) + 1e-12) + xi
        )
        inside ^= intersect
    return inside


# ============================================================
# 主选择管线
# ============================================================
class SelectionPipeline:
    """
    选择管线：将屏幕区域转换为点索引。

    为支持大规模点云，内部提供多级加速：
    1. 视锥体粗筛选（剔除 AABB）
    2. 屏幕空间投影细筛选（对候选点做精确包含测试）
    """

    def __init__(self) -> None:
        self._cache: dict = {}

    # ---------- 公共辅助 ----------
    @staticmethod
    def _prepare_points(points, dtype=np.float32) -> Tuple[np.ndarray, int]:
        """
        对输入点做统一的防御性处理，返回 (处理后的数组, 点数 N)。

        处理以下异常输入：
        - None → 返回 (empty(0,3), 0)
        - 标量数组 shape=() → 返回 (empty(0,3), 0)
        - 一维数组 shape=(N,) 或 (3,) → 尝试 reshape 为 (N,3) 或 (1,3)
        - 二维数组但列数 != 3 → 取前 3 列或报错
        - 空数组 shape=(0, x) → 返回 (empty(0,3), 0)
        """
        if points is None:
            return np.empty((0, 3), dtype=dtype), 0
        pts = np.asarray(points, dtype=dtype)
        if pts.ndim == 0:
            # 0 维标量数组（常见于传入 None + 指定 dtype 后的结果）
            return np.empty((0, 3), dtype=dtype), 0
        if pts.ndim == 1:
            # 一维：可能是 (3,) 单点或 (N*3,) 展平
            if pts.size == 3:
                pts = pts.reshape(1, 3)
            elif pts.size % 3 == 0:
                pts = pts.reshape(-1, 3)
            else:
                return np.empty((0, 3), dtype=dtype), 0
        if pts.ndim != 2 or pts.shape[1] < 3:
            # 维度不对或列数不足，安全返回
            return np.empty((0, 3), dtype=dtype), 0
        if pts.shape[1] > 3:
            pts = pts[:, :3]
        N = pts.shape[0]
        if N == 0:
            return pts, 0
        return pts.astype(dtype, copy=False), N

    # ---------- 矩形框选 ----------
    def pick_rectangle(
        self,
        points: np.ndarray,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        width: int,
        height: int,
        view_proj_matrix: np.ndarray,
        subset_mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        返回选中点的索引数组 (M,) int64
        """
        points, N = self._prepare_points(points)
        if N == 0:
            return np.empty(0, dtype=np.int64)
        view_proj = np.asarray(view_proj_matrix, dtype=np.float64).reshape(4, 4)
        vp_inv = np.linalg.inv(view_proj)

        # 构建视锥体
        frustum = frustum_from_screen_rect(x0, y0, x1, y1, width, height, vp_inv)

        # 1. 粗筛：视锥体包含测试
        if subset_mask is not None:
            indices = np.where(subset_mask)[0].astype(np.int64)
            candidate_pts = points[indices]
        else:
            indices = np.arange(points.shape[0], dtype=np.int64)
            candidate_pts = points

        if candidate_pts.shape[0] == 0:
            return np.empty(0, dtype=np.int64)

        mask1 = frustum.contains_points_batch(candidate_pts)
        cand_idx = indices[mask1]
        if cand_idx.size == 0:
            return cand_idx

        # 2. 精筛：投影到屏幕，判断在矩形内部
        pts_in = points[cand_idx]
        screen_xy = self._project_to_screen(pts_in, view_proj, width, height)
        xa, ya = min(x0, x1), min(y0, y1)
        xb, yb = max(x0, x1), max(y0, y1)
        mask2 = (
            (screen_xy[:, 0] >= xa)
            & (screen_xy[:, 0] <= xb)
            & (screen_xy[:, 1] >= ya)
            & (screen_xy[:, 1] <= yb)
        )
        return cand_idx[mask2]

    # ---------- 套索 ----------
    def pick_polygon(
        self,
        points: np.ndarray,
        polygon_xy: List[Tuple[float, float]],
        width: int,
        height: int,
        view_proj_matrix: np.ndarray,
        subset_mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        if len(polygon_xy) < 3:
            return np.empty(0, dtype=np.int64)
        points, N = self._prepare_points(points)
        if N == 0:
            return np.empty(0, dtype=np.int64)
        view_proj = np.asarray(view_proj_matrix, dtype=np.float64).reshape(4, 4)
        vp_inv = np.linalg.inv(view_proj)
        xs = [p[0] for p in polygon_xy]
        ys = [p[1] for p in polygon_xy]
        frustum = frustum_from_screen_rect(
            min(xs), min(ys), max(xs), max(ys), width, height, vp_inv
        )

        if subset_mask is not None:
            indices = np.where(subset_mask)[0].astype(np.int64)
        else:
            indices = np.arange(points.shape[0], dtype=np.int64)

        candidate_pts = points[indices]
        mask1 = frustum.contains_points_batch(candidate_pts)
        cand_idx = indices[mask1]
        if cand_idx.size == 0:
            return cand_idx

        # 精筛：点在多边形内
        pts_in = points[cand_idx]
        screen_xy = self._project_to_screen(pts_in, view_proj, width, height)
        mask2 = point_in_polygon(screen_xy, polygon_xy)
        return cand_idx[mask2]

    # ---------- 画笔圆形 ----------
    def pick_circle(
        self,
        points: np.ndarray,
        cx: float,
        cy: float,
        radius: float,
        width: int,
        height: int,
        view_proj_matrix: np.ndarray,
        subset_mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        points, N = self._prepare_points(points)
        if N == 0:
            return np.empty(0, dtype=np.int64)
        view_proj = np.asarray(view_proj_matrix, dtype=np.float64).reshape(4, 4)
        vp_inv = np.linalg.inv(view_proj)
        frustum = frustum_from_screen_rect(
            cx - radius, cy - radius, cx + radius, cy + radius, width, height, vp_inv
        )

        if subset_mask is not None:
            indices = np.where(subset_mask)[0].astype(np.int64)
        else:
            indices = np.arange(points.shape[0], dtype=np.int64)

        candidate_pts = points[indices]
        mask1 = frustum.contains_points_batch(candidate_pts)
        cand_idx = indices[mask1]
        if cand_idx.size == 0:
            return cand_idx

        pts_in = points[cand_idx]
        screen_xy = self._project_to_screen(pts_in, view_proj, width, height)
        dx = screen_xy[:, 0] - cx
        dy = screen_xy[:, 1] - cy
        mask2 = (dx * dx + dy * dy) <= radius * radius
        return cand_idx[mask2]

    # ---------- 射线单点点选 ----------
    def pick_ray_single(
        self,
        points: np.ndarray,
        sx: float,
        sy: float,
        width: int,
        height: int,
        view_proj_matrix: np.ndarray,
        max_screen_dist: float = 5.0,
    ) -> Optional[int]:
        """返回距离鼠标最近的点的索引"""
        points, N = self._prepare_points(points)
        if N == 0:
            return None
        view_proj = np.asarray(view_proj_matrix, dtype=np.float64).reshape(4, 4)
        vp_inv = np.linalg.inv(view_proj)

        # 视锥体：以鼠标为中心的 5 像素框
        frustum = frustum_from_screen_rect(
            sx - max_screen_dist,
            sy - max_screen_dist,
            sx + max_screen_dist,
            sy + max_screen_dist,
            width,
            height,
            vp_inv,
        )
        indices = np.arange(points.shape[0], dtype=np.int64)
        mask1 = frustum.contains_points_batch(points)
        cand_idx = indices[mask1]
        if cand_idx.size == 0:
            return None

        pts_in = points[cand_idx]
        screen_xy = self._project_to_screen(pts_in, view_proj, width, height)
        dx = screen_xy[:, 0] - sx
        dy = screen_xy[:, 1] - sy
        dist2 = dx * dx + dy * dy
        nearest_local = int(np.argmin(dist2))
        if dist2[nearest_local] > max_screen_dist * max_screen_dist:
            return None
        return int(cand_idx[nearest_local])

    # ---------- 内部投影 ----------
    @staticmethod
    def _project_to_screen(
        pts: np.ndarray,
        view_proj: np.ndarray,
        width: int,
        height: int,
    ) -> np.ndarray:
        """
        世界点 -> 屏幕像素坐标 (N, 2)

        注意：OpenCV/Qt 屏幕左上角为 (0,0)，与 OpenGL NDC 一致
        """
        N = pts.shape[0]
        if N == 0:
            return np.empty((0, 2), dtype=np.float32)
        ones = np.ones((N, 1), dtype=np.float64)
        hom = np.hstack([pts.astype(np.float64), ones])  # (N, 4)
        clip = hom @ view_proj.T  # (N,4)
        w = clip[:, 3:4]
        w = np.where(np.abs(w) < 1e-12, 1e-12, w)
        ndc = clip[:, :3] / w  # (N,3) range [-1,1]
        # NDC -> screen
        screen_x = (ndc[:, 0] + 1.0) * 0.5 * width
        screen_y = (1.0 - ndc[:, 1]) * 0.5 * height  # 翻转 Y
        return np.stack([screen_x, screen_y], axis=1).astype(np.float32)


# ============================================================
# 便捷函数
# ============================================================
def pick_points_in_frustum(
    points: np.ndarray,
    frustum: Frustum,
) -> np.ndarray:
    """返回视锥体内点的索引"""
    mask = frustum.contains_points_batch(points)
    return np.where(mask)[0]
