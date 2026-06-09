"""PointVault 桌面应用入口
Usage:
    python -m pointvault.main          # 模块方式运行
    pointvault                          # 安装后通过 entry point 运行
"""

from __future__ import annotations

import logging
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt


def _setup_logging(verbose: bool = False) -> Path:
    """设置控制台 + 文件日志，返回日志文件路径"""
    fmt = "%(asctime)s [%(levelname)7s] %(name)s: %(message)s"
    level = logging.DEBUG if verbose else logging.INFO

    log_dir = Path(tempfile.gettempdir()) / "PointVault"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"pointvault_{ts}.log"

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(log_file), encoding="utf-8"),
    ]
    logging.basicConfig(format=fmt, datefmt="%H:%M:%S", level=level, handlers=handlers)
    return log_file


def _install_excepthook() -> None:
    """安装全局异常钩子，捕获 Qt 事件循环内部异常（否则会无声退出）"""
    _old_hook = sys.excepthook

    def _hook(etype, value, tb):
        lines = traceback.format_exception(etype, value, tb)
        msg = "".join(lines)
        # 写日志
        log = logging.getLogger("pointvault.crash")
        log.critical("未捕获异常导致程序退出:\n%s", msg)
        # 控制台 + 文件都写一份
        sys.stderr.write(msg)
        sys.stderr.flush()
        # 调用原始钩子
        _old_hook(etype, value, tb)

    sys.excepthook = _hook


def _install_qt_message_handler() -> None:
    """重定向 Qt 的警告/致命消息到 Python 日志"""
    from PySide6.QtCore import qInstallMessageHandler, QtMsgType

    _py_log = logging.getLogger("pointvault.qt")

    def _handler(mtype, ctx, msg):
        lvl = {
            QtMsgType.QtDebugMsg: logging.DEBUG,
            QtMsgType.QtInfoMsg: logging.INFO,
            QtMsgType.QtWarningMsg: logging.WARNING,
            QtMsgType.QtCriticalMsg: logging.ERROR,
            QtMsgType.QtFatalMsg: logging.CRITICAL,
        }.get(mtype, logging.ERROR)
        _py_log.log(lvl, "Qt: %s", msg)

    qInstallMessageHandler(_handler)


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
    log_file = _setup_logging(verbose)
    log = logging.getLogger("pointvault")
    log.info(f"PointVault 启动，日志文件: {log_file}")

    _install_excepthook()
    log.info("已安装全局 sys.excepthook")

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName("PointVault")
    app.setOrganizationName("PointVault Team")
    app.setApplicationVersion("1.0.0")

    _install_qt_message_handler()
    log.info("已安装 Qt 消息重定向处理器")

    font = QFont("Segoe UI", 10 if sys.platform == "win32" else 11)
    app.setFont(font)

    _setup_qt_material(app)

    from pointvault.gui.main_window import PointVaultMainWindow
    win = PointVaultMainWindow()
    win.resize(1400, 900)
    win.show()

    log.info("PointVault 启动成功")
    rc = app.exec()
    log.info(f"PointVault 正常退出，返回码={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
