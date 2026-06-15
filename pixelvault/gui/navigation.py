import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDockWidget, QTreeView, QListView, QVBoxLayout, QWidget,
    QHeaderView, QMenu, QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QAbstractItemModel, QModelIndex
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction

from pixelvault.database.dao import LibraryDAO, PersonDAO
from pixelvault.database.models import Library, Person

logger = logging.getLogger(__name__)


class NavigationDock(QDockWidget):
    library_selected = Signal(int)
    person_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__("Navigation", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setMinimumWidth(200)

        self.library_dao = LibraryDAO()
        self.person_dao = PersonDAO()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        self.library_tree = QTreeView()
        self.library_tree.setHeaderHidden(False)
        self.library_model = QStandardItemModel()
        self.library_model.setHorizontalHeaderLabels(["Libraries"])
        self.library_tree.setModel(self.library_model)
        self.library_tree.clicked.connect(self._on_library_click)
        self.library_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.library_tree.customContextMenuRequested.connect(self._library_context_menu)
        layout.addWidget(self.library_tree)

        self.person_list = QListView()
        self.person_list.setFlow(QListView.Flow.TopToBottom)
        self.person_model = QStandardItemModel()
        self.person_list.setModel(self.person_model)
        self.person_list.clicked.connect(self._on_person_click)
        self.person_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.person_list.customContextMenuRequested.connect(self._person_context_menu)
        layout.addWidget(self.person_list)

        self.setWidget(container)
        self.refresh_libraries()
        self.refresh_persons()

    def refresh_libraries(self):
        self.library_model.clear()
        self.library_model.setHorizontalHeaderLabels(["Libraries"])
        root = self.library_model.invisibleRootItem()

        libraries = self.library_dao.get_all()
        for lib in libraries:
            import os
            name = os.path.basename(lib.directory_path) or lib.directory_path
            item = QStandardItem(name)
            item.setData(lib.id, Qt.ItemDataRole.UserRole)
            item.setToolTip(lib.directory_path)
            root.appendRow(item)

        self.library_tree.expandAll()

    def refresh_persons(self):
        self.person_model.clear()
        persons = self.person_dao.get_all()
        for person in persons:
            label = f"{person.name} ({person.face_count})"
            item = QStandardItem(label)
            item.setData(person.id, Qt.ItemDataRole.UserRole)
            self.person_model.appendRow(item)

    def _on_library_click(self, index: QModelIndex):
        item = self.library_model.itemFromIndex(index)
        if item:
            lib_id = item.data(Qt.ItemDataRole.UserRole)
            if lib_id:
                self.library_selected.emit(lib_id)

    def _on_person_click(self, index: QModelIndex):
        item = self.person_model.itemFromIndex(index)
        if item:
            person_id = item.data(Qt.ItemDataRole.UserRole)
            if person_id:
                self.person_selected.emit(person_id)

    def _library_context_menu(self, pos):
        index = self.library_tree.indexAt(pos)
        if not index.isValid():
            return

        item = self.library_model.itemFromIndex(index)
        lib_id = item.data(Qt.ItemDataRole.UserRole)
        if not lib_id:
            return

        menu = QMenu(self)
        scan_action = QAction("Scan", self)
        scan_action.triggered.connect(lambda: self._scan_library(lib_id))
        menu.addAction(scan_action)

        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self._remove_library(lib_id))
        menu.addAction(remove_action)

        menu.exec(self.library_tree.viewport().mapToGlobal(pos))

    def _person_context_menu(self, pos):
        index = self.person_list.indexAt(pos)
        if not index.isValid():
            return

        item = self.person_model.itemFromIndex(index)
        person_id = item.data(Qt.ItemDataRole.UserRole)
        if not person_id:
            return

        menu = QMenu(self)
        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(lambda: self._rename_person(person_id))
        menu.addAction(rename_action)

        menu.exec(self.person_list.viewport().mapToGlobal(pos))

    def _scan_library(self, lib_id: int):
        from pixelvault.gui.main_window import MainWindow
        main_win = self.window()
        if isinstance(main_win, MainWindow):
            main_win._start_scan(lib_id)

    def _remove_library(self, lib_id: int):
        reply = QMessageBox.question(
            self, "Remove Library",
            "Remove this library? Assets will be removed from index but files will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.library_dao.delete(lib_id)
            self.refresh_libraries()

    def _rename_person(self, person_id: int):
        name, ok = QInputDialog.getText(self, "Rename Person", "New name:")
        if ok and name:
            self.person_dao.rename(person_id, name)
            self.refresh_persons()
