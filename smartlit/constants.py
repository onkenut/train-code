from enum import Enum


class ReadingStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    DEEP_READ = "deep_read"


class AnnotationType(str, Enum):
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    TEXT_BOX = "text_box"


class FolderType(str, Enum):
    STATIC = "static"
    VIRTUAL = "virtual"


READING_STATUS_LABELS = {
    ReadingStatus.UNREAD: "未读",
    ReadingStatus.READ: "已读",
    ReadingStatus.DEEP_READ: "精读",
}


ANNOTATION_COLORS = [
    "#FFEB3B",
    "#4CAF50",
    "#2196F3",
    "#9C27B0",
    "#F44336",
    "#FF9800",
]


DEFAULT_TAG_COLORS = [
    "#E91E63",
    "#9C27B0",
    "#673AB7",
    "#3F51B5",
    "#2196F3",
    "#03A9F4",
    "#00BCD4",
    "#009688",
    "#4CAF50",
    "#8BC34A",
    "#CDDC39",
    "#FFEB3B",
    "#FFC107",
    "#FF9800",
    "#FF5722",
    "#795548",
    "#9E9E9E",
    "#607D8B",
]
