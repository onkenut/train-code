"""
配置管理模块

管理应用程序级配置和项目级配置，包括用户偏好、最近打开项目、
默认渲染设置、语言选择等。使用 JSON 文件进行持久化。
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


APP_CONFIG_DIR = Path(os.path.expanduser("~")) / ".pointvault"
APP_CONFIG_FILE = APP_CONFIG_DIR / "config.json"


def _default_render_settings() -> Dict[str, Any]:
    return {
        "point_size": 3.0,
        "background_color": [0.15, 0.15, 0.15],
        "color_mode": "height",  # height, rgb, intensity, label, normal
        "show_grid": True,
        "show_axes": True,
        "point_opacity": 1.0,
        "perspective": True,
        "field_of_view": 60.0,
    }


def _default_ui_settings() -> Dict[str, Any]:
    return {
        "theme": "dark_teal.xml",
        "language": "zh_CN",  # zh_CN, en_US
        "sidebar_width": 280,
        "sidebar_collapsed": False,
        "statusbar_visible": True,
        "auto_save_interval_sec": 120,
    }


@dataclass
class AppConfig:
    """应用级用户配置（跨项目共享）"""

    recent_projects: List[str] = field(default_factory=list)
    max_recent_projects: int = 10
    default_pointclouds_dir: str = ""
    default_projects_dir: str = ""
    render_settings: Dict[str, Any] = field(default_factory=_default_render_settings)
    ui_settings: Dict[str, Any] = field(default_factory=_default_ui_settings)

    def add_recent_project(self, path: str) -> None:
        path = str(Path(path).resolve())
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        if len(self.recent_projects) > self.max_recent_projects:
            self.recent_projects = self.recent_projects[: self.max_recent_projects]

    def remove_recent_project(self, path: str) -> None:
        path = str(Path(path).resolve())
        if path in self.recent_projects:
            self.recent_projects.remove(path)


@dataclass
class ProjectConfig:
    """项目级配置（保存在项目文件夹 project.json 中）"""

    name: str = "Untitled Project"
    description: str = ""
    created_at: str = ""
    last_modified: str = ""
    default_labelset_id: Optional[int] = None
    active_pointcloud_ids: List[int] = field(default_factory=list)
    camera_bookmarks: List[Dict[str, Any]] = field(default_factory=list)
    current_view: Optional[Dict[str, Any]] = None


class SettingsManager:
    """设置管理器 - 线程安全地读写 JSON 配置文件"""

    _instance: Optional["SettingsManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "SettingsManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._app_config = AppConfig()
                    cls._instance._loaded = False
        return cls._instance

    def __init__(self) -> None:
        if not getattr(self, "_loaded", False):
            self._loaded = True
            self.load_app_config()

    # ---------- App 配置 ----------
    def load_app_config(self) -> AppConfig:
        APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if APP_CONFIG_FILE.exists():
            try:
                with open(APP_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._app_config = AppConfig(**data)
            except (json.JSONDecodeError, TypeError, KeyError):
                self._app_config = AppConfig()
        else:
            self._app_config = AppConfig()
            self.save_app_config()
        return self._app_config

    def save_app_config(self) -> None:
        APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(APP_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self._app_config), f, indent=2, ensure_ascii=False)

    @property
    def app_config(self) -> AppConfig:
        return self._app_config

    def update_app_config(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self._app_config, k):
                setattr(self._app_config, k, v)
        self.save_app_config()

    # ---------- Project 配置 ----------
    @staticmethod
    def load_project_config(project_dir: Path | str) -> ProjectConfig:
        project_dir = Path(project_dir)
        cfg_file = project_dir / "project.json"
        if cfg_file.exists():
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ProjectConfig(**data)
        return ProjectConfig()

    @staticmethod
    def save_project_config(project_dir: Path | str, config: ProjectConfig) -> None:
        project_dir = Path(project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = project_dir / "project.json"
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, indent=2, ensure_ascii=False)
