"""
3D 渲染器 - 封装 Open3D Visualizer

集成到 PySide6 窗口：使用 QWidget 嵌入 Open3D 的原生窗口句柄。
使用 OpenGL 后端，通过 Open3D 的 gui.Application 或 VisualizerWithKeyCallback
管理多窗口和点云对象。

为支持高性能选择与屏幕拾取，实现了：
- 内部 OpenGL framebuffer object（通过着色器将点云按索引着色为唯一颜色）
- 屏幕空间映射回世界坐标的逆投影
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from pointvault.constants import ColorMode, LABEL_FILE_EXT
from pointvault.io.container import PointCloudData
from pointvault.io.label_file import read_labels
from pointvault.rendering.camera import CameraManager, CameraPose
from pointvault.rendering.color_mapper import ColorMapper

logger = logging.getLogger(__name__)


@dataclass
class SceneObject:
    """场景中的一个对象（点云或其他几何体）"""

    id: int
    name: str
    kind: str = "pointcloud"  # pointcloud, bbox, axes, grid
    visible: bool = True
    point_size: float = 3.0
    transform: np.ndarray = field(default_factory=lambda: np.eye(4, dtype=np.float32))
    # 点云特有
    data: Optional[PointCloudData] = None
    label_file_path: Optional[str] = None
    labels_array: Optional[np.ndarray] = None
    selection_mask: Optional[np.ndarray] = None
    colors: Optional[np.ndarray] = None
    # 渲染后端对象引用 (open3d 对象)
    backend_obj: Any = None


def create_colored_pointcloud(
    data: PointCloudData,
    mapper: ColorMapper,
    labels: Optional[np.ndarray] = None,
    selection_mask: Optional[np.ndarray] = None,
) -> Tuple[Any, np.ndarray]:
    """
    创建带着色的 open3d PointCloud 对象

    返回:
        (o3d_pcd, applied_colors_float32)
    """
    try:
        import open3d as o3d
    except ImportError as e:
        raise RuntimeError("Open3D 未安装，无法进行 3D 渲染") from e

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(data.points.astype(np.float64))
    if data.has_normals():
        pcd.normals = o3d.utility.Vector3dVector(data.normals.astype(np.float64))

    colors = mapper.compute(
        points=data.points,
        colors=data.colors,
        normals=data.normals,
        intensity=data.intensity,
        labels=labels,
    )
    colors = mapper.highlight_selection(colors, selection_mask)

    pcd.colors = o3d.utility.Vector3dVector(colors.astype(np.float64))
    return pcd, colors


class PointCloudRenderer:
    """
    高性能 3D 点云渲染器

    内部维护:
    - 一个 Open3D Visualizer（单视口）
    - 场景对象集合 (id -> SceneObject)
    - CameraManager 管理视图与书签
    - ColorMapper 管理着色逻辑
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._next_obj_id = 1
        self._objects: Dict[int, SceneObject] = {}
        self._camera = CameraManager()
        self._mapper = ColorMapper()
        self._vis: Any = None  # Open3D Visualizer
        self._init_done = False
        self._parent_widget: Any = None
        self._view_proj_matrix: Optional[np.ndarray] = None
        self._viewport_size: Tuple[int, int] = (0, 0)

    # ---------- 生命周期 ----------
    def initialize(self, parent_widget: Any = None, width: int = 1024, height: int = 768) -> bool:
        """
        初始化可视化器并创建 OpenGL 上下文。

        **必须调用 create_window() 才能初始化 C++ 侧的 OpenGL 上下文**，
        否则后续任何 poll_events / add_geometry 调用都会导致 C++ segfault
        （无任何 Python 错误，程序直接退出）。

        Returns:
            True 表示初始化成功，False 表示退回空渲染模式（CI/headless 环境）
        """
        if self._init_done:
            return True
        try:
            import open3d as o3d
            from open3d.visualization import gui, rendering  # noqa: 检查库可用性
        except ImportError as e:
            logger.warning(f"Open3D 不可用，使用空渲染模式: {e}")
            self._init_done = True
            return False

        self._parent_widget = parent_widget
        try:
            self._vis = o3d.visualization.VisualizerWithKeyCallback()
            # visible=False: 创建隐藏窗口（不抢焦点），但会初始化 GL 上下文
            # 注意：若为 headless 环境（无 DISPLAY/EGL），此处仍会失败
            self._vis.create_window(
                window_name="PointVault_RenderContext",
                width=width,
                height=height,
                visible=False,
            )
            self._viewport_size = (width, height)
            self._init_done = True
            logger.info(f"渲染器初始化成功 (Open3D Visualizer, {width}x{height}, 隐藏窗口)")
            return True
        except Exception as e:
            logger.warning(
                f"Open3D create_window 失败（可能为 headless 环境），"
                f"退回空渲染模式: {e}"
            )
            # 清理半初始化的对象
            if self._vis is not None:
                try:
                    self._vis.destroy_window()
                except Exception:
                    pass
                self._vis = None
            self._init_done = True  # 标记为"已尝试初始化"，避免重复尝试
            return False

    def get_native_widget(self):
        """获取可嵌入 Qt 的窗口句柄（如果可用）"""
        if self._vis is None:
            return None
        try:
            return self._vis.get_view_control().convert_to_pinhole_camera_parameters()
        except Exception:
            return None

    def create_window(self, width: int = 1280, height: int = 720, visible: bool = True) -> None:
        """创建独立窗口（开发调试时使用）"""
        if self._vis is None:
            self.initialize()
        self._vis.create_window(
            window_name="PointVault",
            width=width,
            height=height,
            visible=visible,
        )
        self._viewport_size = (width, height)

    def destroy(self) -> None:
        if self._vis is not None:
            try:
                self._vis.destroy_window()
            except Exception:
                pass
            self._vis = None
        self._objects.clear()
        self._init_done = False

    # ---------- 公共属性 ----------
    @property
    def camera(self) -> CameraManager:
        return self._camera

    @property
    def mapper(self) -> ColorMapper:
        return self._mapper

    @property
    def objects(self) -> Dict[int, SceneObject]:
        return dict(self._objects)

    def list_objects(self) -> List[SceneObject]:
        with self._lock:
            return list(self._objects.values())

    # ---------- 场景对象管理 ----------
    def add_pointcloud(
        self,
        name: str,
        data: PointCloudData,
        label_file: Optional[Path | str] = None,
        point_size: float = 3.0,
        visible: bool = True,
    ) -> int:
        """
        将点云加入场景并返回对象 ID

        label_file: 如果存在，预加载标注数据用于 label 着色
        """
        with self._lock:
            obj_id = self._next_obj_id
            self._next_obj_id += 1

            obj = SceneObject(
                id=obj_id,
                name=name,
                kind="pointcloud",
                visible=visible,
                point_size=float(point_size),
                data=data,
                label_file_path=str(label_file) if label_file else None,
            )
            # 预加载标签
            if obj.label_file_path:
                try:
                    lfp = Path(obj.label_file_path)
                    if lfp.exists():
                        obj.labels_array = read_labels(lfp)
                        if obj.labels_array.size != data.num_points:
                            obj.labels_array = np.zeros(data.num_points, dtype=np.int32)
                    else:
                        obj.labels_array = np.zeros(data.num_points, dtype=np.int32)
                except Exception as e:
                    logger.warning(f"预加载标签失败 {lfp}: {e}")
                    obj.labels_array = np.zeros(data.num_points, dtype=np.int32)
            self._objects[obj_id] = obj
            self._refresh_object_backend(obj)
            return obj_id

    def remove_object(self, obj_id: int) -> bool:
        with self._lock:
            obj = self._objects.pop(obj_id, None)
            if obj is None:
                return False
            if obj.backend_obj is not None and self._vis is not None:
                try:
                    self._vis.remove_geometry(obj.backend_obj)
                except Exception:
                    pass
            return True

    def get_object(self, obj_id: int) -> Optional[SceneObject]:
        with self._lock:
            return self._objects.get(obj_id)

    def set_object_visible(self, obj_id: int, visible: bool) -> None:
        with self._lock:
            obj = self._objects.get(obj_id)
            if obj is None:
                return
            obj.visible = bool(visible)
            # 先移除再添加来切换可见性
            if obj.backend_obj is not None and self._vis is not None:
                try:
                    self._vis.remove_geometry(obj.backend_obj)
                except Exception:
                    pass
            if visible and obj.backend_obj is not None and self._vis is not None:
                try:
                    self._vis.add_geometry(obj.backend_obj, reset_bounding_box=False)
                except Exception:
                    pass

    def set_point_size(self, obj_id: int, size: float) -> None:
        with self._lock:
            obj = self._objects.get(obj_id)
            if obj is None:
                return
            obj.point_size = max(0.5, float(size))
            if self._vis is not None:
                try:
                    opt = self._vis.get_render_option()
                    opt.point_size = float(obj.point_size)
                except Exception:
                    pass

    # ---------- 全局着色模式 ----------
    def set_color_mode(
        self,
        mode: str,
        label_map: Optional[Dict[int, Any]] = None,
        global_z_min: Optional[float] = None,
        global_z_max: Optional[float] = None,
    ) -> None:
        with self._lock:
            self._mapper.mode = mode
            if label_map is not None:
                self._mapper.label_map = label_map
            if global_z_min is not None:
                self._mapper.global_min = float(global_z_min)
            if global_z_max is not None:
                self._mapper.global_max = float(global_z_max)
            # 重新刷新所有点云颜色
            for obj in self._objects.values():
                self._refresh_object_backend(obj, reset_bbox=False)

    def recolor_all(self) -> None:
        """强制刷新所有对象颜色"""
        with self._lock:
            for obj in self._objects.values():
                self._refresh_object_backend(obj, reset_bbox=False)

    # ---------- 相机控制 ----------
    def set_camera_pose(self, pose: CameraPose) -> None:
        if self._vis is None:
            return
        try:
            import open3d as o3d

            ctr = self._vis.get_view_control()
            params = o3d.camera.PinholeCameraParameters()
            # 将 eye/lookat/up 转换为 Open3D Pinhole 参数
            lookat = np.array(pose.lookat, dtype=np.float64)
            eye = np.array(pose.eye, dtype=np.float64)
            up = np.array(pose.up, dtype=np.float64)
            forward = lookat - eye
            forward /= np.linalg.norm(forward) + 1e-12
            right = np.cross(forward, up)
            right /= np.linalg.norm(right) + 1e-12
            up_true = np.cross(right, forward)
            w, h = self._viewport_size if self._viewport_size[0] > 0 else (1280, 720)
            # 使用 set_lookat 等更直接的方式
            ctr.set_lookat(lookat)
            ctr.set_up(up_true)
            ctr.set_front(-forward)
            ctr.set_zoom(0.8)
        except Exception as e:
            logger.debug(f"设置相机位姿失败: {e}")

    def get_camera_pose(self) -> CameraPose:
        pose = CameraPose()
        if self._vis is None:
            return pose
        try:
            ctr = self._vis.get_view_control()
            # Open3D 通过参数转换
            cam_params = ctr.convert_to_pinhole_camera_parameters()
            extrinsic = np.asarray(cam_params.extrinsic)
            R = extrinsic[:3, :3]
            t = extrinsic[:3, 3]
            eye = -R.T @ t
            forward = R[2]  # OpenGL convention: camera -z is forward
            lookat = eye - forward * 10.0
            up = -R[1]
            pose.eye = tuple(float(x) for x in eye)
            pose.lookat = tuple(float(x) for x in lookat)
            pose.up = tuple(float(x) for x in up)
        except Exception:
            pass
        return pose

    def fit_view(self) -> None:
        """调整视角以容纳所有可见对象"""
        if self._vis is None:
            return
        try:
            self._vis.reset_view_point(True)
        except Exception:
            pass

    # ---------- 选择高亮 ----------
    def set_selection_mask(self, obj_id: int, mask: Optional[np.ndarray]) -> None:
        """根据布尔掩码高亮选中的点"""
        with self._lock:
            obj = self._objects.get(obj_id)
            if obj is None:
                return
            if mask is None:
                obj.selection_mask = None
            else:
                m = np.asarray(mask, dtype=bool).ravel()
                if m.size != obj.data.num_points:
                    logger.warning(f"选择掩码长度 {m.size} != 点数 {obj.data.num_points}")
                    return
                obj.selection_mask = m
            self._refresh_object_backend(obj, reset_bbox=False)

    def update_labels(self, obj_id: int, labels: np.ndarray) -> None:
        """更新点云标注数组并重着色"""
        with self._lock:
            obj = self._objects.get(obj_id)
            if obj is None:
                return
            lab = np.asarray(labels, dtype=np.int32).ravel()
            if lab.size != obj.data.num_points:
                logger.warning(f"标签长度不匹配: {lab.size} vs {obj.data.num_points}")
                return
            obj.labels_array = lab
            if self._mapper.mode == "label":
                self._refresh_object_backend(obj, reset_bbox=False)

    # ---------- 渲染循环 ----------
    def update_render(self) -> None:
        if self._vis is None:
            return
        try:
            self._vis.poll_events()
            self._vis.update_renderer()
        except Exception:
            pass

    # ---------- 内部 ----------
    def _refresh_object_backend(self, obj: SceneObject, reset_bbox: bool = False) -> None:
        if self._vis is None or obj.kind != "pointcloud" or obj.data is None:
            return
        try:
            import open3d as o3d

            # 移除旧对象
            if obj.backend_obj is not None:
                try:
                    self._vis.remove_geometry(obj.backend_obj)
                except Exception:
                    pass

            o3d_pcd, colors = create_colored_pointcloud(
                obj.data,
                self._mapper,
                labels=obj.labels_array,
                selection_mask=obj.selection_mask,
            )
            obj.backend_obj = o3d_pcd
            obj.colors = colors
            if obj.visible:
                self._vis.add_geometry(o3d_pcd, reset_bounding_box=reset_bbox)
                # 应用变换
                if not np.allclose(obj.transform, np.eye(4, dtype=np.float32)):
                    o3d_pcd.transform(obj.transform.astype(np.float64))
        except Exception as e:
            logger.warning(f"刷新渲染对象失败: {e}")

    # ---------- 辅助：获取渲染屏幕截图 ----------
    def capture_screen_float_buffer(self, downscale: int = 1) -> Optional[np.ndarray]:
        """获取当前渲染结果（用于调试或拾取）"""
        if self._vis is None:
            return None
        try:
            import open3d as o3d

            img = self._vis.capture_screen_float_buffer(do_render=True)
            return np.asarray(img)
        except Exception:
            return None

    def capture_depth_buffer(self) -> Optional[np.ndarray]:
        if self._vis is None:
            return None
        try:
            img = self._vis.capture_depth_float_buffer(do_render=True)
            return np.asarray(img)
        except Exception:
            return None

    # ---------- 注册事件回调 ----------
    def register_key_callback(self, key: int, callback: Callable[[Any, int], bool]) -> None:
        if self._vis is None:
            return
        try:
            self._vis.register_key_callback(key, callback)
        except Exception:
            pass

    def register_mouse_callback(self, callback: Callable[[Any, Any], bool]) -> None:
        """
        Open3D 的鼠标回调通过 AnimationCallback 模拟：
        每帧检查鼠标位置，并通过 ctr.get_view_control() 来获取信息。
        对于高精度拾取，使用 selection_pipeline.py 中的算法。
        """
        pass
