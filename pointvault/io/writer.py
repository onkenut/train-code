"""
点云写入器 - 支持 PLY / LAS / PCD / XYZ
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from pointvault.io.container import PointCloudData

logger = logging.getLogger(__name__)


class PointCloudWriter:
    """点云写入器"""

    def write(
        self,
        data: PointCloudData,
        path: Path | str,
        format: Optional[str] = None,
        write_binary: bool = True,
    ) -> Path:
        path = Path(path)
        ext = (format or path.suffix).lower()
        if not ext.startswith("."):
            ext = "." + ext
        path = path.with_suffix(ext)
        path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"写入点云: {path} 格式={ext} n={data.num_points}")

        if ext == ".ply":
            self._write_ply(data, path, write_binary)
        elif ext in (".las", ".laz"):
            self._write_las(data, path)
        elif ext == ".pcd":
            self._write_pcd(data, path, write_binary)
        elif ext in (".xyz", ".txt", ".xyzn"):
            self._write_xyz(data, path, ext)
        else:
            raise ValueError(f"不支持的导出格式: {ext}")
        return path

    # ---- PLY ----
    @staticmethod
    def _write_ply(data: PointCloudData, path: Path, binary: bool) -> None:
        try:
            import open3d as o3d
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(data.points.astype(np.float64))
            if data.has_colors():
                pcd.colors = o3d.utility.Vector3dVector(data.colors.astype(np.float64))
            if data.has_normals():
                pcd.normals = o3d.utility.Vector3dVector(data.normals.astype(np.float64))
            o3d.io.write_point_cloud(str(path), pcd, write_ascii=not binary)
            return
        except ImportError:
            pass

        from plyfile import PlyData, PlyElement

        props = [("x", "f4"), ("y", "f4"), ("z", "f4")]
        arrays = [data.points[:, 0], data.points[:, 1], data.points[:, 2]]

        if data.has_normals():
            props += [("nx", "f4"), ("ny", "f4"), ("nz", "f4")]
            arrays += [data.normals[:, 0], data.normals[:, 1], data.normals[:, 2]]

        if data.has_colors():
            c = (np.clip(data.colors, 0, 1) * 255).astype(np.uint8)
            props += [("red", "u1"), ("green", "u1"), ("blue", "u1")]
            arrays += [c[:, 0], c[:, 1], c[:, 2]]

        if data.has_intensity():
            inten = (np.clip(data.intensity, 0, 1) * 255).astype(np.uint8)
            props.append(("intensity", "u1"))
            arrays.append(inten)

        if data.has_labels():
            props.append(("label", "i4"))
            arrays.append(data.labels.astype(np.int32))

        n = data.num_points
        vertex = np.empty(n, dtype=np.dtype(props))
        for (name, _), arr in zip(props, arrays):
            vertex[name] = arr

        el = PlyElement.describe(vertex, "vertex", comments=["PointVault generated"])
        PlyData([el], text=not binary).write(str(path))

    # ---- LAS ----
    @staticmethod
    def _write_las(data: PointCloudData, path: Path) -> None:
        import laspy

        header = laspy.LasHeader(point_format=7, version="1.4")
        pts = data.points.astype(np.float64)
        mins = pts.min(axis=0)
        maxs = pts.max(axis=0)
        header.mins = tuple(mins)
        header.maxs = tuple(maxs)
        scale = 1e-4
        header.scales = (scale, scale, scale)
        header.offsets = tuple(mins - 1)
        las = laspy.LasData(header)
        X = np.round((pts[:, 0] - header.offsets[0]) / header.scales[0]).astype(np.int32)
        Y = np.round((pts[:, 1] - header.offsets[1]) / header.scales[1]).astype(np.int32)
        Z = np.round((pts[:, 2] - header.offsets[2]) / header.scales[2]).astype(np.int32)
        las.X, las.Y, las.Z = X, Y, Z

        if data.has_colors():
            c = (np.clip(data.colors, 0, 1) * 65535).astype(np.uint16)
            las.red = c[:, 0]
            las.green = c[:, 1]
            las.blue = c[:, 2]

        if data.has_intensity():
            las.intensity = (np.clip(data.intensity, 0, 1) * 65535).astype(np.uint16)

        if data.has_labels():
            # classification 为 uint8，超过 255 的标签映射到 extended_scalars
            safe_labels = np.clip(data.labels, 0, 255).astype(np.uint8)
            las.classification = safe_labels
            if data.labels.max() >= 256:
                las.add_extra_dim(laspy.ExtraBytesParams(name="label_id", type=np.int32))
                las["label_id"] = data.labels.astype(np.int32)

        las.write(str(path))

    # ---- PCD ----
    @staticmethod
    def _write_pcd(data: PointCloudData, path: Path, binary: bool) -> None:
        try:
            import open3d as o3d
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(data.points.astype(np.float64))
            if data.has_colors():
                pcd.colors = o3d.utility.Vector3dVector(data.colors.astype(np.float64))
            if data.has_normals():
                pcd.normals = o3d.utility.Vector3dVector(data.normals.astype(np.float64))
            o3d.io.write_point_cloud(str(path), pcd, write_ascii=not binary)
            return
        except ImportError:
            pass

        # 手写 ASCII PCD
        pts = data.points
        n = pts.shape[0]
        fields = "x y z"
        has_rgb = data.has_colors()
        if has_rgb:
            fields += " rgb"
        has_normals = data.has_normals()
        if has_normals:
            fields += " nx ny nz"

        lines = [
            "# .PCD v0.7 - Point Cloud Data file format",
            "VERSION 0.7",
            f"FIELDS {fields}",
            f"SIZE {'4' * len(fields.split())}",
            f"TYPE {'F' * len(fields.split())}",
            f"COUNT {'1' * len(fields.split())}",
            f"WIDTH {n}",
            "HEIGHT 1",
            f"VIEWPOINT 0 0 0 1 0 0 0",
            f"POINTS {n}",
            "DATA ascii",
        ]
        with open(path, "w", encoding="ascii") as f:
            f.write("\n".join(lines) + "\n")
            rows = [pts]
            if has_rgb:
                c = (np.clip(data.colors, 0, 1) * 255).astype(np.uint32)
                packed = (c[:, 2].astype(np.uint32) << 16) | (c[:, 1] << 8) | c[:, 0]
                packed_float = packed.view(np.float32).reshape(-1, 1)
                rows.append(packed_float)
            if has_normals:
                rows.append(data.normals)
            arr = np.hstack(rows)
            np.savetxt(f, arr, fmt="%.6f")

    # ---- XYZ ----
    @staticmethod
    def _write_xyz(data: PointCloudData, path: Path, ext: str) -> None:
        cols = [data.points]
        if ext == ".xyzn" and data.has_normals():
            cols.append(data.normals)
            if data.has_colors():
                cols.append((np.clip(data.colors, 0, 1) * 255).astype(np.uint8).astype(np.float32))
        else:
            if data.has_normals():
                cols.append(data.normals)
            if data.has_colors():
                cols.append((np.clip(data.colors, 0, 1) * 255).astype(np.uint8).astype(np.float32))
        arr = np.hstack(cols)
        with open(path, "w", encoding="ascii") as f:
            np.savetxt(f, arr, fmt="%.6f")


# ---------- 便捷函数 ----------
_writer_singleton: Optional[PointCloudWriter] = None


def _writer() -> PointCloudWriter:
    global _writer_singleton
    if _writer_singleton is None:
        _writer_singleton = PointCloudWriter()
    return _writer_singleton


def write_pointcloud(
    data: PointCloudData,
    path: Path | str,
    format: Optional[str] = None,
    write_binary: bool = True,
) -> Path:
    return _writer().write(data, path, format=format, write_binary=write_binary)
