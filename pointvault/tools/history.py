"""
撤销/重做命令栈

设计采用 Command 模式 + 快照文件折中：
- 对标注修改（仅影响 .labels 文件）：记录变更索引 + 原值 → 轻量可逆
- 对点云修改（下采样、去噪等）：保存修改前的整云快照文件（大文件）
- 命令栈默认最大 50 条；超过后自动清理最早的快照以释放磁盘
"""

from __future__ import annotations

import abc
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from pointvault.constants import OperationType
from pointvault.db.repositories import RepositoryFactory


# ============================================================
# Command 抽象
# ============================================================
class Command(abc.ABC):
    """可撤销命令基类"""

    op_type: str = OperationType.ANNOTATE_LABELS
    description: str = ""

    @abc.abstractmethod
    def do(self) -> None:
        """执行（首次执行）"""

    @abc.abstractmethod
    def undo(self) -> None:
        """撤销"""

    @abc.abstractmethod
    def redo(self) -> None:
        """重做（默认等同于 do，但某些情况可走快速路径）"""

    def dispose(self) -> None:
        """清理临时资源（如快照文件）"""


# ============================================================
# 标注编辑命令
# ============================================================
@dataclass
class AnnotationEditCommand(Command):
    """
    标注编辑 - 修改标注文件中部分索引的标签值

    可逆方式：保存被修改的点索引 + 修改前的原标签值
    """

    op_type: str = OperationType.ANNOTATE_LABELS
    description: str = "修改标注"

    label_file_path: str = ""
    total_points: int = 0
    # 本次修改
    modified_indices: np.ndarray = field(
        default_factory=lambda: np.empty(0, dtype=np.int64)
    )
    old_labels: np.ndarray = field(
        default_factory=lambda: np.empty(0, dtype=np.int32)
    )
    new_label: int = 0
    # 回调：完成后刷新渲染
    post_change_callback: Optional[Callable[[], None]] = None
    # 历史记录信息
    pointcloud_id: int = 0
    labelset_id: int = 0

    # 内部：临时保存快照路径
    _snapshot_before: Optional[str] = None

    def do(self) -> None:
        from pointvault.io.label_file import _handler

        if self.modified_indices.size == 0:
            return
        # 先创建快照（快速复制）
        snap = Path(self.label_file_path).with_suffix(
            ".labels.snap_" + str(os.getpid()) + "_" + str(threading.get_ident())
        )
        _handler().snapshot(self.label_file_path, snap)
        self._snapshot_before = str(snap)

        # 更新到文件
        indices = np.clip(
            np.asarray(self.modified_indices, dtype=np.int64).ravel(),
            0,
            self.total_points - 1,
        )
        # 先记录原标签
        if self.old_labels.size == 0 and indices.size > 0:
            all_labels = _handler().read_all(self.label_file_path)
            self.old_labels = all_labels[indices].copy()
        _handler().update_indices(
            self.label_file_path, indices, self.new_label, self.total_points
        )
        self._update_db_stats()
        if self.post_change_callback is not None:
            self.post_change_callback()

    def undo(self) -> None:
        from pointvault.io.label_file import _handler

        if self._snapshot_before and Path(self._snapshot_before).exists():
            _handler().restore_snapshot(self._snapshot_before, self.label_file_path)
        elif self.old_labels.size > 0:
            indices = np.clip(
                np.asarray(self.modified_indices, dtype=np.int64).ravel(),
                0,
                self.total_points - 1,
            )
            for i, old in zip(indices, self.old_labels):
                _handler().update_indices(
                    self.label_file_path, np.array([i]), int(old), self.total_points
                )
        self._update_db_stats()
        if self.post_change_callback is not None:
            self.post_change_callback()

    def redo(self) -> None:
        self.do()

    def dispose(self) -> None:
        if self._snapshot_before:
            try:
                Path(self._snapshot_before).unlink(missing_ok=True)
            except OSError:
                pass

    # ---------- 工具 ----------
    def _update_db_stats(self) -> None:
        from pointvault.io.label_file import compute_label_histogram

        if self.pointcloud_id == 0 or self.labelset_id == 0:
            return
        try:
            counts = compute_label_histogram(self.label_file_path)
            annot_repo = RepositoryFactory.annotations()
            annot = annot_repo.get_for_pointcloud(
                self.pointcloud_id, self.labelset_id
            )
            if annot is not None:
                annot_repo.update_stats(annot.id, counts)
        except Exception:
            pass


