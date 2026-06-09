"""PointVault 桌面应用入口
Usage:
    python -m pointvault.main          # 模块方式运行
    pointvault                          # 安装后通过 entry point 运行
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt


def _setup_logging(verbose: bool = False) -> None:
    fmt = "%(asctime)s [%(levelname)7s] %(name)s: %(message)s"
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format=fmt, datefmt="%H:%M:%S", level=level,
                        handlers=[logging.StreamHandler(sys.stdout)])


def _setup_qt_material(app: QApplication) -> None:
    """尝试加载 qt-material 深色主题，失败则回退到系统默认"""
    try:
        from qt_material import apply_stylesheet
        apply_stylesheet(app, theme="dark_teal.xml", invert_secondary=True)
        logging.getLogger("pointvault").info("已加载 qt-material 深色主题")
    except Exception as e:  # pragma: no cover - 仅装饰性
        logging.getLogger("pointvault").debug(f"qt-material 不可用，使用默认主题: {e}")


def main() -> int:
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    _setup_logging(verbose)
    log = logging.getLogger("pointvault")

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName("PointVault")
    app.setOrganizationName("PointVault Team")
    app.setApplicationVersion("1.0.0")

    font = QFont("Segoe UI", 10 if sys.platform == "win32" else 11)
    app.setFont(font)

    _setup_qt_material(app)

    from pointvault.gui.main_window import PointVaultMainWindow
    win = PointVaultMainWindow()
    win.resize(1400, 900)
    win.show()

    log.info("PointVault 启动成功")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
