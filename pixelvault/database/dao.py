import json
import struct
from typing import Optional, List, Tuple

import numpy as np

from pixelvault.database.connection import get_connection
from pixelvault.database.models import Library, Asset, Metadata, ClipVector, Face, Person, Tag, AssetTag, DuplicateGroup


class LibraryDAO:
    def __init__(self):
        self.conn = get_connection()

    def insert(self, lib: Library) -> int:
        cur = self.conn.execute(
            "INSERT INTO libraries (directory_path, monitoring_enabled) VALUES (?, ?)",
            (lib.directory_path, int(lib.monitoring_enabled)),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_all(self) -> List[Library]:
        rows = self.conn.execute("SELECT * FROM libraries ORDER BY id").fetchall()
        return [Library(**dict(r)) for r in rows]

    def get_by_id(self, lib_id: int) -> Optional[Library]:
        row = self.conn.execute("SELECT * FROM libraries WHERE id = ?", (lib_id,)).fetchone()
        return Library(**dict(row)) if row else None

    def get_by_path(self, path: str) -> Optional[Library]:
        row = self.conn.execute("SELECT * FROM libraries WHERE directory_path = ?", (path,)).fetchone()
        return Library(**dict(row)) if row else None

    def update_scan_time(self, lib_id: int) -> None:
        self.conn.execute(
            "UPDATE libraries SET last_scan_time = datetime('now') WHERE id = ?",
            (lib_id,),
        )
        self.conn.commit()

    def delete(self, lib_id: int) -> None:
        self.conn.execute("DELETE FROM libraries WHERE id = ?", (lib_id,))
        self.conn.commit()


class AssetDAO:
    def __init__(self):
        self.conn = get_connection()

    def insert(self, asset: Asset) -> int:
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO assets
            (library_id, absolute_path, filename, extension, file_size, modified_time,
             md5_hash, perceptual_hash, media_type, width, height, duration, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (asset.library_id, asset.absolute_path, asset.filename, asset.extension,
             asset.file_size, asset.modified_time, asset.md5_hash, asset.perceptual_hash,
             asset.media_type, asset.width, asset.height, asset.duration, asset.status),
        )
        self.conn.commit()
        return cur.lastrowid

    def insert_batch(self, assets: List[Asset]) -> List[int]:
        ids = []
        for a in assets:
            cur = self.conn.execute(
                """INSERT OR IGNORE INTO assets
                (library_id, absolute_path, filename, extension, file_size, modified_time,
                 md5_hash, perceptual_hash, media_type, width, height, duration, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (a.library_id, a.absolute_path, a.filename, a.extension,
                 a.file_size, a.modified_time, a.md5_hash, a.perceptual_hash,
                 a.media_type, a.width, a.height, a.duration, a.status),
            )
            if cur.lastrowid:
                ids.append(cur.lastrowid)
        self.conn.commit()
        return ids

    def get_by_id(self, asset_id: int) -> Optional[Asset]:
        row = self.conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        return Asset(**dict(row)) if row else None

    def get_by_path(self, path: str) -> Optional[Asset]:
        row = self.conn.execute("SELECT * FROM assets WHERE absolute_path = ?", (path,)).fetchone()
        return Asset(**dict(row)) if row else None

    def get_pending(self, limit: int = 100) -> List[Asset]:
        rows = self.conn.execute(
            "SELECT * FROM assets WHERE status = 'pending' LIMIT ?", (limit,)
        ).fetchall()
        return [Asset(**dict(r)) for r in rows]

    def update_status(self, asset_id: int, status: str) -> None:
        self.conn.execute("UPDATE assets SET status = ? WHERE id = ?", (status, asset_id))
        self.conn.commit()

    def update_hash(self, asset_id: int, md5_hash: str, perceptual_hash: str) -> None:
        self.conn.execute(
            "UPDATE assets SET md5_hash = ?, perceptual_hash = ? WHERE id = ?",
            (md5_hash, perceptual_hash, asset_id),
        )
        self.conn.commit()

    def update_dimensions(self, asset_id: int, width: int, height: int) -> None:
        self.conn.execute(
            "UPDATE assets SET width = ?, height = ? WHERE id = ?",
            (width, height, asset_id),
        )
        self.conn.commit()

    def update_duration(self, asset_id: int, duration: float) -> None:
        self.conn.execute(
            "UPDATE assets SET duration = ? WHERE id = ?",
            (duration, asset_id),
        )
        self.conn.commit()

    def find_duplicates_by_hash(self) -> List[DuplicateGroup]:
        rows = self.conn.execute(
            """SELECT md5_hash, GROUP_CONCAT(id) as ids, COUNT(*) as cnt
            FROM assets WHERE md5_hash IS NOT NULL AND status != 'corrupt'
            GROUP BY md5_hash HAVING cnt > 1"""
        ).fetchall()
        groups = []
        for r in rows:
            asset_ids = [int(x) for x in r["ids"].split(",")]
            assets = [self.get_by_id(aid) for aid in asset_ids]
            assets = [a for a in assets if a is not None]
            groups.append(DuplicateGroup(md5_hash=r["md5_hash"], assets=assets))
        return groups

    def search_fts(self, query: str, limit: int = 100) -> List[Asset]:
        rows = self.conn.execute(
            """SELECT a.* FROM assets a
            JOIN assets_fts fts ON a.id = fts.rowid
            WHERE assets_fts MATCH ?
            ORDER BY rank LIMIT ?""",
            (query, limit),
        ).fetchall()
        return [Asset(**dict(r)) for r in rows]

    def search_filtered(
        self,
        media_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        min_width: Optional[int] = None,
        min_height: Optional[int] = None,
        camera_model: Optional[str] = None,
        limit: int = 100,
    ) -> List[Asset]:
        sql = "SELECT a.* FROM assets a"
        params = []
        joins = []
        conditions = []

        if camera_model:
            joins.append("JOIN metadata m ON a.id = m.asset_id")
            conditions.append("m.exif_json LIKE ?")
            params.append(f'%{camera_model}%')

        if media_type:
            conditions.append("a.media_type = ?")
            params.append(media_type)
        if date_from:
            conditions.append("a.modified_time >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("a.modified_time <= ?")
            params.append(date_to)
        if min_width:
            conditions.append("a.width >= ?")
            params.append(min_width)
        if min_height:
            conditions.append("a.height >= ?")
            params.append(min_height)

        sql += " ".join(joins)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY a.modified_time DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [Asset(**dict(r)) for r in rows]

    def get_by_library(self, library_id: int, limit: int = 1000) -> List[Asset]:
        rows = self.conn.execute(
            "SELECT * FROM assets WHERE library_id = ? ORDER BY modified_time DESC LIMIT ?",
            (library_id, limit),
        ).fetchall()
        return [Asset(**dict(r)) for r in rows]

    def delete(self, asset_id: int) -> None:
        self.conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        self.conn.commit()


class MetadataDAO:
    def __init__(self):
        self.conn = get_connection()

    def insert(self, meta: Metadata) -> int:
        cur = self.conn.execute(
            """INSERT OR REPLACE INTO metadata
            (asset_id, exif_json, gps_longitude, gps_latitude, dominant_colors_json)
            VALUES (?, ?, ?, ?, ?)""",
            (meta.asset_id, meta.exif_json, meta.gps_longitude,
             meta.gps_latitude, meta.dominant_colors_json),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_by_asset(self, asset_id: int) -> Optional[Metadata]:
        row = self.conn.execute(
            "SELECT * FROM metadata WHERE asset_id = ?", (asset_id,)
        ).fetchone()
        return Metadata(**dict(row)) if row else None

    def get_exif(self, asset_id: int) -> dict:
        meta = self.get_by_asset(asset_id)
        if meta and meta.exif_json:
            return json.loads(meta.exif_json)
        return {}

    def search_by_camera(self, camera_model: str, limit: int = 100) -> List[int]:
        rows = self.conn.execute(
            """SELECT asset_id FROM metadata
            WHERE exif_json LIKE ? LIMIT ?""",
            (f'%{camera_model}%', limit),
        ).fetchall()
        return [r["asset_id"] for r in rows]

    def search_by_gps_area(
        self, lon: float, lat: float, radius: float, limit: int = 100
    ) -> List[int]:
        rows = self.conn.execute(
            """SELECT asset_id FROM metadata
            WHERE gps_longitude BETWEEN ? AND ?
            AND gps_latitude BETWEEN ? AND ?
            LIMIT ?""",
            (lon - radius, lon + radius, lat - radius, lat + radius, limit),
        ).fetchall()
        return [r["asset_id"] for r in rows]

    def search_by_color(self, color_hex: str, limit: int = 100) -> List[int]:
        rows = self.conn.execute(
            """SELECT asset_id FROM metadata
            WHERE dominant_colors_json LIKE ? LIMIT ?""",
            (f'%{color_hex}%', limit),
        ).fetchall()
        return [r["asset_id"] for r in rows]


class ClipVectorDAO:
    def __init__(self):
        self.conn = get_connection()

    @staticmethod
    def _serialize_vector(vec: np.ndarray) -> bytes:
        return struct.pack(f"{len(vec)}f", *vec)

    @staticmethod
    def _deserialize_vector(data: bytes) -> np.ndarray:
        count = len(data) // 4
        return np.array(struct.unpack(f"{count}f", data), dtype=np.float32)

    def insert(self, vec: ClipVector) -> int:
        data = self._serialize_vector(vec.vector_data) if isinstance(vec.vector_data, np.ndarray) else vec.vector_data
        cur = self.conn.execute(
            """INSERT INTO clip_vectors (asset_id, vector_type, frame_index, vector_data)
            VALUES (?, ?, ?, ?)""",
            (vec.asset_id, vec.vector_type, vec.frame_index, data),
        )
        self.conn.commit()
        return cur.lastrowid

    def insert_batch(self, vectors: List[ClipVector]) -> List[int]:
        ids = []
        for v in vectors:
            data = self._serialize_vector(v.vector_data) if isinstance(v.vector_data, np.ndarray) else v.vector_data
            cur = self.conn.execute(
                """INSERT INTO clip_vectors (asset_id, vector_type, frame_index, vector_data)
                VALUES (?, ?, ?, ?)""",
                (v.asset_id, v.vector_type, v.frame_index, data),
            )
            ids.append(cur.lastrowid)
        self.conn.commit()
        return ids

    def get_by_asset(self, asset_id: int) -> List[Tuple[ClipVector, np.ndarray]]:
        rows = self.conn.execute(
            "SELECT * FROM clip_vectors WHERE asset_id = ?", (asset_id,)
        ).fetchall()
        result = []
        for r in rows:
            cv = ClipVector(**dict(r))
            vec = self._deserialize_vector(r["vector_data"])
            result.append((cv, vec))
        return result

    def get_all_vectors(self, vector_type: str = "image") -> List[Tuple[int, np.ndarray]]:
        rows = self.conn.execute(
            "SELECT asset_id, vector_data FROM clip_vectors WHERE vector_type = ?",
            (vector_type,),
        ).fetchall()
        return [(r["asset_id"], self._deserialize_vector(r["vector_data"])) for r in rows]

    def search_similar(
        self, query_vector: np.ndarray, top_k: int = 50, vector_type: str = "image"
    ) -> List[Tuple[int, float]]:
        query_norm = query_vector / (np.linalg.norm(query_vector) + 1e-8)
        all_vectors = self.get_all_vectors(vector_type)
        if not all_vectors:
            return []

        asset_ids = [v[0] for v in all_vectors]
        matrix = np.array([v[1] for v in all_vectors])
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8
        matrix_norm = matrix / norms
        similarities = matrix_norm @ query_norm
        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [(asset_ids[i], float(similarities[i])) for i in top_indices]

    def delete_by_asset(self, asset_id: int) -> None:
        self.conn.execute("DELETE FROM clip_vectors WHERE asset_id = ?", (asset_id,))
        self.conn.commit()


class FaceDAO:
    def __init__(self):
        self.conn = get_connection()

    @staticmethod
    def _serialize_vector(vec: np.ndarray) -> bytes:
        return struct.pack(f"{len(vec)}f", *vec)

    @staticmethod
    def _deserialize_vector(data: bytes) -> np.ndarray:
        count = len(data) // 4
        return np.array(struct.unpack(f"{count}f", data), dtype=np.float32)

    def insert(self, face: Face) -> int:
        fv = self._serialize_vector(face.feature_vector) if isinstance(face.feature_vector, np.ndarray) else face.feature_vector
        cur = self.conn.execute(
            """INSERT INTO faces (asset_id, person_group_id, bbox_json, feature_vector, confidence)
            VALUES (?, ?, ?, ?, ?)""",
            (face.asset_id, face.person_group_id, face.bbox_json, fv, face.confidence),
        )
        self.conn.commit()
        return cur.lastrowid

    def insert_batch(self, faces: List[Face]) -> List[int]:
        ids = []
        for f in faces:
            fv = self._serialize_vector(f.feature_vector) if isinstance(f.feature_vector, np.ndarray) else f.feature_vector
            cur = self.conn.execute(
                """INSERT INTO faces (asset_id, person_group_id, bbox_json, feature_vector, confidence)
                VALUES (?, ?, ?, ?, ?)""",
                (f.asset_id, f.person_group_id, f.bbox_json, fv, f.confidence),
            )
            ids.append(cur.lastrowid)
        self.conn.commit()
        return ids

    def get_by_asset(self, asset_id: int) -> List[Face]:
        rows = self.conn.execute(
            "SELECT * FROM faces WHERE asset_id = ?", (asset_id,)
        ).fetchall()
        return [Face(**dict(r)) for r in rows]

    def get_unassigned(self, limit: int = 1000) -> List[Tuple[Face, np.ndarray]]:
        rows = self.conn.execute(
            "SELECT * FROM faces WHERE person_group_id IS NULL LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for r in rows:
            face = Face(**dict(r))
            vec = self._deserialize_vector(r["feature_vector"]) if r["feature_vector"] else np.array([])
            result.append((face, vec))
        return result

    def get_all_vectors(self) -> List[Tuple[int, np.ndarray]]:
        rows = self.conn.execute(
            "SELECT id, feature_vector FROM faces WHERE feature_vector IS NOT NULL"
        ).fetchall()
        return [(r["id"], self._deserialize_vector(r["feature_vector"])) for r in rows]

    def assign_person(self, face_id: int, person_group_id: int) -> None:
        self.conn.execute(
            "UPDATE faces SET person_group_id = ? WHERE id = ?",
            (person_group_id, face_id),
        )
        self.conn.commit()

    def assign_person_batch(self, face_ids: List[int], person_group_id: int) -> None:
        placeholders = ",".join("?" * len(face_ids))
        self.conn.execute(
            f"UPDATE faces SET person_group_id = ? WHERE id IN ({placeholders})",
            [person_group_id] + face_ids,
        )
        self.conn.commit()

    def delete_by_asset(self, asset_id: int) -> None:
        self.conn.execute("DELETE FROM faces WHERE asset_id = ?", (asset_id,))
        self.conn.commit()


class PersonDAO:
    def __init__(self):
        self.conn = get_connection()

    def insert(self, person: Person) -> int:
        cur = self.conn.execute(
            "INSERT INTO persons (name, representative_face_path) VALUES (?, ?)",
            (person.name, person.representative_face_path),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_all(self) -> List[Person]:
        rows = self.conn.execute(
            """SELECT p.*, COUNT(f.id) as face_count FROM persons p
            LEFT JOIN faces f ON p.id = f.person_group_id
            GROUP BY p.id ORDER BY p.name"""
        ).fetchall()
        return [Person(**dict(r)) for r in rows]

    def get_by_id(self, person_id: int) -> Optional[Person]:
        row = self.conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
        return Person(**dict(row)) if row else None

    def rename(self, person_id: int, name: str) -> None:
        self.conn.execute("UPDATE persons SET name = ? WHERE id = ?", (name, person_id))
        self.conn.commit()

    def merge(self, source_id: int, target_id: int) -> None:
        self.conn.execute(
            "UPDATE faces SET person_group_id = ? WHERE person_group_id = ?",
            (target_id, source_id),
        )
        self.conn.execute("DELETE FROM persons WHERE id = ?", (source_id,))
        self.conn.commit()

    def delete(self, person_id: int) -> None:
        self.conn.execute("UPDATE faces SET person_group_id = NULL WHERE person_group_id = ?", (person_id,))
        self.conn.execute("DELETE FROM persons WHERE id = ?", (person_id,))
        self.conn.commit()


class TagDAO:
    def __init__(self):
        self.conn = get_connection()

    def insert(self, tag: Tag) -> int:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO tags (name, category) VALUES (?, ?)",
            (tag.name, tag.category),
        )
        self.conn.commit()
        return cur.lastrowid

    def insert_batch(self, tags: List[Tag]) -> List[int]:
        ids = []
        for t in tags:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO tags (name, category) VALUES (?, ?)",
                (t.name, t.category),
            )
            if cur.lastrowid:
                ids.append(cur.lastrowid)
            else:
                existing = self.conn.execute("SELECT id FROM tags WHERE name = ?", (t.name,)).fetchone()
                if existing:
                    ids.append(existing["id"])
        self.conn.commit()
        return ids

    def get_all(self) -> List[Tag]:
        rows = self.conn.execute("SELECT * FROM tags ORDER BY category, name").fetchall()
        return [Tag(**dict(r)) for r in rows]

    def get_by_category(self, category: str) -> List[Tag]:
        rows = self.conn.execute("SELECT * FROM tags WHERE category = ?", (category,)).fetchall()
        return [Tag(**dict(r)) for r in rows]

    def get_by_asset(self, asset_id: int) -> List[Tuple[Tag, float]]:
        rows = self.conn.execute(
            """SELECT t.*, at.confidence FROM tags t
            JOIN asset_tags at ON t.id = at.tag_id
            WHERE at.asset_id = ?""",
            (asset_id,),
        ).fetchall()
        return [(Tag(id=r["id"], name=r["name"], category=r["category"]), r["confidence"]) for r in rows]


class AssetTagDAO:
    def __init__(self):
        self.conn = get_connection()

    def assign(self, asset_id: int, tag_id: int, confidence: float = 1.0) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO asset_tags (asset_id, tag_id, confidence) VALUES (?, ?, ?)",
            (asset_id, tag_id, confidence),
        )
        self.conn.commit()

    def assign_batch(self, pairs: List[Tuple[int, int, float]]) -> None:
        self.conn.executemany(
            "INSERT OR REPLACE INTO asset_tags (asset_id, tag_id, confidence) VALUES (?, ?, ?)",
            pairs,
        )
        self.conn.commit()

    def remove(self, asset_id: int, tag_id: int) -> None:
        self.conn.execute(
            "DELETE FROM asset_tags WHERE asset_id = ? AND tag_id = ?",
            (asset_id, tag_id),
        )
        self.conn.commit()

    def search_by_tag(self, tag_id: int, limit: int = 100) -> List[int]:
        rows = self.conn.execute(
            "SELECT asset_id FROM asset_tags WHERE tag_id = ? ORDER BY confidence DESC LIMIT ?",
            (tag_id, limit),
        ).fetchall()
        return [r["asset_id"] for r in rows]
