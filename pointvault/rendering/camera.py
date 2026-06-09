"""
相机管理器 - 相机位姿、标准视图、书签
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class StandardView(str, Enum):
    TOP = "top"
    FRONT = "front"
    RIGHT = "right"
    BACK = "back"
    LEFT = "left"
    BOTTOM = "bottom"
    ISO = "iso"


@dataclass
class CameraPose:
    """Open3D 风格的相机位姿

    由 eye (相机位置), lookat (看向点), up (向上向量) 定义。
    field_of_view 为度。
    """

    eye: Tuple[float, float, float] = (0.0, 0.0, 10.0)
    lookat: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    up: Tuple[float, float, float] = (0.0, 1.0, 0.0)
    fov: float = 60.0
    perspective: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CameraPose":
        return cls(
            eye=tuple(float(x) for x in d["eye"]),
            lookat=tuple(float(x) for x in d["lookat"]),
            up=tuple(float(x) for x in d["up"]),
            fov=float(d.get("fov", 60.0)),
            perspective=bool(d.get("perspective", True)),
        )


@dataclass
class ViewBookmark:
    id: int
    name: str
    pose: CameraPose
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "pose": self.pose.to_dict(),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ViewBookmark":
        return cls(
            id=int(d["id"]),
            name=str(d["name"]),
            pose=CameraPose.from_dict(d["pose"]),
            created_at=str(d.get("created_at", "")),
        )


class CameraManager:
    """相机管理器 - 负责标准视图生成、书签管理"""

    def __init__(self) -> None:
        self._bookmarks: List[ViewBookmark] = []
        self._next_bookmark_id = 1

    # ---------- 标准视图 ----------
    @staticmethod
    def standard_view(
        view: StandardView,
        bbox_center: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        bbox_size: Tuple[float, float, float] = (10.0, 10.0, 10.0),
        fov: float = 60.0,
        perspective: bool = True,
    ) -> CameraPose:
        cx, cy, cz = bbox_center
        sx, sy, sz = bbox_size
        max_dim = max(sx, sy, sz) * 1.5
        max_dim = max(max_dim, 1.0)

        # 计算 fov 对应的距离（近似）
        dist = max_dim / (2.0 * np.tan(np.radians(fov / 2.0)))

        if view == StandardView.TOP:
            eye = (cx, cy - 1e-4, cz + dist)
            up = (0.0, 1.0, 0.0)
            lookat = (cx, cy, cz)
        elif view == StandardView.FRONT:
            eye = (cx, cy - dist, cz)
            up = (0.0, 0.0, 1.0)
            lookat = (cx, cy, cz)
        elif view == StandardView.BACK:
            eye = (cx, cy + dist, cz)
            up = (0.0, 0.0, 1.0)
            lookat = (cx, cy, cz)
        elif view == StandardView.RIGHT:
            eye = (cx + dist, cy, cz)
            up = (0.0, 0.0, 1.0)
            lookat = (cx, cy, cz)
        elif view == StandardView.LEFT:
            eye = (cx - dist, cy, cz)
            up = (0.0, 0.0, 1.0)
            lookat = (cx, cy, cz)
        elif view == StandardView.BOTTOM:
            eye = (cx, cy - 1e-4, cz - dist)
            up = (0.0, -1.0, 0.0)
            lookat = (cx, cy, cz)
        else:  # ISO
            s = dist / np.sqrt(3.0)
            eye = (cx + s, cy + s, cz + s * 0.8)
            up = (0.0, 0.0, 1.0)
            lookat = (cx, cy, cz)

        return CameraPose(
            eye=eye,
            lookat=lookat,
            up=up,
            fov=fov,
            perspective=perspective,
        )

    def fit_to_bbox(
        self,
        bbox_center: Tuple[float, float, float],
        bbox_size: Tuple[float, float, float],
        fov: float = 60.0,
        perspective: bool = True,
    ) -> CameraPose:
        return self.standard_view(
            StandardView.ISO, bbox_center, bbox_size, fov, perspective
        )

    # ---------- 书签 ----------
    def add_bookmark(self, name: str, pose: CameraPose) -> ViewBookmark:
        from datetime import datetime

        bm = ViewBookmark(
            id=self._next_bookmark_id,
            name=name,
            pose=pose,
            created_at=datetime.utcnow().isoformat(timespec="seconds"),
        )
        self._bookmarks.append(bm)
        self._next_bookmark_id += 1
        return bm

    def remove_bookmark(self, bookmark_id: int) -> bool:
        for i, bm in enumerate(self._bookmarks):
            if bm.id == bookmark_id:
                del self._bookmarks[i]
                return True
        return False

    def get_bookmark(self, bookmark_id: int) -> Optional[ViewBookmark]:
        for bm in self._bookmarks:
            if bm.id == bookmark_id:
                return bm
        return None

    @property
    def bookmarks(self) -> List[ViewBookmark]:
        return list(self._bookmarks)

    # ---------- 序列化 ----------
    def to_list(self) -> List[Dict[str, Any]]:
        return [bm.to_dict() for bm in self._bookmarks]

    def load_from_list(self, data: List[Dict[str, Any]]) -> None:
        self._bookmarks = []
        max_id = 0
        for d in data:
            bm = ViewBookmark.from_dict(d)
            self._bookmarks.append(bm)
            max_id = max(max_id, bm.id)
        self._next_bookmark_id = max_id + 1
