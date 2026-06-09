"""
交互式工具包

包含：
- selection_tools.py:   选择/标注工具（矩形框、套索、画笔、RANSAC平面）
- preprocess.py:        点云预处理（下采样、去噪、法向量估计、配准）
- history.py:           撤销/重做命令栈
"""

from pointvault.tools.selection_tools import (
    SelectionTool,
    RectangleSelectTool,
    LassoSelectTool,
    PaintBrushTool,
    RansacPlaneTool,
    SelectionToolFactory,
    SelectionResult,
)
from pointvault.tools.preprocess import (
    voxel_downsample,
    statistical_outlier_removal,
    radius_outlier_removal,
    estimate_normals,
    orient_normals_towards_camera,
    ransac_detect_plane,
    icp_registration,
)
from pointvault.tools.history import (
    CommandHistory,
    Command,
    PointCloudEditCommand,
    AnnotationEditCommand,
)

__all__ = [
    "SelectionTool",
    "RectangleSelectTool",
    "LassoSelectTool",
    "PaintBrushTool",
    "RansacPlaneTool",
    "SelectionToolFactory",
    "SelectionResult",
    "voxel_downsample",
    "statistical_outlier_removal",
    "radius_outlier_removal",
    "estimate_normals",
    "orient_normals_towards_camera",
    "ransac_detect_plane",
    "icp_registration",
    "CommandHistory",
    "Command",
    "PointCloudEditCommand",
    "AnnotationEditCommand",
]
