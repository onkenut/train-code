import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator

from ..config import get_config


class DatabaseManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._local = threading.local()
        self.db_path = get_config().db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def get_cursor(self) -> Iterator[sqlite3.Cursor]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN")
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def _init_db(self):
        with self.get_cursor() as cursor:
            cursor.executescript(_SCHEMA_SQL)


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    authors TEXT,
    year INTEGER,
    journal TEXT,
    doi TEXT,
    url TEXT,
    file_path TEXT NOT NULL UNIQUE,
    file_hash TEXT,
    page_count INTEGER,
    file_size INTEGER,
    reading_status TEXT DEFAULT 'unread',
    rating INTEGER DEFAULT 0,
    notes TEXT,
    summary TEXT,
    keywords TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_read_at TIMESTAMP,
    is_archived INTEGER DEFAULT 0,
    abstract TEXT,
    full_text TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#2196F3',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_tags (
    paper_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (paper_id, tag_id),
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER,
    folder_type TEXT DEFAULT 'static',
    filter_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS paper_folders (
    paper_id INTEGER NOT NULL,
    folder_id INTEGER NOT NULL,
    PRIMARY KEY (paper_id, folder_id),
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    page INTEGER NOT NULL,
    annotation_type TEXT NOT NULL,
    color TEXT DEFAULT '#FFEB3B',
    rects TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_notes (
    paper_id INTEGER NOT NULL,
    note_id INTEGER NOT NULL,
    PRIMARY KEY (paper_id, note_id),
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_paper_id INTEGER NOT NULL,
    target_paper_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_paper_id, target_paper_id),
    FOREIGN KEY (source_paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    FOREIGN KEY (target_paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    cache_type TEXT NOT NULL,
    cache_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(paper_id, cache_type),
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS paper_vectors (
    paper_id INTEGER PRIMARY KEY,
    vector BLOB,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    title,
    authors,
    abstract,
    full_text,
    content='papers',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS papers_ai AFTER INSERT ON papers BEGIN
    INSERT INTO papers_fts(rowid, title, authors, abstract, full_text)
    VALUES (new.id, new.title, new.authors, new.abstract, new.full_text);
END;

CREATE TRIGGER IF NOT EXISTS papers_ad AFTER DELETE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, authors, abstract, full_text)
    VALUES ('delete', old.id, old.title, old.authors, old.abstract, old.full_text);
END;

CREATE TRIGGER IF NOT EXISTS papers_au AFTER UPDATE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, authors, abstract, full_text)
    VALUES ('delete', old.id, old.title, old.authors, old.abstract, old.full_text);
    INSERT INTO papers_fts(rowid, title, authors, abstract, full_text)
    VALUES (new.id, new.title, new.authors, new.abstract, new.full_text);
END;

CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_papers_reading_status ON papers(reading_status);
CREATE INDEX IF NOT EXISTS idx_papers_rating ON papers(rating);
CREATE INDEX IF NOT EXISTS idx_papers_added_at ON papers(added_at);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_annotations_paper_page ON annotations(paper_id, page);
CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_paper_id);
CREATE INDEX IF NOT EXISTS idx_citations_target ON citations(target_paper_id);
"""


def get_db() -> DatabaseManager:
    return DatabaseManager()
