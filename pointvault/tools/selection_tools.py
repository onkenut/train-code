"""
交互式选择工具（基础逻辑）

每个工具接收：
- 当前 3D 点云坐标
- 视口参数 + 视图投影矩阵（用于逆投影）
- 鼠标事件（拖拽起点/终点、路径、笔刷中心）

返回 SelectionResult:
    indices:     (M,) int64 被选中点的索引
    inlier_mask: (N,) bool  被选中掩码
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple, Type

import numpy as np

from pointvault.rendering.selection_pipeline import SelectionPipeline


@dataclass
class SelectionResult:
    """选择结果"""

    indices: np.ndarray = field(
        default_factory=lambda: np.empty(0, dtype=np.int64)
    )
    inlier_mask: Optional[np.ndarray] = None
    metadata: dict = field(default_factory=dict)

    @property
    def count(self) -> int:
        return int(self.indices.size)

    def build_mask(self, total_points: int) -> np.ndarray:
        if self.inlier_mask is not None and self.inlier_mask.size == total_points:
            return self.inlier_mask.astype(bool)
        m = np.zeros(total_points, dtype=bool)
        if self.indices.size > 0:
            idx = np.clip(self.indices, 0, total_points - 1)
            m[idx] = True
        return m


class SelectionTool(abc.ABC):
    """选择工具基类"""

    tool_name: str = "base"

    def __init__(self) -> None:
        self._pipeline = SelectionPipeline()

    @abc.abstractmethod
    def begin(self, *args: Any, **kwargs: Any) -> None:
        """开始一次选择操作（鼠标按下）"""

    @abc.abstractmethod
    def update(self, *args: Any, **kwargs: Any) -> SelectionResult:
        """更新选择状态（鼠标移动）"""

    @abc.abstractmethod
    def end(self, *args: Any, **kwargs: Any) -> SelectionResult:
        """结束选择（鼠标抬起）"""


# ============================================================
# 矩形框选工具
# ============================================================
class RectangleSelectTool(SelectionTool):
    tool_name = "rectangle"

    def __init__(self) -> None:
        super().__init__()
        self._start_xy: Optional[Tuple[float, float]] = None
        self._current_xy: Optional[Tuple[float, float]] = None

    def begin(
        self,
        sx: float,
        sy: float,
        points: np.ndarray,
        width: int,
        height: int,
        view_proj: np.ndarray,
    ) -> None:
        self._start_xy = (sx, sy)
        self._current_xy = (sx, sy)

    def update(
        self,
        sx: float,
        sy: float,
        points: np.ndarray,
        width: int,
        height: int,
        view_proj: np.ndarray,
        existing_mask: Optional[np.ndarray] = None,
        union: bool = True,
    ) -> SelectionResult:
        if self._start_xy is None:
            self._start_xy = (sx, sy)
        self._current_xy = (sx, sy)
        x0, y0 = self._start_xy
        idx = self._pipeline.pick_rectangle(
            points, x0, y0, sx, sy, width, height, view_proj
        )
        if existing_mask is not None and union:
            mask = existing_mask.astype(bool).copy()
            if idx.size > 0:
                mask[idx] = True
            return SelectionResult(indices=np.where(mask)[0], inlier_mask=mask)
        return SelectionResult(indices=idx)

    def end(
        self,
        sx: float,
        sy: float,
        points: np.ndarray,
        width: int,
        height: int,
        view_proj: np.ndarray,
        existing_mask: Optional[np.ndarray] = None,
        union: bool = True,
    ) -> SelectionResult:
        result = self.update(
            sx, sy, points, width, height, view_proj, existing_mask, union
        )
        self._start_xy = None
        self._current_xy = None
        return result

    def draw_preview(self) -> Optional[Tuple[float, float, float, float]]:
        """返回屏幕矩形 x0,y0,x1,y1 用于 GUI 预览"""
        if self._start_xy is None or self._current_xy is None:
            return None
        x0, y0 = self._start_xy
        x1, y1 = self._current_xy
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


# ============================================================
# 套索选择工具
# ============================================================
class LassoSelectTool(SelectionTool):
    tool_name = "lasso"

    def __init__(self) -> None:
        super().__init__()
        self._path: List[Tuple[float, float]] = []

    def begin(self, sx: float, sy: float, **kwargs: Any) -> None:
        self._path = [(sx, sy)]

    def update(
        self,
        sx: float,
        sy: float,
        points: np.ndarray,
        width: int,
        height: int,
        view_proj: np.ndarray,
        existing_mask: Optional[np.ndarray] = None,
        union: bool = True,
        min_points_for_preview: int = 4,
    ) -> SelectionResult:
        self._path.append((sx, sy))
        if len(self._path) < min_points_for_preview:
            # 点太少，先不计算
            if existing_mask is not None:
                return SelectionResult(
                    indices=np.where(existing_mask)[0],
                    inlier_mask=existing_mask,
                )
            return SelectionResult()
        idx = self._pipeline.pick_polygon(
            points, self._path, width, height, view_proj
        )
        if existing_mask is not None and union:
            mask = existing_mask.astype(bool).copy()
            if idx.size > 0:
                mask[idx] = True
            return SelectionResult(indices=np.where(mask)[0], inlier_mask=mask)
        return SelectionResult(indices=idx)

    def end(
        self,
        sx: float,
        sy: float,
        points: np.ndarray,
        width: int,
        height: int,
        view_proj: np.ndarray,
        existing_mask: Optional[np.ndarray] = None,
        union: bool = True,
    ) -> SelectionResult:
        if len(self._path) >= 3:
            idx = self._pipeline.pick_polygon(
                points, self._path, width, height, view_proj
            )
        else:
            idx = np.empty(0, dtype=np.int64)
        result: SelectionResult
        if existing_mask is not None and union:
            mask = existing_mask.astype(bool).copy()
            if idx.size > 0:
                mask[idx] = True
            result = SelectionResult(indices=np.where(mask)[0], inlier_mask=mask)
        else:
            result = SelectionResult(indices=idx)
        self._path = []
        return result

    @property
    def polygon_path(self) -> List[Tuple[float, float]]:
        return list(self._path)


# ============================================================
# 画笔工具
# ============================================================
class PaintBrushTool(SelectionTool):
    tool_name = "paint_brush"

    def __init__(self, radius: float = 30.0) -> None:
        super().__init__()
        self._radius = max(1.0, float(radius))
        self._is_painting = False

    @property
    def radius(self) -> float:
        return self._radius

    @radius.setter
    def radius(self, value: float) -> None:
        self._radius = max(1.0, float(value))

    def begin(
        self,
        sx: float,
        sy: float,
        points: np.ndarray,
        width: int,
        height: int,
        view_proj: np.ndarray,
        existing_mask: Optional[np.ndarray] = None,
        union: bool = True,
    ) -> SelectionResult:
        self._is_painting = True
        return self.update(
            sx, sy, points, width, height, view_proj, existing_mask, union
        )

    def update(
        self,
        sx: float,
        sy: float,
        points: np.ndarray,
        width: int,
        height: int,
        view_proj: np.ndarray,
        existing_mask: Optional[np.ndarray] = None,
        union: bool = True,
    ) -> SelectionResult:
        idx = self._pipeline.pick_circle(
            points, sx, sy, self._radius, width, height, view_proj
        )
        if existing_mask is not None and union:
            mask = existing_mask.astype(bool).copy()
            if idx.size > 0:
                mask[idx] = True
            return SelectionResult(indices=np.where(mask)[0], inlier_mask=mask)
        return SelectionResult(indices=idx)

    def end(
        self,
        sx: float,
        sy: float,
        points: np.ndarray,
        width: int,
        height: int,
        view_proj: np.ndarray,
        existing_mask: Optional[np.ndarray] = None,
        union: bool = True,
    ) -> SelectionResult:
        result = self.update(
            sx, sy, points, width, height, view_proj, existing_mask, union
        )
        self._is_painting = False
        return result

    @property
    def is_painting(self) -> bool:
        return self._is_painting


# ============================================================
# RANSAC 平面分割工具
# ============================================================
class RansacPlaneTool(SelectionTool):
    tool_name = "ransac_plane"

    def __init__(
        self,
        distance_threshold: float = 0.05,
        ransac_n: int = 3,
        num_iterations: int = 1000,
    ) -> None:
        super().__init__()
        self.distance_threshold = float(distance_threshold)
        self.ransac_n = int(ransac_n)
        self.num_iterations = int(num_iterations)
        self._seed_point_index: Optional[int] = None

    def begin(
        self,
        sx: float,
        sy: float,
        points: np.ndarray,
        width: int,
        height: int,
        view_proj: np.ndarray,
        **kwargs: Any,
    ) -> None:
        """点击选择种子点（取最近的点）"""
        self._seed_point_index = self._pipeline.pick_ray_single(
            points, sx, sy, width, height, view_proj, max_screen_dist=10.0
        )

    def update(self, *args: Any, **kwargs: Any) -> SelectionResult:
        return SelectionResult()

    def end(
        self,
        sx: Optional[float] = None,
        sy: Optional[float] = None,
        points: Optional[np.ndarray] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        view_proj: Optional[np.ndarray] = None,
        **kwargs: Any,
    ) -> SelectionResult:
        pts = kwargs.get("points", points)
        if pts is None:
            return SelectionResult()
        pts = np.asarray(pts, dtype=np.float64)
        if pts.shape[0] < 3:
            return SelectionResult()

        plane_model, inlier_mask = self._ransac_fit(
            pts,
            seed=self._seed_point_index,
        )
        self._seed_point_index = None
        inlier_idx = np.where(inlier_mask)[0].astype(np.int64)
        return SelectionResult(
            indices=inlier_idx,
            inlier_mask=inlier_mask,
            metadata={"plane_model": plane_model.tolist()},
        )

    # ---------- 纯 NumPy RANSAC 平面拟合 ----------
    def _ransac_fit(
        self,
        points: np.ndarray,
        seed: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        返回: (plane_model [a,b,c,d], inlier_mask)

        平面方程: ax + by + cz + d = 0
        """
        N = points.shape[0]
        best_inliers = np.zeros(N, dtype=bool)
        best_model = np.zeros(4, dtype=np.float64)
        best_count = 0

        rng = np.random.default_rng(42)
        indices = np.arange(N, dtype=np.int64)

        # 若有种子点，强制包含它
        for _ in range(self.num_iterations):
            if seed is not None:
                others = indices[indices != seed]
                sample_idx = np.concatenate(
                    [[seed], rng.choice(others, size=self.ransac_n - 1, replace=False)]
                )
            else:
                sample_idx = rng.choice(N, size=self.ransac_n, replace=False)
            sample = points[sample_idx]
            # 平面拟合
            try:
                v1 = sample[1] - sample[0]
                v2 = sample[2] - sample[0]
                normal = np.cross(v1, v2)
                n_len = np.linalg.norm(normal)
                if n_len < 1e-12:
                    continue
                normal = normal / n_len
                d = -np.dot(normal, sample[0])
                model = np.array([normal[0], normal[1], normal[2], d], dtype=np.float64)
            except Exception:
                continue
            # 计算点到平面的距离
            distances = np.abs(points @ model[:3] + model[3])
            inliers = distances < self.distance_threshold
            inlier_count = int(inliers.sum())
            if inlier_count > best_count:
                best_count = inlier_count
                best_inliers = inliers
                best_model = model

        # 优化：使用所有内点重新拟合
        if best_count >= 3:
            pts_in = points[best_inliers]
            centroid = pts_in.mean(axis=0)
            centered = pts_in - centroid
            try:
                U, S, Vt = np.linalg.svd(centered, full_matrices=False)
                normal_opt = Vt[-1]
                n_len = np.linalg.norm(normal_opt)
                if n_len > 1e-12:
                    normal_opt = normal_opt / n_len
                    d_opt = -np.dot(normal_opt, centroid)
                    best_model = np.array(
                        [normal_opt[0], normal_opt[1], normal_opt[2], d_opt], dtype=np.float64
                    )
                    distances = np.abs(points @ best_model[:3] + best_model[3])
                    best_inliers = distances < self.distance_threshold
            except Exception:
                pass

        return best_model, best_inliers


# ============================================================
# 工具工厂
# ============================================================
class SelectionToolFactory:
    """选择工具工厂"""

    _registry: dict = {
        "rectangle": RectangleSelectTool,
        "lasso": LassoSelectTool,
        "paint_brush": PaintBrushTool,
        "ransac_plane": RansacPlaneTool,
    }

    @classmethod
    def create(cls, tool_name: str, **kwargs: Any) -> SelectionTool:
        cls_type: Optional[Type[SelectionTool]] = cls._registry.get(tool_name)
        if cls_type is None:
            raise ValueError(f"未知选择工具: {tool_name}")
        return cls_type(**kwargs)

    @classmethod
    def available_tools(cls) -> List[str]:
        return list(cls._registry.keys())

    @classmethod
    def register(cls, name: str, tool_cls: Type[SelectionTool]) -> None:
        """用于注册第三方插件工具"""
        cls._registry[name] = tool_cls
