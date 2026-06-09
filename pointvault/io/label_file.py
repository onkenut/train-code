"""
标注文件 (.labels) 处理器

二进制格式设计（与点云等长的 int32 数组）：
- 每个点一个 32 位有符号整数，代表语义标签 ID
- label_id = 0 表示未标注
- 标注文件与点云文件 1:1 对应，总字节数 = 4 * num_points

出于安全和校验考虑，写入时在文件尾部附加一个简单的 footer (可选)：
    [ 4 字节 magic: 0x50564C42 ('PVLB') ]
    [ 4 字节 num_points 校验 ]
    [ 4 字节 CRC32 ]

但读取时如果 footer 不存在也能正常解析（兼容纯 int32 数组）。
"""

from __future__ import annotations

import logging
import mmap
import os
import struct
import zlib
from collections import Counter
from pathlib import Path
from threading import Lock
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from pointvault.constants import LABEL_FILE_EXT, UNLABELED_ID

logger = logging.getLogger(__name__)

_FOOTER_MAGIC = 0x50564C42  # 'PVLB'
_FOOTER_SIZE = 12  # magic(4) + num_points(4) + crc32(4)

# 对外公开的常量（供测试与文档一致性检查）
LABEL_FILE_MAGIC: int = _FOOTER_MAGIC
LABEL_FILE_FOOTER_SIZE: int = _FOOTER_SIZE
PVLB_MAGIC_BYTES: bytes = b'PVLB'