# ============================================================
# 点云几何编辑命令
# ============================================================
@dataclass
class PointCloudEditCommand(Command):
    """
    点云几何编辑 - 下采样、去噪等

    通过快照文件保存操作前后的点云状态以支持撤销。
    """

    op_type: str = OperationType.VOXEL_DOWNSAMPLE
    description: str = "编辑点云"

    pointcloud_id: int = 0
    project_id: int = 0

    # 操作前后的快照文件
    snapshot_before: Optional[str] = None
    snapshot_after: Optional[str] = None

    # 处理函数（首次执行时调用）
    process_fn: Optional[Callable[[], Any]] = None
    apply_after_fn: Optional[Callable[[Path], None]] = None
    apply_before_fn: Optional[Callable[[Path], None]] = None

    _first_executed: bool = False

    def do(self) -> None:
        if self.process_fn is not None and not self._first_executed:
            self.process_fn()
            self._first_executed = True
        else:
            if self.snapshot_after and Path(self.snapshot_after).exists():
                if self.apply_after_fn is not None:
                    self.apply_after_fn(Path(self.snapshot_after))
        # 写数据库
        try:
            hist_repo = RepositoryFactory.history()
            hist_repo.add(
                project_id=self.project_id,
                op_type=self.op_type,
                description=self.description,
                pointcloud_ids=[self.pointcloud_id],
                snapshot_before=self.snapshot_before,
                snapshot_after=self.snapshot_after,
            )
        except Exception:
            pass

    def undo(self) -> None:
        if self.snapshot_before and Path(self.snapshot_before).exists():
            if self.apply_before_fn is not None:
                self.apply_before_fn(Path(self.snapshot_before))

    def redo(self) -> None:
        if self.snapshot_after and Path(self.snapshot_after).exists():
            if self.apply_after_fn is not None:
                self.apply_after_fn(Path(self.snapshot_after))

    def dispose(self) -> None:
        for fp in (self.snapshot_before, self.snapshot_after):
            if fp:
                try:
                    Path(fp).unlink(missing_ok=True)
                except OSError:
                    pass


# ============================================================
# 命令栈
# ============================================================
class CommandHistory:
    """
    撤销/重做命令栈

    - _undo_stack: 已执行、可撤销的命令列表（最近的在末尾）
    - _redo_stack: 已撤销、可重做的命令列表（最早的在开头）
    """

    def __init__(self, max_commands: int = 50, snapshots_dir: Optional[Path | str] = None) -> None:
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self._max = max(1, int(max_commands))
        self._snapshots_dir = Path(snapshots_dir) if snapshots_dir else None
        if self._snapshots_dir:
            self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # ---------- 属性 ----------
    @property
    def can_undo(self) -> bool:
        with self._lock:
            return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        with self._lock:
            return len(self._redo_stack) > 0

    @property
    def undo_stack_size(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_stack_size(self) -> int:
        return len(self._redo_stack)

    def peek_undo(self) -> Optional[Command]:
        with self._lock:
            return self._undo_stack[-1] if self._undo_stack else None

    def peek_redo(self) -> Optional[Command]:
        with self._lock:
            return self._redo_stack[0] if self._redo_stack else None

    # ---------- 操作 ----------
    def execute(self, cmd: Command) -> None:
        """执行新命令并压入 undo 栈；清空 redo 栈"""
        with self._lock:
            cmd.do()
            self._undo_stack.append(cmd)
            # 清理 redo
            for stale in self._redo_stack:
                stale.dispose()
            self._redo_stack.clear()
            # 超出限制，丢弃最旧的
            while len(self._undo_stack) > self._max:
                old = self._undo_stack.pop(0)
                old.dispose()

    def undo(self) -> Optional[Command]:
        with self._lock:
            if not self._undo_stack:
                return None
            cmd = self._undo_stack.pop()
            cmd.undo()
            self._redo_stack.append(cmd)
            return cmd

    def redo(self) -> Optional[Command]:
        with self._lock:
            if not self._redo_stack:
                return None
            cmd = self._redo_stack.pop()
            cmd.redo()
            self._undo_stack.append(cmd)
            return cmd

    def clear(self) -> None:
        with self._lock:
            for c in self._undo_stack + self._redo_stack:
                c.dispose()
            self._undo_stack.clear()
            self._redo_stack.clear()
