import os
import logging
from pathlib import Path
from typing import Callable, Optional

from pixelvault.config import SUPPORTED_EXTS
from pixelvault.database.dao import LibraryDAO, AssetDAO

logger = logging.getLogger(__name__)


class FileSystemWatcher:
    def __init__(self):
        self.library_dao = LibraryDAO()
        self.asset_dao = AssetDAO()
        self._observer = None
        self._callback: Optional[Callable] = None
        self._running = False

    def set_callback(self, callback: Callable) -> None:
        self._callback = callback

    def start(self) -> None:
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class Handler(FileSystemEventHandler):
                def __init__(self, watcher):
                    super().__init__()
                    self.watcher = watcher

                def on_created(self, event):
                    if not event.is_directory:
                        ext = Path(event.src_path).suffix.lower()
                        if ext in SUPPORTED_EXTS:
                            logger.info(f"New file detected: {event.src_path}")
                            if self.watcher._callback:
                                self.watcher._callback(event.src_path, "created")

                def on_deleted(self, event):
                    if not event.is_directory:
                        ext = Path(event.src_path).suffix.lower()
                        if ext in SUPPORTED_EXTS:
                            logger.info(f"File deleted: {event.src_path}")
                            if self.watcher._callback:
                                self.watcher._callback(event.src_path, "deleted")

                def on_modified(self, event):
                    if not event.is_directory:
                        ext = Path(event.src_path).suffix.lower()
                        if ext in SUPPORTED_EXTS:
                            logger.info(f"File modified: {event.src_path}")
                            if self.watcher._callback:
                                self.watcher._callback(event.src_path, "modified")

            self._observer = Observer()
            handler = Handler(self)

            libraries = self.library_dao.get_all()
            for lib in libraries:
                if lib.monitoring_enabled and os.path.isdir(lib.directory_path):
                    self._observer.schedule(handler, lib.directory_path, recursive=True)

            self._observer.start()
            self._running = True
            logger.info("FileSystemWatcher started")

        except ImportError:
            logger.warning("watchdog not installed, file system watching disabled")
        except Exception as e:
            logger.error(f"FileSystemWatcher error: {e}")

    def stop(self) -> None:
        if self._observer and self._running:
            self._observer.stop()
            self._observer.join()
            self._running = False
            logger.info("FileSystemWatcher stopped")

    def is_running(self) -> bool:
        return self._running
