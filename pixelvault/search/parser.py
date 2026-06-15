import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class ParsedQuery:
    semantic_text: str = ""
    media_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    min_width: Optional[int] = None
    min_height: Optional[int] = None
    camera_model: Optional[str] = None
    color: Optional[str] = None
    person_name: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    filename_pattern: Optional[str] = None
    has_semantic: bool = False


class QueryParser:
    FILTER_PATTERNS = [
        (re.compile(r'\btype:(image|video|audio)\b', re.I), "media_type"),
        (re.compile(r'\bafter:(\d{4}-\d{2}-\d{2})\b'), "date_from"),
        (re.compile(r'\bbefore:(\d{4}-\d{2}-\d{2})\b'), "date_to"),
        (re.compile(r'\byear:(\d{4})\b'), "year"),
        (re.compile(r'\bminw:(\d+)\b'), "min_width"),
        (re.compile(r'\bminh:(\d+)\b'), "min_height"),
        (re.compile(r'\bcamera:([^\s]+)\b'), "camera_model"),
        (re.compile(r'\bcolor:([^\s]+)\b'), "color"),
        (re.compile(r'\bperson:([^\s]+)\b'), "person_name"),
        (re.compile(r'\btag:([^\s]+)\b'), "tag"),
    ]

    def parse(self, query: str) -> ParsedQuery:
        parsed = ParsedQuery()
        remaining = query

        for pattern, field_name in self.FILTER_PATTERNS:
            matches = list(pattern.finditer(remaining))
            for match in reversed(matches):
                if field_name == "media_type":
                    parsed.media_type = match.group(1).lower()
                elif field_name == "date_from":
                    parsed.date_from = match.group(1)
                elif field_name == "date_to":
                    parsed.date_to = match.group(1)
                elif field_name == "year":
                    parsed.date_from = f"{match.group(1)}-01-01"
                    parsed.date_to = f"{match.group(1)}-12-31"
                elif field_name == "min_width":
                    parsed.min_width = int(match.group(1))
                elif field_name == "min_height":
                    parsed.min_height = int(match.group(1))
                elif field_name == "camera_model":
                    parsed.camera_model = match.group(1)
                elif field_name == "color":
                    parsed.color = match.group(1)
                elif field_name == "person_name":
                    parsed.person_name = match.group(1)
                elif field_name == "tag":
                    parsed.tags.append(match.group(1))

                remaining = remaining[:match.start()] + remaining[match.end():]

        semantic = remaining.strip()
        if semantic:
            parsed.semantic_text = semantic
            parsed.has_semantic = True

        return parsed

    def to_fts_query(self, parsed: ParsedQuery) -> Optional[str]:
        parts = []
        if parsed.semantic_text:
            words = parsed.semantic_text.split()
            parts.extend(words)
        if parsed.filename_pattern:
            parts.append(parsed.filename_pattern)
        if not parts:
            return None
        return " OR ".join(parts)
