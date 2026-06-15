import logging
from typing import Optional, List

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QStatusBar, QSplitter, QFileDialog, QMessageBox,
    QMenuBar, QMenu, QLabel, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction, QIcon, QKeySequence

from pixelvault.config import APP_NAME, APP_VERSION
from pixelvault.database.connection import initialize_database, close_connection
from pixelvault.database.dao import LibraryDAO
from pixelvault.gui.navigation import NavigationDock
from pixelvault.gui.browser import CentralBrowser
from pixelvault.gui.inspect import InspectDock
from pixelvault.gui.search_bar import SearchBar
from pixelvault.gui.workers import ScanWorker, AIProcessWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    search_requested = Signal(str)
    library_added = Signal(int)
    scan_requested = Signal(int, bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION}")
        self.setMinimumSize(1280, 800)
        self.resize(1600, 900)

        self.library_dao = LibraryDAO()
        self._scan_worker: Optional[ScanWorker] = None
        self._ai_worker: Optional[AIProcessWorker] = None

        self._setup_ui()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()

        initialize_database()

    def _setup_ui(self):
        self.navigation_dock = NavigationDock(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.navigation_dock)

        self.central_browser = CentralBrowser(self)
        self.setCentralWidget(self.central_browser)

        self.inspect_dock = InspectDock(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspect_dock)

        self.search_bar = SearchBar(self)

    def _setup_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        add_lib_action = QAction("Add Library...", self)
        add_lib_action.setShortcut(QKeySequence("Ctrl+L"))
        add_lib_action.triggered.connect(self._add_library)
        file_menu.addAction(add_lib_action)

        file_menu.addSeparator()

        scan_action = QAction("Scan All Libraries", self)
        scan_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        scan_action.triggered.connect(self._scan_all)
        file_menu.addAction(scan_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = menubar.addMenu("&View")
        toggle_nav = self.navigation_dock.toggleViewAction()
        toggle_nav.setShortcut(QKeySequence("Ctrl+1"))
        view_menu.addAction(toggle_nav)

        toggle_inspect = self.inspect_dock.toggleViewAction()
        toggle_inspect.setShortcut(QKeySequence("Ctrl+2"))
        view_menu.addAction(toggle_inspect)

        view_menu.addSeparator()

        grid_action = QAction("Grid View", self)
        grid_action.triggered.connect(lambda: self.central_browser.set_view_mode("grid"))
        view_menu.addAction(grid_action)

        list_action = QAction("List View", self)
        list_action.triggered.connect(lambda: self.central_browser.set_view_mode("list"))
        view_menu.addAction(list_action)

        tools_menu = menubar.addMenu("&Tools")
        dedup_action = QAction("Find Duplicates...", self)
        dedup_action.triggered.connect(self._find_duplicates)
        tools_menu.addAction(dedup_action)

        ai_process_action = QAction("AI Process Pending", self)
        ai_process_action.triggered.connect(self._ai_process)
        tools_menu.addAction(ai_process_action)

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        self.search_bar.setParent(toolbar)
        toolbar.addWidget(self.search_bar)

    def _setup_statusbar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        self.count_label = QLabel("0 items")
        self.status_bar.addPermanentWidget(self.count_label)

    def _connect_signals(self):
        self.search_requested.connect(self._on_search)
        self.library_added.connect(self._on_library_added)
        self.scan_requested.connect(self._on_scan_requested)

        self.navigation_dock.library_selected.connect(self._on_library_selected)
        self.navigation_dock.person_selected.connect(self._on_person_selected)
        self.central_browser.asset_selected.connect(self._on_asset_selected)
        self.search_bar.search_requested.connect(self.search_requested.emit)

    def _add_library(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Library Directory")
        if directory:
            try:
                from pixelvault.database.models import Library
                lib_id = self.library_dao.insert(
                    Library(directory_path=directory, monitoring_enabled=True)
                )
                self.library_added.emit(lib_id)
                self.status_label.setText(f"Library added: {directory}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add library: {e}")

    def _scan_all(self):
        libs = self.library_dao.get_all()
        if not libs:
            QMessageBox.information(self, "Info", "No libraries added yet. Please add a library first.")
            return
        for lib in libs:
            self._start_scan(lib.id)

    def _start_scan(self, library_id: int, force: bool = False):
        if self._scan_worker and self._scan_worker.isRunning():
            self.status_label.setText("Scan already in progress...")
            return
        self._scan_worker = ScanWorker(library_id, force)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished_signal.connect(self._on_scan_finished)
        self._scan_worker.start()
        self.status_label.setText("Scanning...")

    def _ai_process(self):
        if self._ai_worker and self._ai_worker.isRunning():
            self.status_label.setText("AI processing already in progress...")
            return
        self._ai_worker = AIProcessWorker()
        self._ai_worker.progress.connect(self._on_ai_progress)
        self._ai_worker.finished_signal.connect(self._on_ai_finished)
        self._ai_worker.start()
        self.status_label.setText("AI processing...")

    def _find_duplicates(self):
        from pixelvault.core.dedup import Deduplicator
        dedup = Deduplicator()
        groups = dedup.find_exact_duplicates()
        if groups:
            self.status_label.setText(f"Found {len(groups)} duplicate groups")
            self.central_browser.show_duplicate_groups(groups)
        else:
            self.status_label.setText("No duplicates found")

    def _on_search(self, query: str):
        from pixelvault.ai.clip_engine import CLIPEngine
        from pixelvault.search.engine import SearchEngine
        engine = SearchEngine(CLIPEngine())
        results = engine.search(query)
        self.central_browser.show_search_results(results)
        self.status_label.setText(f"Search: {len(results)} results for '{query}'")

    def _on_library_added(self, lib_id: int):
        self.navigation_dock.refresh_libraries()
        self._start_scan(lib_id)

    def _on_scan_requested(self, library_id: int, force: bool):
        self._start_scan(library_id, force)

    def _on_library_selected(self, library_id: int):
        from pixelvault.database.dao import AssetDAO
        assets = AssetDAO().get_by_library(library_id)
        self.central_browser.show_assets(assets)
        self.count_label.setText(f"{len(assets)} items")

    def _on_person_selected(self, person_id: int):
        from pixelvault.ai.clip_engine import CLIPEngine
        from pixelvault.search.engine import SearchEngine
        engine = SearchEngine(CLIPEngine())
        persons = engine.person_dao.get_all()
        matching = [p for p in persons if p.id == person_id]
        if matching:
            results = engine.search_by_person(matching[0].name)
            self.central_browser.show_search_results(results)

    def _on_asset_selected(self, asset_id: int):
        self.inspect_dock.show_asset(asset_id)

    def _on_scan_progress(self, message: str, current: int, total: int):
        self.status_label.setText(message)
        if total > 0:
            self.status_bar.showMessage(f"{message} ({current}/{total})")

    def _on_scan_finished(self, new_ids: list):
        self.status_label.setText(f"Scan complete: {len(new_ids)} new assets")
        self.navigation_dock.refresh_libraries()

    def _on_ai_progress(self, message: str, current: int, total: int):
        self.status_label.setText(message)

    def _on_ai_finished(self, count: int):
        self.status_label.setText(f"AI processing complete: {count} assets processed")

    def _show_about(self):
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "Local Multimedia Asset Management & Intelligent Search Hub\n\n"
            "Built with PySide6, SQLite, CLIP & InsightFace",
        )

    def closeEvent(self, event):
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.stop()
            self._scan_worker.wait(3000)
        if self._ai_worker and self._ai_worker.isRunning():
            self._ai_worker.stop()
            self._ai_worker.wait(3000)
        close_connection()
        event.accept()
