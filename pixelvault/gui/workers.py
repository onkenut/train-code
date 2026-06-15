import logging
from typing import Optional, List

from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtGui import QPixmap

from pixelvault.database.dao import AssetDAO, LibraryDAO, PersonDAO
from pixelvault.database.models import Asset, AssetStatus
from pixelvault.core.scanner import ScannerOrchestrator
from pixelvault.core.thumbnail import ThumbnailGenerator

logger = logging.getLogger(__name__)


class ScanWorker(QThread):
    progress = Signal(str, int, int)
    finished_signal = Signal(list)

    def __init__(self, library_id: int, force: bool = False, parent=None):
        super().__init__(parent)
        self.library_id = library_id
        self.force = force
        self._scanner = ScannerOrchestrator()
        self._scanner.set_progress_callback(self._on_progress)

    def _on_progress(self, message: str, current: int, total: int):
        self.progress.emit(message, current, total)

    def run(self):
        try:
            new_ids = self._scanner.scan_library(self.library_id, self.force)
            self.finished_signal.emit(new_ids)
        except Exception as e:
            logger.error(f"ScanWorker error: {e}")
            self.finished_signal.emit([])

    def stop(self):
        self._scanner.stop()


class AIProcessWorker(QThread):
    progress = Signal(str, int, int)
    finished_signal = Signal(int)

    def __init__(self, limit: int = 100, parent=None):
        super().__init__(parent)
        self.limit = limit
        self._orchestrator = None

    def run(self):
        try:
            from pixelvault.ai.orchestrator import AIOrchestrator
            self._orchestrator = AIOrchestrator()
            self._orchestrator.set_progress_callback(self._on_progress)
            self._orchestrator.initialize()
            count = self._orchestrator.process_pending_assets(self.limit)
            self.finished_signal.emit(count)
        except Exception as e:
            logger.error(f"AIProcessWorker error: {e}")
            self.finished_signal.emit(0)

    def _on_progress(self, message: str, current: int, total: int):
        self.progress.emit(message, current, total)

    def stop(self):
        if self._orchestrator:
            self._orchestrator.stop()


class ThumbnailLoadWorker(QThread):
    loaded = Signal(int, str)

    def __init__(self, asset_id: int, filepath: str, size, parent=None):
        super().__init__(parent)
        self.asset_id = asset_id
        self.filepath = filepath
        self.size = size

    def run(self):
        try:
            gen = ThumbnailGenerator()
            thumb_path = gen.get_or_generate(self.filepath, self.asset_id, self.size)
            if thumb_path:
                self.loaded.emit(self.asset_id, thumb_path)
        except Exception as e:
            logger.debug(f"ThumbnailLoadWorker error: {e}")


class MetadataProcessWorker(QThread):
    progress = Signal(str, int, int)
    finished_signal = Signal(int)

    def __init__(self, asset_ids: Optional[List[int]] = None, parent=None):
        super().__init__(parent)
        self.asset_ids = asset_ids
        self._running = True

    def run(self):
        try:
            from pixelvault.core.metadata import MetadataExtractor
            from pixelvault.core.hasher import compute_md5, compute_phash
            import cv2

            extractor = MetadataExtractor()
            asset_dao = AssetDAO()
            total = 0

            if self.asset_ids:
                assets = [asset_dao.get_by_id(aid) for aid in self.asset_ids]
                assets = [a for a in assets if a is not None]
            else:
                assets = asset_dao.get_pending(limit=500)

            total_count = len(assets)

            for i, asset in enumerate(assets):
                if not self._running:
                    break
                try:
                    md5 = compute_md5(asset.absolute_path)
                    phash = ""
                    if asset.media_type == "image":
                        img = cv2.imread(asset.absolute_path)
                        if img is not None:
                            phash = compute_phash(img)
                    asset_dao.update_hash(asset.id, md5, phash)
                    extractor.process_asset(asset)
                    total += 1
                    self.progress.emit(f"Processing metadata: {i + 1}/{total_count}", i + 1, total_count)
                except Exception as e:
                    logger.error(f"Metadata processing failed for asset {asset.id}: {e}")
                    asset_dao.update_status(asset.id, AssetStatus.CORRUPT)

            self.finished_signal.emit(total)
        except Exception as e:
            logger.error(f"MetadataProcessWorker error: {e}")
            self.finished_signal.emit(0)

    def stop(self):
        self._running = False
