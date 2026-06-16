import os
import logging
from pathlib import Path
from typing import Optional, Tuple

from pixelvault.config import THUMB_SMALL, THUMB_MEDIUM, THUMB_LARGE, THUMBNAIL_DIR

logger = logging.getLogger(__name__)


class ThumbnailGenerator:
    def __init__(self):
        THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _thumb_path(asset_id: int, size: Tuple[int, int]) -> str:
        w, h = size
        return str(THUMBNAIL_DIR / f"{asset_id}_{w}x{h}.webp")

    def generate(self, filepath: str, asset_id: int, size: Tuple[int, int] = THUMB_SMALL) -> Optional[str]:
        out_path = self._thumb_path(asset_id, size)
        if os.path.exists(out_path):
            return out_path

        ext = Path(filepath).suffix.lower()
        if ext in {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp"}:
            return self._generate_video_thumb(filepath, asset_id, size)

        return self._generate_image_thumb(filepath, out_path, size)

    def _generate_image_thumb(self, filepath: str, out_path: str, size: Tuple[int, int]) -> Optional[str]:
        try:
            from PIL import Image
            with Image.open(filepath) as img:
                try:
                    resampler = Image.Resampling.LANCZOS
                except AttributeError:
                    resampler = Image.LANCZOS
                img.thumbnail(size, resampler)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(out_path, "WEBP", quality=85)
            return out_path
        except Exception as e:
            logger.warning(f"Thumbnail generation failed for {filepath}: {e}")
            return None

    def _generate_video_thumb(self, filepath: str, asset_id: int, size: Tuple[int, int]) -> Optional[str]:
        try:
            import ffmpeg
            out_path = self._thumb_path(asset_id, size)
            (
                ffmpeg
                .input(filepath, ss=1)
                .filter("scale", size[0], size[1], force_original_aspect_ratio="decrease")
                .output(out_path, vframes=1, format="image2", vcodec="webp")
                .overwrite_output()
                .run(quiet=True)
            )
            if os.path.exists(out_path):
                return out_path
            return None
        except Exception as e:
            logger.warning(f"Video thumbnail generation failed for {filepath}: {e}")
            return None

    def get_thumbnail(self, asset_id: int, size: Tuple[int, int] = THUMB_SMALL) -> Optional[str]:
        out_path = self._thumb_path(asset_id, size)
        if os.path.exists(out_path):
            return out_path
        return None

    def get_or_generate(self, filepath: str, asset_id: int, size: Tuple[int, int] = THUMB_SMALL) -> Optional[str]:
        existing = self.get_thumbnail(asset_id, size)
        if existing:
            return existing
        return self.generate(filepath, asset_id, size)

    def cleanup_old_thumbnails(self, max_age_days: int = 30) -> int:
        import time
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
        return count
