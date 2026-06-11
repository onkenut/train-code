#!/usr/bin/env python3
"""
SmartLit - 智能文献管理器
本地优先的 PDF 文献管理与 AI 辅助分析工具
"""

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from .infrastructure.logger import setup_logger
from .config import get_config
from .gui.main_window import MainWindow
from .db.database import get_db


def main():
    config = get_config()
    logger = setup_logger("smartlit", debug=False)
    logger.info("Starting SmartLit...")

    db = get_db()

    app = QApplication(sys.argv)
    app.setApplicationName("SmartLit")
    app.setOrganizationName("SmartLit")

    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    logger.info("SmartLit started successfully")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
