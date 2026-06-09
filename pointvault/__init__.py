"""
PointVault - 三维点云标注与交互分析工具

一个面向点云数据处理与研究人员的个人桌面工具，提供多格式导入、
高性能3D渲染、交互式标注、SQLite数据管理、自动预处理与导出功能。
"""

__version__ = "0.1.0"
__author__ = "PointVault Team"

from pointvault.config import AppConfig, ProjectConfig, SettingsManager

__all__ = [
    "__version__",
    "__author__",
    "AppConfig",
    "ProjectConfig",
    "SettingsManager",
]
