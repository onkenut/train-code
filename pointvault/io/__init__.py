"""
点云 I/O 包 - 支持 PLY, LAS/LAZ, XYZ, PCD 格式
及自定义 .labels 二进制标注文件
"""

from pointvault.io.reader import (
    PointCloudReader,
    read_pointcloud,
    get_pointcloud_metadata,
    SUPPORTED_FORMATS,
)
from pointvault.io.writer import PointCloudWriter, write_pointcloud
from pointvault.io.label_file import (
    LabelFileHandler,
    create_empty_label_file,
    read_labels,
    write_labels,
    update_labels_in_range,
    compute_label_histogram,
)

__all__ = [
    "PointCloudReader",
    "read_pointcloud",
    "get_pointcloud_metadata",
    "SUPPORTED_FORMATS",
    "PointCloudWriter",
    "write_pointcloud",
    "LabelFileHandler",
    "create_empty_label_file",
    "read_labels",
    "write_labels",
    "update_labels_in_range",
    "compute_label_histogram",
]
