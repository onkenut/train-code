"""
全局常量与枚举定义
"""

from __future__ import annotations

from enum import IntEnum, Enum
from typing import Tuple


class LabelColor:
    """预定义的高对比度标签颜色调色板（最大支持256类）"""

    PALETTE: Tuple[Tuple[int, int, int], ...] = (
        (0, 0, 0),
        (244, 67, 54),
        (33, 150, 243),
        (76, 175, 80),
        (255, 193, 7),
        (156, 39, 176),
        (0, 188, 212),
        (255, 87, 34),
        (96, 125, 139),
        (63, 81, 181),
        (0, 150, 136),
        (233, 30, 99),
        (139, 195, 74),
        (255, 152, 0),
        (121, 85, 72),
        (158, 158, 158),
        (255, 235, 59),
        (103, 58, 183),
        (26, 35, 126),
        (0, 96, 100),
        (183, 28, 28),
        (27, 94, 32),
        (255, 214, 0),
        (170, 0, 255),
        (0, 229, 255),
        (255, 112, 67),
        (119, 65, 159),
        (46, 125, 50),
        (216, 67, 21),
        (66, 165, 245),
    )

    @classmethod
    def get(cls, index: int) -> Tuple[int, int, int]:
        idx = int(index) % len(cls.PALETTE)
        return cls.PALETTE[idx]

    @classmethod
    def to_float(cls, color: Tuple[int, int, int]) -> Tuple[float, float, float]:
        return (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)


class AnnotationMode(IntEnum):
    """标注/选择模式"""

    NAVIGATE = 0       # 导航：旋转/缩放/平移
    RECTANGLE = 1      # 矩形框选
    LASSO = 2          # 套索选择
    PAINT_BRUSH = 3    # 画笔刷选
    PLANE_RANSAC = 4   # RANSAC平面分割


class ColorMode(str, Enum):
    """点云着色模式"""

    HEIGHT = "height"
    RGB = "rgb"
    INTENSITY = "intensity"
    LABEL = "label"
    NORMAL = "normal"
    UNIFORM = "uniform"
    INSTANCE = "instance"


class OperationType(str, Enum):
    """操作历史中的操作类型"""

    IMPORT_POINTCLOUD = "import_pointcloud"
    REMOVE_POINTCLOUD = "remove_pointcloud"
    VOXEL_DOWNSAMPLE = "voxel_downsample"
    STATISTICAL_OUTLIER = "statistical_outlier"
    RADIUS_OUTLIER = "radius_outlier"
    ESTIMATE_NORMALS = "estimate_normals"
    ORIENT_NORMALS = "orient_normals"
    RANSAC_PLANE = "ransac_plane"
    ICP_REGISTRATION = "icp_registration"
    ANNOTATE_LABELS = "annotate_labels"
    CLEAR_ANNOTATIONS = "clear_annotations"
    TRANSFORM_POINTCLOUD = "transform_pointcloud"


UNLABELED_ID = 0  # 未标注标签的默认 ID
LABEL_FILE_EXT = ".labels"  # 标注文件扩展名（二进制 int32 数组）
