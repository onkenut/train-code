"""
颜色映射器 - 实现点云各种着色模式

所有函数的输入为 (N, ...) 的 numpy 数组，输出为 (N, 3) float32 的 RGB [0,1]。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
from matplotlib import cm as _cm

from pointvault.constants import UNLABELED_ID
from pointvault.db.models import LabelDefinition


# ---------- 内置 colormap 包装 ----------
_COLORMAP_CACHE: Dict[str, np.ndarray] = {}


def _get_cmap_array(name: str, n: int = 256) -> np.ndarray:
    if name in _COLORMAP_CACHE:
        return _COLORMAP_CACHE[name]
    try:
        cmap = _cm.get_cmap(name)
    except Exception:
        cmap = _cm.viridis
    arr = np.zeros((n, 3), dtype=np.float32)
    for i in range(n):
        rgba = cmap(i / (n - 1))
        arr[i, 0] = rgba[0]
        arr[i, 1] = rgba[1]
        arr[i, 2] = rgba[2]
    _COLORMAP_CACHE[name] = arr
    return arr


def apply_colormap_to_array(
    scalar: np.ndarray,
    cmap_name: str = "viridis",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> np.ndarray:
    """对标量数组应用 colormap，返回 (N, 3) float32 RGB"""
    scalar = np.asarray(scalar, dtype=np.float32).ravel()
    if scalar.size == 0:
        return np.zeros((0, 3), dtype=np.float32)
    if vmin is None:
        vmin = float(np.nanmin(scalar))
    if vmax is None:
        vmax = float(np.nanmax(scalar))
    rng = vmax - vmin
    if rng <= 0:
        rng = 1.0
    normed = np.clip((scalar - vmin) / rng, 0.0, 1.0)
    cmap = _get_cmap_array(cmap_name, 256)
    idx = (normed * 255).astype(np.int32)
    return cmap[idx]


# ---------- 各着色模式 ----------
def height_color(
    points: np.ndarray,
    axis: int = 2,
    cmap: str = "turbo",
    global_min: Optional[float] = None,
    global_max: Optional[float] = None,
) -> np.ndarray:
    if points.size == 0:
        return np.zeros((0, 3), dtype=np.float32)
    z = points[:, axis].astype(np.float32)
    return apply_colormap_to_array(z, cmap, vmin=global_min, vmax=global_max)


def rgb_color(colors: np.ndarray) -> np.ndarray:
    if colors is None or colors.size == 0:
        return np.zeros((0, 3), dtype=np.float32)
    c = np.asarray(colors, dtype=np.float32)
    if c.max() > 1.0:
        c = c / 255.0
    return np.clip(c, 0.0, 1.0)


def intensity_color(
    intensity: np.ndarray,
    cmap: str = "inferno",
) -> np.ndarray:
    if intensity is None or intensity.size == 0:
        return np.zeros((0, 3), dtype=np.float32)
    v = np.asarray(intensity, dtype=np.float32).ravel()
    return apply_colormap_to_array(v, cmap, vmin=0.0, vmax=1.0)


def label_color(
    labels: np.ndarray,
    label_map: Dict[int, LabelDefinition],
    default_color: Tuple[float, float, float] = (0.5, 0.5, 0.5),
) -> np.ndarray:
    """根据标签映射生成 (N, 3) RGB"""
    if labels is None or labels.size == 0:
        return np.zeros((0, 3), dtype=np.float32)
    lab = np.asarray(labels, dtype=np.int32).ravel()
    out = np.zeros((lab.size, 3), dtype=np.float32)
    out[:, 0] = default_color[0]
    out[:, 1] = default_color[1]
    out[:, 2] = default_color[2]
    unique = np.unique(lab)
    for lid in unique:
        if lid == UNLABELED_ID:
            continue
        ld = label_map.get(int(lid))
        if ld is not None:
            mask = lab == lid
            out[mask, 0] = ld.color_float[0]
            out[mask, 1] = ld.color_float[1]
            out[mask, 2] = ld.color_float[2]
    return out


def normal_color(normals: np.ndarray) -> np.ndarray:
    if normals is None or normals.size == 0:
        return np.zeros((0, 3), dtype=np.float32)
    n = np.asarray(normals, dtype=np.float32)
    # 归一化到 [0,1]
    return np.clip((n + 1.0) * 0.5, 0.0, 1.0)


def uniform_color(
    n_points: int,
    color: Tuple[float, float, float] = (0.8, 0.8, 0.8),
) -> np.ndarray:
    arr = np.zeros((n_points, 3), dtype=np.float32)
    arr[:, 0] = color[0]
    arr[:, 1] = color[1]
    arr[:, 2] = color[2]
    return arr


# ---------- 统一入口 ----------
@dataclass
class ColorMapper:
    """集中管理颜色映射参数，避免每次重建 LUT"""

    mode: str = "height"
    label_map: Optional[Dict[int, LabelDefinition]] = None
    height_axis: int = 2
    height_cmap: str = "turbo"
    intensity_cmap: str = "inferno"
    default_uniform: Tuple[float, float, float] = (0.7, 0.7, 0.7)
    # 全局范围（跨点云使用同一个 z min/max 以便对比）
    global_min: Optional[float] = None
    global_max: Optional[float] = None

    def compute(
        self,
        points: np.ndarray,
        colors: Optional[np.ndarray] = None,
        normals: Optional[np.ndarray] = None,
        intensity: Optional[np.ndarray] = None,
        labels: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        mode = self.mode.lower()
        if mode == "rgb" and colors is not None:
            return rgb_color(colors)
        if mode == "label" and labels is not None and self.label_map is not None:
            return label_color(labels, self.label_map)
        if mode == "normal" and normals is not None:
            return normal_color(normals)
        if mode == "intensity" and intensity is not None:
            return intensity_color(intensity, cmap=self.intensity_cmap)
        if mode == "uniform":
            return uniform_color(points.shape[0], self.default_uniform)
        # 默认 height
        return height_color(
            points,
            axis=self.height_axis,
            cmap=self.height_cmap,
            global_min=self.global_min,
            global_max=self.global_max,
        )

    def highlight_selection(
        self,
        base_colors: np.ndarray,
        selected_mask: Optional[np.ndarray],
        selection_color: Tuple[float, float, float] = (1.0, 1.0, 0.0),
        alpha: float = 0.6,
    ) -> np.ndarray:
        if selected_mask is None or not np.any(selected_mask):
            return base_colors
        out = base_colors.copy()
        sc = np.asarray(selection_color, dtype=np.float32)
        out[selected_mask] = (1 - alpha) * out[selected_mask] + alpha * sc
        return out
