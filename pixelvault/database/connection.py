import sqlite3
import threading
from pathlib import Path
from typing import Optional

from pixelvault.config import DB_PATH, DB_WAL_MODE, DB_BUSY_TIMEOUT, DATA_DIR


_local = threading.local()


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL" if DB_WAL_MODE else "PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-65536")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT}")
    conn.execute("PRAGMA foreign_keys=ON")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        path = db_path or str(DB_PATH)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _init_db(conn)
        _local.conn = conn
    return _local.conn


def close_connection() -> None:
    if hasattr(_local, "conn") and _local.conn is not None:
        _local.conn.close()
        _local.conn = None


def initialize_database(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS libraries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            directory_path TEXT NOT NULL UNIQUE,
            monitoring_enabled INTEGER NOT NULL DEFAULT 1,
            last_scan_time TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            absolute_path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            extension TEXT NOT NULL,
            file_size INTEGER NOT NULL DEFAULT 0,
            modified_time TEXT,
            md5_hash TEXT,
            perceptual_hash TEXT,
            media_type TEXT NOT NULL DEFAULT 'image',
            width INTEGER,
            height INTEGER,
            duration REAL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (library_id) REFERENCES libraries(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_assets_path ON assets(absolute_path);
        CREATE INDEX IF NOT EXISTS idx_assets_modified ON assets(modified_time);
        CREATE INDEX IF NOT EXISTS idx_assets_hash ON assets(md5_hash);
        CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
        CREATE INDEX IF NOT EXISTS idx_assets_media_type ON assets(media_type);
        CREATE INDEX IF NOT EXISTS idx_assets_library ON assets(library_id);

        CREATE TABLE IF NOT EXISTS metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL UNIQUE,
            exif_json TEXT,
            gps_longitude REAL,
            gps_latitude REAL,
            dominant_colors_json TEXT,
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_metadata_asset ON metadata(asset_id);

        CREATE TABLE IF NOT EXISTS clip_vectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            vector_type TEXT NOT NULL DEFAULT 'image',
            frame_index INTEGER DEFAULT 0,
            vector_data BLOB NOT NULL,
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_clip_vectors_asset ON clip_vectors(asset_id);

        CREATE TABLE IF NOT EXISTS faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            person_group_id INTEGER,
            bbox_json TEXT,
            feature_vector BLOB,
            confidence REAL DEFAULT 0.0,
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
            FOREIGN KEY (person_group_id) REFERENCES persons(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_faces_asset ON faces(asset_id);
        CREATE INDEX IF NOT EXISTS idx_faces_person ON faces(person_group_id);

        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'unnamed',
            representative_face_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL DEFAULT 'scene'
        );

        CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);

        CREATE TABLE IF NOT EXISTS asset_tags (
            asset_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            confidence REAL DEFAULT 0.0,
            PRIMARY KEY (asset_id, tag_id),
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(
            absolute_path,
            filename,
            content='assets',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS assets_ai AFTER INSERT ON assets BEGIN
            INSERT INTO assets_fts(rowid, absolute_path, filename)
            VALUES (new.id, new.absolute_path, new.filename);
        END;

        CREATE TRIGGER IF NOT EXISTS assets_ad AFTER DELETE ON assets BEGIN
            INSERT INTO assets_fts(assets_fts, rowid, absolute_path, filename)
            VALUES ('delete', old.id, old.absolute_path, old.filename);
        END;

        CREATE TRIGGER IF NOT EXISTS assets_au AFTER UPDATE ON assets BEGIN
            INSERT INTO assets_fts(assets_fts, rowid, absolute_path, filename)
            VALUES ('delete', old.id, old.absolute_path, old.filename);
            INSERT INTO assets_fts(rowid, absolute_path, filename)
            VALUES (new.id, new.absolute_path, new.filename);
        END;
    """)
    conn.commit()
