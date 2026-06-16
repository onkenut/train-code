import json
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QTabWidget,
    QLabel, QScrollArea, QFormLayout, QGroupBox,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QSplitter, QListView,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QImage, QStandardItemModel, QStandardItem, QPainter

from pixelvault.database.dao import AssetDAO, MetadataDAO, TagDAO, FaceDAO
from pixelvault.database.models import Asset, Metadata
from pixelvault.config import THUMB_MEDIUM, THUMB_LARGE

logger = logging.getLogger(__name__)


class PreviewPane(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = None
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setBackgroundBrush(Qt.GlobalColor.black)

    def show_image(self, filepath: str):
        try:
            pixmap = QPixmap(filepath)
            if pixmap.isNull():
                self._scene.clear()
                text = self._scene.addText("Unable to load image")
                text.setDefaultTextColor(Qt.GlobalColor.white)
                return

            self._scene.clear()
            self._pixmap_item = QGraphicsPixmapItem(pixmap)
            self._scene.addItem(self._pixmap_item)
            self._scene.setSceneRect(pixmap.rect())
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        except Exception as e:
            logger.debug(f"PreviewPane.show_image failed: {e}")
            self._scene.clear()

    def wheelEvent(self, event):
        try:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
        except Exception:
            pass

    def clear(self):
        self._scene.clear()


class InspectDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Inspector", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setMinimumWidth(280)

        self.asset_dao = AssetDAO()
        self.metadata_dao = MetadataDAO()
        self.tag_dao = TagDAO()
        self.face_dao = FaceDAO()

        self._setup_ui()

    def _setup_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        self._preview = PreviewPane()
        self._preview.setFixedHeight(300)
        layout.addWidget(self._preview)

        self._tabs = QTabWidget()

        self._exif_widget = QWidget()
        self._exif_layout = QFormLayout(self._exif_widget)
        self._exif_scroll = QScrollArea()
        self._exif_scroll.setWidget(self._exif_widget)
        self._exif_scroll.setWidgetResizable(True)
        self._tabs.addTab(self._exif_scroll, "EXIF")

        self._tags_widget = QWidget()
        self._tags_layout = QVBoxLayout(self._tags_widget)
        self._tags_list = QListView()
        self._tags_model = QStandardItemModel()
        self._tags_list.setModel(self._tags_model)
        self._tags_layout.addWidget(self._tags_list)
        self._tabs.addTab(self._tags_widget, "Tags")

        self._faces_widget = QWidget()
        self._faces_layout = QVBoxLayout(self._faces_widget)
        self._faces_list = QListView()
        self._faces_model = QStandardItemModel()
        self._faces_list.setModel(self._faces_model)
        self._faces_layout.addWidget(self._faces_list)
        self._tabs.addTab(self._faces_widget, "Faces")

        layout.addWidget(self._tabs)
        self.setWidget(container)

    def show_asset(self, asset_id: int):
        try:
            asset = self.asset_dao.get_by_id(asset_id)
            if not asset:
                self.clear_inspector()
                return

            self._preview.show_image(asset.absolute_path)
            self._show_exif(asset)
            self._show_tags(asset_id)
            self._show_faces(asset_id)
        except Exception as e:
            logger.error(f"InspectDock.show_asset failed: {e}")
            self.clear_inspector()

    def _show_exif(self, asset: Asset):
        try:
            while self._exif_layout.rowCount() > 0:
                self._exif_layout.removeRow(0)

            self._exif_layout.addRow("Filename:", QLabel(asset.filename))
            self._exif_layout.addRow("Path:", QLabel(asset.absolute_path))
            self._exif_layout.addRow("Size:", QLabel(f"{asset.file_size:,} bytes"))
            self._exif_layout.addRow("Type:", QLabel(asset.media_type))
            if asset.width and asset.height:
                self._exif_layout.addRow("Resolution:", QLabel(f"{asset.width} x {asset.height}"))
            if asset.duration:
                self._exif_layout.addRow("Duration:", QLabel(f"{asset.duration:.1f}s"))

            meta = self.metadata_dao.get_by_asset(asset.id)
            if meta and meta.exif_json:
                try:
                    exif = json.loads(meta.exif_json)
                    for key, value in exif.items():
                        if key != "GPSInfo" and isinstance(value, (str, int, float)):
                            self._exif_layout.addRow(f"{key}:", QLabel(str(value)))

                    if meta.gps_longitude is not None and meta.gps_latitude is not None:
                        self._exif_layout.addRow(
                            "GPS:",
                            QLabel(f"{meta.gps_latitude:.4f}, {meta.gps_longitude:.4f}"),
                        )
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.error(f"InspectDock._show_exif failed: {e}")

    def _show_tags(self, asset_id: int):
        self._tags_model.clear()
        tag_pairs = self.tag_dao.get_by_asset(asset_id)
        for tag, confidence in tag_pairs:
            item = QStandardItem(f"{tag.name} ({confidence:.2f})")
            self._tags_model.appendRow(item)

    def _show_faces(self, asset_id: int):
        self._faces_model.clear()
        faces = self.face_dao.get_by_asset(asset_id)
        for face in faces:
            label = f"Face (confidence: {face.confidence:.2f})"
            item = QStandardItem(label)
            self._faces_model.appendRow(item)

    def clear_inspector(self):
        self._preview.clear()
        while self._exif_layout.rowCount() > 0:
            self._exif_layout.removeRow(0)
        self._tags_model.clear()
        self._faces_model.clear()
