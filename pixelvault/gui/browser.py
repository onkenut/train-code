import logging
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QListView, QTableView, QAbstractItemView, QLabel,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize, QAbstractListModel, QModelIndex, QSortFilterProxyModel, QObject
from PySide6.QtGui import QPixmap, QIcon, QPainter, QColor, QFont

from pixelvault.database.models import Asset, SearchResult, DuplicateGroup
from pixelvault.core.thumbnail import ThumbnailGenerator
from pixelvault.config import THUMB_SMALL

logger = logging.getLogger(__name__)


class ThumbnailModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._assets: List[Asset] = []
        self._thumbnails = {}
        self._thumb_gen = ThumbnailGenerator()
        self._placeholder = self._create_placeholder()
        self._workers: List[QObject] = []

    def _create_placeholder(self) -> QPixmap:
        pixmap = QPixmap(128, 128)
        pixmap.fill(QColor(240, 240, 240))
        painter = QPainter(pixmap)
        painter.setPen(QColor(200, 200, 200))
        painter.drawRect(0, 0, 127, 127)
        painter.setPen(QColor(160, 160, 160))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "...")
        painter.end()
        return pixmap

    def set_assets(self, assets: List[Asset]):
        self.beginResetModel()
        self._assets = assets
        self._thumbnails = {}
        self.endResetModel()

        for w in self._workers:
            try:
                if hasattr(w, "isRunning") and w.isRunning():
                    w.quit()
                    w.wait(100)
            except Exception:
                pass
        self._workers.clear()

        for asset in assets:
            self._load_thumbnail(asset)

    def _load_thumbnail(self, asset: Asset):
        from PySide6.QtCore import QThread
        from pixelvault.gui.workers import ThumbnailLoadWorker

        worker = ThumbnailLoadWorker(asset.id, asset.absolute_path, THUMB_SMALL, self)
        worker.loaded.connect(self._on_thumbnail_loaded)
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))
        self._workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker):
        try:
            if worker in self._workers:
                self._workers.remove(worker)
        except Exception:
            pass
        try:
            worker.deleteLater()
        except Exception:
            pass

    def _on_thumbnail_loaded(self, asset_id: int, thumb_path: str):
        row = None
        for i, a in enumerate(self._assets):
            if a.id == asset_id:
                row = i
                break
        if row is not None:
            try:
                pixmap = QPixmap(thumb_path)
                if not pixmap.isNull():
                    self._thumbnails[asset_id] = pixmap
                    index = self.index(row)
                    self.dataChanged.emit(index, index)
            except Exception as e:
                logger.debug(f"Failed to load thumbnail pixmap: {e}")

    def rowCount(self, parent=QModelIndex()):
        return len(self._assets)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._assets):
            return None

        asset = self._assets[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return asset.filename
        elif role == Qt.ItemDataRole.DecorationRole:
            return self._thumbnails.get(asset.id, self._placeholder)
        elif role == Qt.ItemDataRole.ToolTipRole:
            dims = f"{asset.width}x{asset.height}" if asset.width and asset.height else ""
            return f"{asset.filename}\n{asset.absolute_path}\n{dims}"
        elif role == Qt.ItemDataRole.UserRole:
            return asset.id

        return None

    def get_asset(self, row: int) -> Optional[Asset]:
        if 0 <= row < len(self._assets):
            return self._assets[row]
        return None


class CentralBrowser(QWidget):
    asset_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_mode = "grid"
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._info_label = QLabel("No items")
        self._info_label.setStyleSheet("padding: 4px; color: #666;")
        layout.addWidget(self._info_label)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._grid_view = QListView()
        self._grid_view.setViewMode(QListView.ViewMode.IconMode)
        self._grid_view.setIconSize(QSize(128, 128))
        self._grid_view.setGridSize(QSize(140, 150))
        self._grid_view.setResizeMode(QListView.ResizeMode.Adjust)
        self._grid_view.setMovement(QListView.Movement.Static)
        self._grid_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._grid_view.clicked.connect(self._on_item_clicked)
        self._model = ThumbnailModel()
        self._grid_view.setModel(self._model)

        self._list_view = QListView()
        self._list_view.setViewMode(QListView.ViewMode.ListMode)
        self._list_view.setMovement(QListView.Movement.Static)
        self._list_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list_view.clicked.connect(self._on_item_clicked)
        self._list_view.setModel(self._model)

        self._stack.addWidget(self._grid_view)
        self._stack.addWidget(self._list_view)
        self._stack.setCurrentIndex(0)

        self._filmstrip = QListView()
        self._filmstrip.setFlow(QListView.Flow.LeftToRight)
        self._filmstrip.setIconSize(QSize(64, 64))
        self._filmstrip.setFixedHeight(80)
        self._filmstrip.setMovement(QListView.Movement.Static)
        self._filmstrip.setModel(self._model)
        self._filmstrip.clicked.connect(self._on_item_clicked)
        layout.addWidget(self._filmstrip)

    def set_view_mode(self, mode: str):
        self._view_mode = mode
        if mode == "grid":
            self._stack.setCurrentIndex(0)
        else:
            self._stack.setCurrentIndex(1)

    def show_assets(self, assets: List[Asset]):
        self._model.set_assets(assets)
        self._info_label.setText(f"{len(assets)} items")

    def show_search_results(self, results: List[SearchResult]):
        from pixelvault.database.dao import AssetDAO
        asset_dao = AssetDAO()
        assets = []
        for r in results:
            asset = asset_dao.get_by_id(r.asset_id)
            if asset:
                assets.append(asset)
        self._model.set_assets(assets)
        self._info_label.setText(f"{len(assets)} results")

    def show_duplicate_groups(self, groups: List[DuplicateGroup]):
        assets = []
        for group in groups:
            assets.extend(group.assets)
        self._model.set_assets(assets)
        self._info_label.setText(f"{len(groups)} duplicate groups, {len(assets)} files")

    def _on_item_clicked(self, index: QModelIndex):
        asset_id = index.data(Qt.ItemDataRole.UserRole)
        if asset_id:
            self.asset_selected.emit(asset_id)
