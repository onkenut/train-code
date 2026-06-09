"""
点云读取器 - 支持 PLY / LAS / LAZ / XYZ / PCD

策略：
- 优先使用 Open3D（快，且内置多格式支持）
- Open3D 无法读取时退回到专用库（laspy, plyfile, pypcd4）
- XYZ 使用纯 numpy 读取
"""

from __future__ import annotations

import hashlib
import logging
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import numpy as np

from pointvault.io.container import PointCloudData

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS: Tuple[str, ...] = (".ply", ".las", ".laz", ".xyz", ".pcd", ".xyzn", ".txt")


@dataclass
class PointCloudMetadata:
    """点云元数据（无需加载所有点即可获得）"""

    file_path: str
    file_format: str
    file_size_bytes: int
    file_hash: str
    num_points: int
    min_xyz: Tuple[float, float, float]
    max_xyz: Tuple[float, float, float]
    has_colors: bool
    has_normals: bool
    has_intensity: bool
    has_classes: bool


class PointCloudReader:
    """多格式点云读取器"""

    FORMAT_MAP: Dict[str, Callable[[Path], PointCloudData]] = {}

    def __init__(self, use_open3d: bool = True) -> None:
        self._use_open3d = use_open3d

    # ---------- 公共 API ----------
    def read(self, path: Path | str, max_points: Optional[int] = None) -> PointCloudData:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"点云文件不存在: {path}")

        ext = path.suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            raise ValueError(f"不支持的点云格式: {ext}")

        logger.info(f"读取点云: {path} (格式={ext})")

        data: Optional[PointCloudData] = None
        if self._use_open3d:
            try:
                data = self._read_open3d(path)
            except Exception as e:
                logger.warning(f"Open3D 读取失败，回退到专用库: {e}")

        if data is None:
            data = self._read_fallback(path, ext)

        # 可选下采样（用于快速预览）
        if max_points is not None and data.num_points > max_points:
            stride = max(1, data.num_points // int(max_points))
            data = data.select_indices(np.arange(0, data.num_points, stride))

        return data

    def get_metadata(self, path: Path | str) -> PointCloudMetadata:
        """获取元数据，尽量不加载全部点"""
        path = Path(path)
        ext = path.suffix.lower()
        size = path.stat().st_size
        sha = self._sha256_of_file(path)

        # 快速路径：读取点数 + 快速范围估算（读前 1 万和后 1 万点）
        try:
            quick = self.read(path, max_points=50000)
            lo, hi = quick.bounds()
            num_pts = self._fast_count_points(path, ext, size)
            return PointCloudMetadata(
                file_path=str(path.resolve()),
                file_format=ext.lstrip("."),
                file_size_bytes=size,
                file_hash=sha,
                num_points=num_pts if num_pts > 0 else quick.num_points,
                min_xyz=(float(lo[0]), float(lo[1]), float(lo[2])),
                max_xyz=(float(hi[0]), float(hi[1]), float(hi[2])),
                has_colors=quick.has_colors(),
                has_normals=quick.has_normals(),
                has_intensity=quick.has_intensity(),
                has_classes=quick.has_labels(),
            )
        except Exception as e:
            logger.warning(f"快速元数据读取失败，执行完整读取: {e}")
            full = self.read(path)
            lo, hi = full.bounds()
            return PointCloudMetadata(
                file_path=str(path.resolve()),
                file_format=ext.lstrip("."),
                file_size_bytes=size,
                file_hash=sha,
                num_points=full.num_points,
                min_xyz=(float(lo[0]), float(lo[1]), float(lo[2])),
                max_xyz=(float(hi[0]), float(hi[1]), float(hi[2])),
                has_colors=full.has_colors(),
                has_normals=full.has_normals(),
                has_intensity=full.has_intensity(),
                has_classes=full.has_labels(),
            )

    # ---------- 内部实现 ----------
    @staticmethod
    def _sha256_of_file(path: Path, chunk: int = 1 << 20) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for blk in iter(lambda: f.read(chunk), b""):
                h.update(blk)
        return h.hexdigest()

    @staticmethod
    def _fast_count_points(path: Path, ext: str, file_size: int) -> int:
        """尽量快速估算点数"""
        try:
            if ext in (".las", ".laz"):
                try:
                    import laspy
                    with laspy.open(path) as f:
                        return int(f.header.point_count)
                except Exception:
                    pass
            if ext == ".pcd":
                return PointCloudReader._pcd_count_points(path)
            if ext == ".ply":
                return PointCloudReader._ply_count_points(path)
            # XYZ / TXT：按行数估算
            if ext in (".xyz", ".txt", ".xyzn"):
                avg_line = 60  # 字节
                return max(0, file_size // avg_line)
        except Exception:
            pass
        return 0

    @staticmethod
    def _pcd_count_points(path: Path) -> int:
        with open(path, "rb") as f:
            for line in f:
                s = line.decode("ascii", errors="ignore").strip()
                if s.upper().startswith("POINTS"):
                    try:
                        return int(s.split()[1])
                    except (ValueError, IndexError):
                        return 0
                if s == "DATA binary" or s == "DATA binary_compressed":
                    break
        return 0

    @staticmethod
    def _ply_count_points(path: Path) -> int:
        with open(path, "rb") as f:
            in_vertex = False
            for raw in f:
                line = raw.decode("ascii", errors="ignore").strip()
                if line.startswith("element vertex"):
                    try:
                        return int(line.split()[-1])
                    except ValueError:
                        pass
                if line == "end_header":
                    break
        return 0

    # ---------- Open3D ----------
    @staticmethod
    def _read_open3d(path: Path) -> Optional[PointCloudData]:
        try:
            import open3d as o3d
        except ImportError:
            return None

        pcd = o3d.io.read_point_cloud(str(path))
        if pcd.is_empty():
            return None
        data = PointCloudData()
        data.points = np.asarray(pcd.points, dtype=np.float32).copy()
        if pcd.has_colors():
            data.colors = np.asarray(pcd.colors, dtype=np.float32).copy()
        if pcd.has_normals():
            data.normals = np.asarray(pcd.normals, dtype=np.float32).copy()
        return data

    # ---------- Fallback 专用库 ----------
    def _read_fallback(self, path: Path, ext: str) -> PointCloudData:
        if ext in (".las", ".laz"):
            return self._read_las(path)
        if ext == ".ply":
            return self._read_ply(path)
        if ext == ".pcd":
            return self._read_pcd(path)
        if ext in (".xyz", ".txt", ".xyzn"):
            return self._read_xyz(path, ext)
        raise ValueError(f"不支持的格式: {ext}")

    @staticmethod
    def _read_las(path: Path) -> PointCloudData:
        import laspy

        las = laspy.read(path)
        scale = np.array([las.header.x_scale, las.header.y_scale, las.header.z_scale], dtype=np.float64)
        offset = np.array([las.header.x_offset, las.header.y_offset, las.header.z_offset], dtype=np.float64)
        xyz = (np.stack([las.X, las.Y, las.Z], axis=1).astype(np.float64) * scale + offset).astype(np.float32)

        data = PointCloudData(points=xyz)

        # 颜色
        if "red" in las.point_format.extra_dimension_names or hasattr(las, "red"):
            try:
                r = np.asarray(las.red)
                g = np.asarray(las.green)
                b = np.asarray(las.blue)
                # 16bit -> float
                maxv = max(1.0, float(r.max()))
                if maxv > 255:
                    maxv = 65535.0
                data.colors = np.stack([r / maxv, g / maxv, b / maxv], axis=1).astype(np.float32)
            except Exception:
                pass

        # 强度
        if hasattr(las, "intensity"):
            try:
                inten = np.asarray(las.intensity).astype(np.float32)
                if inten.max() > 1.0:
                    inten /= 255.0
                data.intensity = inten
            except Exception:
                pass

        # 分类
        if hasattr(las, "classification"):
            try:
                data.labels = np.asarray(las.classification).astype(np.int32)
            except Exception:
                pass

        return data

    @staticmethod
    def _read_ply(path: Path) -> PointCloudData:
        from plyfile import PlyData, PlyElement

        ply = PlyData.read(str(path))
        # 找到 vertex 元素
        vert: Optional[PlyElement] = None
        for e in ply.elements:
            if e.name == "vertex":
                vert = e
                break
        if vert is None:
            raise RuntimeError("PLY 文件不包含 vertex 元素")

        n = len(vert)
        pts = np.empty((n, 3), dtype=np.float32)
        pts[:, 0] = vert["x"]
        pts[:, 1] = vert["y"]
        pts[:, 2] = vert["z"]

        data = PointCloudData(points=pts)
        props = [p.name for p in vert.properties]

        if all(c in props for c in ("red", "green", "blue")):
            r = vert["red"].astype(np.float32)
            g = vert["green"].astype(np.float32)
            b = vert["blue"].astype(np.float32)
            mx = max(1.0, float(r.max()))
            if mx > 1.0:
                mx = 255.0
            data.colors = np.stack([r / mx, g / mx, b / mx], axis=1)

        if all(c in props for c in ("nx", "ny", "nz")):
            data.normals = np.stack(
                [vert["nx"].astype(np.float32), vert["ny"].astype(np.float32), vert["nz"].astype(np.float32)],
                axis=1,
            )

        if "intensity" in props:
            inten = vert["intensity"].astype(np.float32)
            if inten.max() > 1.0:
                inten /= 255.0
            data.intensity = inten

        if "label" in props or "class" in props or "semantic" in props:
            pname = "label" if "label" in props else ("class" if "class" in props else "semantic")
            data.labels = vert[pname].astype(np.int32)

        return data

    @staticmethod
    def _read_pcd(path: Path) -> PointCloudData:
        try:
            import open3d as o3d
            pcd = o3d.t.io.read_point_cloud(str(path))
            data = PointCloudData()
            data.points = pcd.point.positions.numpy().astype(np.float32)
            if "colors" in pcd.point:
                c = pcd.point.colors.numpy().astype(np.float32)
                if c.max() > 1.0:
                    c /= 255.0
                data.colors = c
            if "normals" in pcd.point:
                data.normals = pcd.point.normals.numpy().astype(np.float32)
            if "intensity" in pcd.point:
                inten = pcd.point.intensity.numpy().astype(np.float32).reshape(-1)
                if inten.max() > 1.0:
                    inten /= 255.0
                data.intensity = inten
            return data
        except ImportError:
            # 纯 numpy 读 PCD (仅 ASCII)
            return PointCloudReader._read_pcd_ascii(path)

    @staticmethod
    def _read_pcd_ascii(path: Path) -> PointCloudData:
        header = {}
        with open(path, "r", encoding="ascii", errors="ignore") as f:
            while True:
                line = f.readline().strip()
                if not line:
                    continue
                if line.startswith("#"):
                    continue
                parts = line.split()
                key = parts[0]
                header[key] = parts[1:]
                if key == "DATA":
                    break

            n = int(header["POINTS"][0])
            fields = header["FIELDS"]
            sizes = [int(s) for s in header["SIZE"]]
            counts = [int(s) for s in header["COUNT"]]
            types = header["TYPE"]

            dtype_map = {"I": "i", "U": "u", "F": "f"}
            dt = []
            for i in range(len(fields)):
                name = fields[i]
                t = dtype_map[types[i]] + str(sizes[i])
                c = counts[i]
                if c == 1:
                    dt.append((name, t))
                else:
                    dt.append((name, t, (c,)))
            dtype = np.dtype(dt)
            raw = np.fromfile(f, dtype=dtype, count=n)

        xyz = np.stack([raw["x"].astype(np.float32), raw["y"].astype(np.float32), raw["z"].astype(np.float32)], axis=1)
        data = PointCloudData(points=xyz)
        if all(c in fields for c in ("rgb",)):
            rgb = raw["rgb"].astype(np.uint32).view(np.uint8)
            # xyzrgb PCD: rgb 是 packed float
            packed = np.frombuffer(raw["rgb"].tobytes(), dtype=np.uint8).reshape(-1, 4)
            data.colors = np.stack([packed[:, 2] / 255.0, packed[:, 1] / 255.0, packed[:, 0] / 255.0], axis=1).astype(np.float32)
        return data

    @staticmethod
    def _read_xyz(path: Path, ext: str) -> PointCloudData:
        # 首行探测列数
        with open(path, "r", errors="ignore") as f:
            first = None
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                first = s.split()
                break
        if first is None:
            return PointCloudData()

        ncols = len(first)
        cols_expected = min(ncols, 9)  # x y z nx ny nz r g b
        usecols = list(range(cols_expected))

        try:
            arr = np.loadtxt(path, dtype=np.float32, comments="#", usecols=usecols, ndmin=2)
        except ValueError:
            arr = np.genfromtxt(path, dtype=np.float32, comments="#", usecols=usecols, invalid_raise=False)
            arr = arr[~np.isnan(arr).any(axis=1)]

        data = PointCloudData(points=arr[:, :3].astype(np.float32))
        # 法向
        if arr.shape[1] >= 6 and ext == ".xyzn":
            data.normals = arr[:, 3:6].astype(np.float32)
            if arr.shape[1] >= 9:
                c = arr[:, 6:9].astype(np.float32)
                if c.max() > 1.0:
                    c /= 255.0
                data.colors = c
        elif arr.shape[1] >= 6:
            # 尝试判断后三列是颜色还是法向（颜色范围 0-255，法向 -1~1）
            tail = arr[:, 3:6]
            is_color = (tail.min() >= 0) and (tail.max() > 2)
            if is_color:
                c = tail.astype(np.float32)
                if c.max() > 1.0:
                    c /= 255.0
                data.colors = c
            else:
                data.normals = tail.astype(np.float32)
            if arr.shape[1] >= 9:
                c = arr[:, 6:9].astype(np.float32)
                if c.max() > 1.0:
                    c /= 255.0
                data.colors = c
        return data


# ---------- 便捷函数 ----------
_reader_singleton: Optional[PointCloudReader] = None


def _reader() -> PointCloudReader:
    global _reader_singleton
    if _reader_singleton is None:
        _reader_singleton = PointCloudReader()
    return _reader_singleton


def read_pointcloud(path: Path | str, max_points: Optional[int] = None) -> PointCloudData:
    return _reader().read(path, max_points=max_points)


def get_pointcloud_metadata(path: Path | str) -> PointCloudMetadata:
    return _reader().get_metadata(path)
