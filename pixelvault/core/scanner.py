import os
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Callable

from pixelvault.config import SUPPORTED_EXTS, SUPPORTED_IMAGE_EXTS, SUPPORTED_VIDEO_EXTS, SUPPORTED_AUDIO_EXTS
from pixelvault.database.dao import LibraryDAO, AssetDAO
from pixelvault.database.models import Library, Asset, MediaType, AssetStatus

logger = logging.getLogger(__name__)


class ScannerOrchestrator:
    def __init__(self):
        self.library_dao = LibraryDAO()
        self.asset_dao = AssetDAO()
        self._running = False
        self._progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable) -> None:
        self._progress_callback = callback

    def _notify_progress(self, message: str, current: int = 0, total: int = 0) -> None:
        if self._progress_callback:
            self._progress_callback(message, current, total)

    def add_library(self, directory_path: str, monitor: bool = True) -> int:
        path = os.path.abspath(directory_path)
        if not os.path.isdir(path):
            raise ValueError(f"Directory does not exist: {path}")
        existing = self.library_dao.get_by_path(path)
        if existing:
            return existing.id
        lib = Library(directory_path=path, monitoring_enabled=monitor)
        return self.library_dao.insert(lib)

    def remove_library(self, library_id: int) -> None:
        self.library_dao.delete(library_id)

    def scan_library(self, library_id: int, force: bool = False) -> List[int]:
        lib = self.library_dao.get_by_id(library_id)
        if not lib:
            raise ValueError(f"Library not found: {library_id}")

        self._running = True
        new_ids = []

        try:
            all_files = self._collect_files(lib.directory_path)
            total = len(all_files)
            self._notify_progress("Scanning files...", 0, total)

            for i, filepath in enumerate(all_files):
                if not self._running:
                    break

                existing = self.asset_dao.get_by_path(filepath)
                if existing and not force:
                    if existing.status == AssetStatus.INDEXED:
                        continue

                mod_time = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                file_size = os.path.getsize(filepath)
                ext = Path(filepath).suffix.lower()
                media_type = self._classify_media(ext)

                asset = Asset(
                    library_id=library_id,
                    absolute_path=filepath,
                    filename=os.path.basename(filepath),
                    extension=ext,
                    file_size=file_size,
                    modified_time=mod_time,
                    media_type=media_type,
                    status=AssetStatus.PENDING,
                )

                asset_id = self.asset_dao.insert(asset)
                if asset_id:
                    new_ids.append(asset_id)

                if (i + 1) % 50 == 0:
                    self._notify_progress(f"Scanning: {i + 1}/{total}", i + 1, total)

            self.library_dao.update_scan_time(library_id)
            self._notify_progress("Scan complete", total, total)

        except Exception as e:
            logger.error(f"Scan error: {e}")
            self._notify_progress(f"Scan error: {e}", 0, 0)
        finally:
            self._running = False

        return new_ids

    def scan_all_libraries(self) -> List[int]:
        all_ids = []
        libs = self.library_dao.get_all()
        for lib in libs:
            if lib.monitoring_enabled:
                ids = self.scan_library(lib.id)
                all_ids.extend(ids)
        return all_ids

    def stop(self) -> None:
        self._running = False

    def _collect_files(self, directory: str) -> List[str]:
        files = []
        for root, _, filenames in os.walk(directory):
            for fname in filenames:
                ext = Path(fname).suffix.lower()
                if ext in SUPPORTED_EXTS:
                    files.append(os.path.join(root, fname))
        return sorted(files)

    @staticmethod
    def _classify_media(ext: str) -> str:
        if ext in SUPPORTED_IMAGE_EXTS:
            return MediaType.IMAGE
        elif ext in SUPPORTED_VIDEO_EXTS:
            return MediaType.VIDEO
        elif ext in SUPPORTED_AUDIO_EXTS:
            return MediaType.AUDIO
        return MediaType.IMAGE
