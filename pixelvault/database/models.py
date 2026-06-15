from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class AssetStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    CORRUPT = "corrupt"
    ARCHIVED = "archived"


@dataclass
class Library:
    id: Optional[int] = None
    directory_path: str = ""
    monitoring_enabled: bool = True
    last_scan_time: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class Asset:
    id: Optional[int] = None
    library_id: int = 0
    absolute_path: str = ""
    filename: str = ""
    extension: str = ""
    file_size: int = 0
    modified_time: Optional[str] = None
    md5_hash: Optional[str] = None
    perceptual_hash: Optional[str] = None
    media_type: str = MediaType.IMAGE
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    status: str = AssetStatus.PENDING
    created_at: Optional[str] = None


@dataclass
class Metadata:
    id: Optional[int] = None
    asset_id: int = 0
    exif_json: Optional[str] = None
    gps_longitude: Optional[float] = None
    gps_latitude: Optional[float] = None
    dominant_colors_json: Optional[str] = None


@dataclass
class ClipVector:
    id: Optional[int] = None
    asset_id: int = 0
    vector_type: str = "image"
    frame_index: int = 0
    vector_data: bytes = b""


@dataclass
class Face:
    id: Optional[int] = None
    asset_id: int = 0
    person_group_id: Optional[int] = None
    bbox_json: Optional[str] = None
    feature_vector: Optional[bytes] = None
    confidence: float = 0.0


@dataclass
class Person:
    id: Optional[int] = None
    name: str = "unnamed"
    representative_face_path: Optional[str] = None
    created_at: Optional[str] = None
    face_count: int = 0


@dataclass
class Tag:
    id: Optional[int] = None
    name: str = ""
    category: str = "scene"


@dataclass
class AssetTag:
    asset_id: int = 0
    tag_id: int = 0
    confidence: float = 0.0


@dataclass
class DuplicateGroup:
    md5_hash: str = ""
    assets: List[Asset] = field(default_factory=list)


@dataclass
class SimilarGroup:
    assets: List[Asset] = field(default_factory=list)
    similarity: float = 0.0


@dataclass
class SearchResult:
    asset_id: int = 0
    score: float = 0.0
    match_type: str = ""
