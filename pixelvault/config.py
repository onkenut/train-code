import os
import tempfile
from pathlib import Path

APP_NAME = "PixelVault"
APP_VERSION = "0.1.0"
APP_ORG = "PixelVault"

DATA_DIR = Path(os.environ.get("PIXELVAULT_DATA_DIR", Path.home() / ".pixelvault"))
DB_PATH = DATA_DIR / "pixelvault.db"
THUMBNAIL_DIR = Path(tempfile.gettempdir()) / "pixelvault_thumbnails"
MODEL_DIR = Path(os.environ.get("PIXELVAULT_MODEL_DIR", Path(__file__).parent.parent / "models"))

DB_WAL_MODE = True
DB_BUSY_TIMEOUT = 30000

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".heic", ".heif", ".avif", ".svg"}
SUPPORTED_VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp"}
SUPPORTED_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"}
SUPPORTED_EXTS = SUPPORTED_IMAGE_EXTS | SUPPORTED_VIDEO_EXTS | SUPPORTED_AUDIO_EXTS

THUMB_SMALL = (128, 128)
THUMB_MEDIUM = (512, 512)
THUMB_LARGE = (1920, 1080)

SCAN_BATCH_SIZE = 100
AI_BATCH_SIZE = 16
SCAN_INTERVAL_SECONDS = 300

MEMORY_LRU_SIZE = 2000
CLIP_VECTOR_DIM = 512
FACE_VECTOR_DIM = 512
PHASH_THRESHOLD = 0.85

MAX_MEMORY_MB = 500
AI_PEAK_MEMORY_MB = 2048

SCENE_TAGS = [
    "indoor", "outdoor", "landscape", "portrait", "animal", "architecture",
    "food", "vehicle", "nature", "sky", "water", "night", "sunset", "beach",
    "mountain", "forest", "city", "street", "room", "garden", "snow", "rain",
]

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_INDEXED = "indexed"
STATUS_CORRUPT = "corrupt"
STATUS_ARCHIVED = "archived"
