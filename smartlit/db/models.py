from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Paper:
    id: Optional[int] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    file_path: str = ""
    file_hash: Optional[str] = None
    page_count: Optional[int] = None
    file_size: Optional[int] = None
    reading_status: str = "unread"
    rating: int = 0
    notes: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[str] = None
    added_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_read_at: Optional[datetime] = None
    is_archived: int = 0
    abstract: Optional[str] = None
    full_text: Optional[str] = None
    tags: list[str] = field(default_factory=list)


@dataclass
class Tag:
    id: Optional[int] = None
    name: str = ""
    color: str = "#2196F3"
    created_at: Optional[datetime] = None


@dataclass
class Annotation:
    id: Optional[int] = None
    paper_id: int = 0
    page: int = 0
    annotation_type: str = "highlight"
    color: str = "#FFEB3B"
    rects: Optional[str] = None
    content: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Note:
    id: Optional[int] = None
    title: str = ""
    content: str = ""
    file_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Folder:
    id: Optional[int] = None
    name: str = ""
    parent_id: Optional[int] = None
    folder_type: str = "static"
    filter_json: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Citation:
    id: Optional[int] = None
    source_paper_id: int = 0
    target_paper_id: int = 0
    created_at: Optional[datetime] = None


@dataclass
class AICache:
    id: Optional[int] = None
    paper_id: int = 0
    cache_type: str = ""
    cache_data: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
