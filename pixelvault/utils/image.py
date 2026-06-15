import os
import logging
from typing import Optional, Tuple, List

import numpy as np

logger = logging.getLogger(__name__)


def load_image(filepath: str, max_size: Optional[int] = None) -> Optional[np.ndarray]:
    try:
        import cv2
        img = cv2.imread(filepath)
        if img is None:
            return None
        if max_size:
            h, w = img.shape[:2]
            if max(h, w) > max_size:
                scale = max_size / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        return img
    except Exception as e:
        logger.error(f"Failed to load image {filepath}: {e}")
        return None


def get_image_dimensions(filepath: str) -> Optional[Tuple[int, int]]:
    try:
        from PIL import Image
        with Image.open(filepath) as img:
            return img.size
    except Exception:
        try:
            import cv2
            img = cv2.imread(filepath)
            if img is not None:
                h, w = img.shape[:2]
                return (w, h)
        except Exception:
            pass
    return None


def is_image_corrupted(filepath: str) -> bool:
    try:
        from PIL import Image
        with Image.open(filepath) as img:
            img.verify()
        return False
    except Exception:
        return True


def convert_heic_to_jpg(heic_path: str, output_path: Optional[str] = None) -> Optional[str]:
    try:
        from PIL import Image
        import pillow_heif
        pillow_heif.register_heif_opener()

        img = Image.open(heic_path)
        if output_path is None:
            output_path = os.path.splitext(heic_path)[0] + ".jpg"
        img.convert("RGB").save(output_path, "JPEG", quality=95)
        return output_path
    except Exception as e:
        logger.error(f"HEIC conversion failed: {e}")
        return None


def batch_resize(files: List[str], output_dir: str, max_size: int = 1920, quality: int = 85) -> List[str]:
    from PIL import Image
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for filepath in files:
        try:
            with Image.open(filepath) as img:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                name = os.path.splitext(os.path.basename(filepath))[0] + ".webp"
                out_path = os.path.join(output_dir, name)
                img.save(out_path, "WEBP", quality=quality)
                results.append(out_path)
        except Exception as e:
            logger.warning(f"Resize failed for {filepath}: {e}")

    return results