class LabelFileHandler:
    """
    标注文件处理器

    对于超大型点云（>1M 点），使用 mmap 进行部分读写，避免一次性加载。
    """

    def __init__(self) -> None:
        self._locks: Dict[str, Lock] = {}
        self._global_lock = Lock()

    def _get_lock(self, path: Path) -> Lock:
        with self._global_lock:
            key = str(path.resolve())
            if key not in self._locks:
                self._locks[key] = Lock()
            return self._locks[key]

    # ---------- 创建 ----------
    def create_empty(self, path: Path | str, num_points: int) -> Path:
        path = Path(path).with_suffix(LABEL_FILE_EXT)
        path.parent.mkdir(parents=True, exist_ok=True)
        # 直接写 N * 4 字节零 + footer
        zeros = np.zeros(num_points, dtype=np.int32)
        self._write_internal(path, zeros)
        return path

    # ---------- 读 ----------
    def read_all(self, path: Path | str) -> np.ndarray:
        path = self._resolve(path)
        with self._get_lock(path):
            return self._read_internal(path)

    def read_range(self, path: Path | str, start: int, length: int) -> np.ndarray:
        path = self._resolve(path)
        with self._get_lock(path):
            total = self._num_points_from_file(path)
            end = min(start + length, total)
            if start >= total:
                return np.empty(0, dtype=np.int32)
            count = end - start
            with open(path, "rb") as f:
                f.seek(start * 4)
                raw = f.read(count * 4)
            return np.frombuffer(raw, dtype=np.int32).copy()

    # ---------- 写 ----------
    def write_all(self, path: Path | str, labels: np.ndarray) -> None:
        path = self._resolve(path)
        labels = np.asarray(labels, dtype=np.int32).ravel()
        with self._get_lock(path):
            self._write_internal(path, labels)

    def update_indices(
        self,
        path: Path | str,
        indices: np.ndarray,
        new_label: int,
        total_points: int,
    ) -> int:
        """按给定索引更新标签，返回被修改的点数"""
        path = self._resolve(path)
        indices = np.asarray(indices, dtype=np.int64).ravel()
        if indices.size == 0:
            return 0
        indices = np.clip(indices, 0, total_points - 1)
        with self._get_lock(path):
            data = self._read_internal(path)
            if data.size != total_points:
                logger.warning(
                    f"标注文件长度 {data.size} 与期望 {total_points} 不一致，将重置"
                )
                data = np.zeros(total_points, dtype=np.int32)
            data[indices] = int(new_label)
            self._write_internal(path, data)
        return int(indices.size)

    def update_mask(
        self,
        path: Path | str,
        mask: np.ndarray,
        new_label: int,
    ) -> int:
        """按布尔掩码更新标签，返回被修改的点数"""
        path = self._resolve(path)
        mask = np.asarray(mask, dtype=bool).ravel()
        if not mask.any():
            return 0
        with self._get_lock(path):
            data = self._read_internal(path)
            if data.size != mask.size:
                logger.warning(
                    f"标注文件长度 {data.size} 与掩码 {mask.size} 不一致，将截断/填充"
                )
                new_data = np.zeros(mask.size, dtype=np.int32)
                n = min(data.size, mask.size)
                new_data[:n] = data[:n]
                data = new_data
            data[mask] = int(new_label)
            self._write_internal(path, data)
        return int(mask.sum())

    # ---------- 工具 ----------
    def histogram(self, path: Path | str, chunk_size: int = 2_000_000) -> Dict[int, int]:
        """计算标签分布（分块处理，内存友好）"""
        path = self._resolve(path)
        counter: Counter = Counter()
        with self._get_lock(path):
            total = self._num_points_from_file(path)
            if total == 0:
                return {UNLABELED_ID: 0}
            with open(path, "rb") as f:
                for start in range(0, total, chunk_size):
                    end = min(start + chunk_size, total)
                    count = end - start
                    raw = f.read(count * 4)
                    chunk = np.frombuffer(raw, dtype=np.int32)
                    ids, cnts = np.unique(chunk, return_counts=True)
                    for i, c in zip(ids.tolist(), cnts.tolist()):
                        counter[int(i)] += int(c)
        return dict(counter)

    def snapshot(self, path: Path | str, snapshot_path: Path | str) -> Path:
        """创建标注文件的快照副本"""
        path = self._resolve(path)
        snapshot_path = Path(snapshot_path)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_lock(path):
            import shutil
            shutil.copy2(path, snapshot_path)
        return snapshot_path

    def restore_snapshot(self, snapshot_path: Path | str, target_path: Path | str) -> None:
        """从快照恢复"""
        import shutil
        src = Path(snapshot_path)
        dst = self._resolve(target_path)
        with self._get_lock(dst):
            shutil.copy2(src, dst)

    # ---------- 内部 ----------
    @staticmethod
    def _resolve(path: Path | str) -> Path:
        p = Path(path)
        if p.suffix.lower() != LABEL_FILE_EXT:
            p = p.with_suffix(LABEL_FILE_EXT)
        return p

    @staticmethod
    def _num_points_from_file(path: Path) -> int:
        size = path.stat().st_size
        # 尝试解析 footer
        if size >= _FOOTER_SIZE:
            try:
                with open(path, "rb") as f:
                    f.seek(-_FOOTER_SIZE, os.SEEK_END)
                    footer = f.read(_FOOTER_SIZE)
                    magic, n, _ = struct.unpack("<III", footer)
                    if magic == _FOOTER_MAGIC and n * 4 <= size - _FOOTER_SIZE:
                        return int(n)
            except Exception:
                pass
        return size // 4

    @staticmethod
    def _read_internal(path: Path) -> np.ndarray:
        size = path.stat().st_size
        if size == 0:
            return np.empty(0, dtype=np.int32)
        # 尝试读取 footer
        total = size
        footer_bytes = 0
        if size >= _FOOTER_SIZE:
            try:
                with open(path, "rb") as f:
                    f.seek(-_FOOTER_SIZE, os.SEEK_END)
                    footer = f.read(_FOOTER_SIZE)
                    magic, n, _ = struct.unpack("<III", footer)
                    if magic == _FOOTER_MAGIC and n * 4 <= size - _FOOTER_SIZE:
                        total = n * 4
                        footer_bytes = _FOOTER_SIZE
            except Exception:
                pass
        # mmap 读取（内存高效）
        if total > 4 * 1_000_000:
            with open(path, "rb") as f:
                mm = mmap.mmap(f.fileno(), length=total, access=mmap.ACCESS_READ)
                try:
                    arr = np.frombuffer(mm, dtype=np.int32).copy()
                finally:
                    mm.close()
            return arr
        with open(path, "rb") as f:
            raw = f.read(total)
        return np.frombuffer(raw, dtype=np.int32).copy()

    @staticmethod
    def _write_internal(path: Path, data: np.ndarray) -> None:
        data = np.asarray(data, dtype=np.int32).ravel()
        raw = data.tobytes()
        crc = zlib.crc32(raw) & 0xFFFFFFFF
        footer = struct.pack("<III", _FOOTER_MAGIC, int(data.size), crc)
        # 先写到临时文件，再原子替换
        tmp = path.with_suffix(LABEL_FILE_EXT + ".tmp")
        with open(tmp, "wb") as f:
            f.write(raw)
            f.write(footer)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        os.replace(tmp, path)


# ---------- 便捷函数 ----------
_handler_singleton: Optional[LabelFileHandler] = None


def _handler() -> LabelFileHandler:
    global _handler_singleton
    if _handler_singleton is None:
        _handler_singleton = LabelFileHandler()
    return _handler_singleton


def create_empty_label_file(path: Path | str, num_points: int) -> Path:
    return _handler().create_empty(path, num_points)


def read_labels(path: Path | str) -> np.ndarray:
    return _handler().read_all(path)


def write_labels(path: Path | str, labels: np.ndarray) -> None:
    _handler().write_all(path, labels)


def update_labels_in_range(
    path: Path | str,
    indices: np.ndarray,
    new_label: int,
    total_points: int,
) -> int:
    return _handler().update_indices(path, indices, new_label, total_points)


def compute_label_histogram(
    path: Path | str, chunk_size: int = 2_000_000
) -> Dict[int, int]:
    return _handler().histogram(path, chunk_size=chunk_size)
