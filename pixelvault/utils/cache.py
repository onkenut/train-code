import os
import logging
from typing import Optional, Any
from pathlib import Path

from cachetools import LRUCache

from pixelvault.config import MEMORY_LRU_SIZE, THUMBNAIL_DIR

logger = logging.getLogger(__name__)


_thumbnail_cache = LRUCache(maxsize=MEMORY_LRU_SIZE)
_clip_text_cache = LRUCache(maxsize=500)


def get_thumbnail_cache() -> LRUCache:
    return _thumbnail_cache


def get_clip_text_cache() -> LRUCache:
    return _clip_text_cache


def cache_thumbnail(asset_id: int, thumb_path: str) -> None:
    _thumbnail_cache[asset_id] = thumb_path


def get_cached_thumbnail(asset_id: int) -> Optional[str]:
    return _thumbnail_cache.get(asset_id)


def cache_clip_text(text: str, vector) -> None:
    _clip_text_cache[text] = vector


def get_cached_clip_text(text: str):
    return _clip_text_cache.get(text)


def clear_all_caches() -> None:
    _thumbnail_cache.clear()
    _clip_text_cache.clear()


def cleanup_disk_cache(max_age_days: int = 30) -> int:
    import time
    if not THUMBNAIL_DIR.exists():
        return 0

    now = time.time()
    count = 0

    for f in THUMBNAIL_DIR.iterdir():
        if f.is_file():
            age = (now - f.stat().st_mtime) / 86400
            if age > max_age_days:
                try:
                    f.unlink()
                    count += 1
                except Exception:
                    pass

    logger.info(f"Cleaned up {count} old thumbnails")
    return count


def get_cache_stats() -> dict:
    return {
        "thumbnail_cache_size": len(_thumbnail_cache),
        "clip_text_cache_size": len(_clip_text_cache),
        "thumbnail_disk_count": len(list(THUMBNAIL_DIR.iterdir())) if THUMBNAIL_DIR.exists() else 0,
        "thumbnail_disk_size_mb": sum(
            f.stat().st_size for f in THUMBNAIL_DIR.iterdir() if f.is_file()
        ) / (1024 * 1024) if THUMBNAIL_DIR.exists() else 0,
    }
