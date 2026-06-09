"""
3D 渲染引擎包 - 基于 Open3D 的可视化器封装，集成 PySide6

核心组件：
- ColorMapper:    各种着色模式的颜色计算
- CameraManager:  相机位姿、书签、标准视图
- Renderer:       封装 Open3D Visualizer 与点云加载、着色、更新
- Scene:          管理多个点云对象、标注框、地面网格、坐标轴
"""

from pointvault.rendering.color_mapper import (
    ColorMapper,
    height_color,
    rgb_color,
    intensity_color,
    label_color,
    normal_color,
    uniform_color,
    apply_colormap_to_array,
)
from pointvault.rendering.camera import (
    CameraManager,
    CameraPose,
    StandardView,
    ViewBookmark,
)
from pointvault.rendering.renderer import (
    PointCloudRenderer,
    SceneObject,
    create_colored_pointcloud,
)
from pointvault.rendering.selection_pipeline import (
    SelectionPipeline,
    screen_to_ndc,
    pick_points_in_frustum,
)

__all__ = [
    "ColorMapper",
    "height_color",
    "rgb_color",
    "intensity_color",
    "label_color",
    "normal_color",
    "uniform_color",
    "apply_colormap_to_array",
    "CameraManager",
    "CameraPose",
    "StandardView",
    "ViewBookmark",
    "PointCloudRenderer",
    "SceneObject",
    "create_colored_pointcloud",
    "SelectionPipeline",
    "screen_to_ndc",
    "pick_points_in_frustum",
]
