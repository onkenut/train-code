import json
from datetime import datetime
from typing import Optional

from .database import get_db
from .models import Paper, Tag, Annotation, Note, Folder, Citation


class BaseRepository:
    def __init__(self):
        self.db = get_db()


class PaperRepository(BaseRepository):
    def get_all(self, include_archived: bool = False, limit: int = 100, offset: int = 0) -> list[Paper]:
        query = "SELECT * FROM papers WHERE is_archived = ? ORDER BY added_at DESC LIMIT ? OFFSET ?"
        params = (0 if not include_archived else 1, limit, offset)
        if include_archived == "all":
            query = "SELECT * FROM papers ORDER BY added_at DESC LIMIT ? OFFSET ?"
            params = (limit, offset)
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            papers = [self._row_to_paper(row) for row in rows]
            for paper in papers:
                paper.tags = self._get_paper_tags(paper.id)
            return papers

    def get_by_id(self, paper_id: int) -> Optional[Paper]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM papers WHERE id = ?", (paper_id,))
            row = cursor.fetchone()
            if row:
                paper = self._row_to_paper(row)
                paper.tags = self._get_paper_tags(paper.id)
                return paper
        return None

    def get_by_file_path(self, file_path: str) -> Optional[Paper]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM papers WHERE file_path = ?", (file_path,))
            row = cursor.fetchone()
            if row:
                paper = self._row_to_paper(row)
                paper.tags = self._get_paper_tags(paper.id)
                return paper
        return None

    def get_by_doi(self, doi: str) -> Optional[Paper]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM papers WHERE doi = ?", (doi,))
            row = cursor.fetchone()
            if row:
                paper = self._row_to_paper(row)
                paper.tags = self._get_paper_tags(paper.id)
                return paper
        return None

    def create(self, paper: Paper) -> Paper:
        with self.db.transaction() as cursor:
            cursor.execute("""
                INSERT INTO papers (title, authors, year, journal, doi, url, file_path,
                                   file_hash, page_count, file_size, reading_status,
                                   rating, notes, summary, keywords, abstract, full_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                paper.title, paper.authors, paper.year, paper.journal, paper.doi,
                paper.url, paper.file_path, paper.file_hash, paper.page_count,
                paper.file_size, paper.reading_status, paper.rating, paper.notes,
                paper.summary, paper.keywords, paper.abstract, paper.full_text
            ))
            paper.id = cursor.lastrowid
            if paper.tags:
                self._set_paper_tags(cursor, paper.id, paper.tags)
        return paper

    def update(self, paper: Paper) -> Paper:
        with self.db.transaction() as cursor:
            cursor.execute("""
                UPDATE papers SET title=?, authors=?, year=?, journal=?, doi=?, url=?,
                       file_path=?, file_hash=?, page_count=?, file_size=?,
                       reading_status=?, rating=?, notes=?, summary=?, keywords=?,
                       updated_at=CURRENT_TIMESTAMP, abstract=?, full_text=?, is_archived=?
                WHERE id = ?
            """, (
                paper.title, paper.authors, paper.year, paper.journal, paper.doi,
                paper.url, paper.file_path, paper.file_hash, paper.page_count,
                paper.file_size, paper.reading_status, paper.rating, paper.notes,
                paper.summary, paper.keywords, paper.abstract, paper.full_text,
                paper.is_archived, paper.id
            ))
            self._set_paper_tags(cursor, paper.id, paper.tags)
        return paper

    def delete(self, paper_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute("DELETE FROM papers WHERE id = ?", (paper_id,))

    def count(self, include_archived: bool = False) -> int:
        with self.db.get_cursor() as cursor:
            if include_archived:
                cursor.execute("SELECT COUNT(*) FROM papers")
            else:
                cursor.execute("SELECT COUNT(*) FROM papers WHERE is_archived = 0")
            return cursor.fetchone()[0]

    def update_reading_status(self, paper_id: int, status: str) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE papers SET reading_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, paper_id)
            )

    def update_rating(self, paper_id: int, rating: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE papers SET rating = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (rating, paper_id)
            )

    def update_last_read(self, paper_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE papers SET last_read_at = CURRENT_TIMESTAMP WHERE id = ?",
                (paper_id,)
            )

    def toggle_archive(self, paper_id: int) -> bool:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT is_archived FROM papers WHERE id = ?", (paper_id,))
            current = cursor.fetchone()[0]
            new_val = 0 if current else 1
            cursor.execute(
                "UPDATE papers SET is_archived = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_val, paper_id)
            )
            return bool(new_val)

    def filter_papers(
        self,
        tag_ids: list[int] | None = None,
        tag_logic: str = "AND",
        reading_status: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        rating_min: int | None = None,
        author: str | None = None,
        sort_by: str = "added_at",
        sort_order: str = "DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        query = "SELECT DISTINCT p.* FROM papers p"
        conditions = []
        params: list = []

        if tag_ids:
            query += " JOIN paper_tags pt ON p.id = pt.paper_id"
            placeholders = ",".join(["?"] * len(tag_ids))
            conditions.append(f"pt.tag_id IN ({placeholders})")
            params.extend(tag_ids)
            if tag_logic == "AND":
                query += f"""
                    WHERE p.id IN (
                        SELECT paper_id FROM paper_tags
                        WHERE tag_id IN ({placeholders})
                        GROUP BY paper_id HAVING COUNT(DISTINCT tag_id) = ?
                    )
                """.replace("?", "?", 1)
                params.append(len(tag_ids))

        if reading_status:
            conditions.append("p.reading_status = ?")
            params.append(reading_status)
        if year_min:
            conditions.append("p.year >= ?")
            params.append(year_min)
        if year_max:
            conditions.append("p.year <= ?")
            params.append(year_max)
        if rating_min:
            conditions.append("p.rating >= ?")
            params.append(rating_min)
        if author:
            conditions.append("p.authors LIKE ?")
            params.append(f"%{author}%")

        if conditions:
            if tag_ids and tag_logic == "AND":
                query += " AND " + " AND ".join(conditions)
            else:
                query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY p.{sort_by} {sort_order} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            papers = [self._row_to_paper(row) for row in rows]
            for paper in papers:
                paper.tags = self._get_paper_tags(paper.id)
            return papers

    def get_year_distribution(self) -> dict[int, int]:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT year, COUNT(*) as cnt FROM papers WHERE year IS NOT NULL GROUP BY year ORDER BY year"
            )
            rows = cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    def get_reading_status_distribution(self) -> dict[str, int]:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT reading_status, COUNT(*) as cnt FROM papers GROUP BY reading_status"
            )
            rows = cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    def _row_to_paper(self, row) -> Paper:
        return Paper(
            id=row["id"],
            title=row["title"],
            authors=row["authors"],
            year=row["year"],
            journal=row["journal"],
            doi=row["doi"],
            url=row["url"],
            file_path=row["file_path"],
            file_hash=row["file_hash"],
            page_count=row["page_count"],
            file_size=row["file_size"],
            reading_status=row["reading_status"],
            rating=row["rating"],
            notes=row["notes"],
            summary=row["summary"],
            keywords=row["keywords"],
            added_at=row["added_at"],
            updated_at=row["updated_at"],
            last_read_at=row["last_read_at"],
            is_archived=row["is_archived"],
            abstract=row["abstract"],
            full_text=row["full_text"],
        )

    def _get_paper_tags(self, paper_id: int | None) -> list[str]:
        if paper_id is None:
            return []
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT t.name FROM tags t
                JOIN paper_tags pt ON t.id = pt.tag_id
                WHERE pt.paper_id = ?
                ORDER BY t.name
            """, (paper_id,))
            return [row[0] for row in cursor.fetchall()]

    def _set_paper_tags(self, cursor, paper_id: int, tag_names: list[str]):
        cursor.execute("DELETE FROM paper_tags WHERE paper_id = ?", (paper_id,))
        for name in tag_names:
            cursor.execute("SELECT id FROM tags WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                tag_id = row[0]
            else:
                cursor.execute("INSERT INTO tags (name) VALUES (?)", (name,))
                tag_id = cursor.lastrowid
            cursor.execute(
                "INSERT OR IGNORE INTO paper_tags (paper_id, tag_id) VALUES (?, ?)",
                (paper_id, tag_id)
            )


class TagRepository(BaseRepository):
    def get_all(self) -> list[Tag]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM tags ORDER BY name")
            return [Tag(id=row["id"], name=row["name"], color=row["color"],
                        created_at=row["created_at"]) for row in cursor.fetchall()]

    def get_by_id(self, tag_id: int) -> Optional[Tag]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM tags WHERE id = ?", (tag_id,))
            row = cursor.fetchone()
            if row:
                return Tag(id=row["id"], name=row["name"], color=row["color"],
                          created_at=row["created_at"])
        return None

    def get_by_name(self, name: str) -> Optional[Tag]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM tags WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                return Tag(id=row["id"], name=row["name"], color=row["color"],
                          created_at=row["created_at"])
        return None

    def create(self, tag: Tag) -> Tag:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO tags (name, color) VALUES (?, ?)",
                (tag.name, tag.color)
            )
            tag.id = cursor.lastrowid
        return tag

    def update(self, tag: Tag) -> Tag:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE tags SET name = ?, color = ? WHERE id = ?",
                (tag.name, tag.color, tag.id)
            )
        return tag

    def delete(self, tag_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))

    def get_paper_count(self, tag_id: int) -> int:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM paper_tags WHERE tag_id = ?", (tag_id,))
            return cursor.fetchone()[0]

    def get_tag_distribution(self) -> dict[str, int]:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT t.name, COUNT(pt.paper_id) as cnt
                FROM tags t LEFT JOIN paper_tags pt ON t.id = pt.tag_id
                GROUP BY t.id ORDER BY cnt DESC
            """)
            return {row[0]: row[1] for row in cursor.fetchall()}


class AnnotationRepository(BaseRepository):
    def get_by_paper(self, paper_id: int) -> list[Annotation]:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM annotations WHERE paper_id = ? ORDER BY page, id
            """, (paper_id,))
            return [self._row_to_annotation(row) for row in cursor.fetchall()]

    def get_by_id(self, annotation_id: int) -> Optional[Annotation]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM annotations WHERE id = ?", (annotation_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_annotation(row)
        return None

    def create(self, annotation: Annotation) -> Annotation:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO annotations (paper_id, page, annotation_type, color, rects, content)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                annotation.paper_id, annotation.page, annotation.annotation_type,
                annotation.color, annotation.rects, annotation.content
            ))
            annotation.id = cursor.lastrowid
        return annotation

    def update(self, annotation: Annotation) -> Annotation:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE annotations SET page=?, annotation_type=?, color=?,
                       rects=?, content=?, updated_at=CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                annotation.page, annotation.annotation_type, annotation.color,
                annotation.rects, annotation.content, annotation.id
            ))
        return annotation

    def delete(self, annotation_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))

    def delete_by_paper(self, paper_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute("DELETE FROM annotations WHERE paper_id = ?", (paper_id,))

    def _row_to_annotation(self, row) -> Annotation:
        return Annotation(
            id=row["id"],
            paper_id=row["paper_id"],
            page=row["page"],
            annotation_type=row["annotation_type"],
            color=row["color"],
            rects=row["rects"],
            content=row["content"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class NoteRepository(BaseRepository):
    def get_all(self) -> list[Note]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM notes ORDER BY updated_at DESC")
            return [self._row_to_note(row) for row in cursor.fetchall()]

    def get_by_id(self, note_id: int) -> Optional[Note]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_note(row)
        return None

    def get_by_paper(self, paper_id: int) -> list[Note]:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT n.* FROM notes n
                JOIN paper_notes pn ON n.id = pn.note_id
                WHERE pn.paper_id = ? ORDER BY n.updated_at DESC
            """, (paper_id,))
            return [self._row_to_note(row) for row in cursor.fetchall()]

    def create(self, note: Note) -> Note:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO notes (title, content, file_path)
                VALUES (?, ?, ?)
            """, (note.title, note.content, note.file_path))
            note.id = cursor.lastrowid
        return note

    def update(self, note: Note) -> Note:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE notes SET title=?, content=?, file_path=?,
                       updated_at=CURRENT_TIMESTAMP WHERE id = ?
            """, (note.title, note.content, note.file_path, note.id))
        return note

    def delete(self, note_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    def link_paper(self, note_id: int, paper_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "INSERT OR IGNORE INTO paper_notes (note_id, paper_id) VALUES (?, ?)",
                (note_id, paper_id)
            )

    def unlink_paper(self, note_id: int, paper_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM paper_notes WHERE note_id = ? AND paper_id = ?",
                (note_id, paper_id)
            )

    def _row_to_note(self, row) -> Note:
        return Note(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            file_path=row["file_path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class FolderRepository(BaseRepository):
    def get_all(self) -> list[Folder]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM folders ORDER BY parent_id, name")
            return [self._row_to_folder(row) for row in cursor.fetchall()]

    def get_by_id(self, folder_id: int) -> Optional[Folder]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM folders WHERE id = ?", (folder_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_folder(row)
        return None

    def get_root_folders(self) -> list[Folder]:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM folders WHERE parent_id IS NULL ORDER BY name"
            )
            return [self._row_to_folder(row) for row in cursor.fetchall()]

    def get_children(self, parent_id: int) -> list[Folder]:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM folders WHERE parent_id = ? ORDER BY name",
                (parent_id,)
            )
            return [self._row_to_folder(row) for row in cursor.fetchall()]

    def create(self, folder: Folder) -> Folder:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO folders (name, parent_id, folder_type, filter_json)
                VALUES (?, ?, ?, ?)
            """, (folder.name, folder.parent_id, folder.folder_type, folder.filter_json))
            folder.id = cursor.lastrowid
        return folder

    def update(self, folder: Folder) -> Folder:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE folders SET name=?, parent_id=?, folder_type=?, filter_json=?
                WHERE id = ?
            """, (folder.name, folder.parent_id, folder.folder_type,
                  folder.filter_json, folder.id))
        return folder

    def delete(self, folder_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute("DELETE FROM folders WHERE id = ?", (folder_id,))

    def add_paper(self, folder_id: int, paper_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "INSERT OR IGNORE INTO paper_folders (folder_id, paper_id) VALUES (?, ?)",
                (folder_id, paper_id)
            )

    def remove_paper(self, folder_id: int, paper_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM paper_folders WHERE folder_id = ? AND paper_id = ?",
                (folder_id, paper_id)
            )

    def get_papers(self, folder_id: int) -> list[int]:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT paper_id FROM paper_folders WHERE folder_id = ?",
                (folder_id,)
            )
            return [row[0] for row in cursor.fetchall()]

    def _row_to_folder(self, row) -> Folder:
        return Folder(
            id=row["id"],
            name=row["name"],
            parent_id=row["parent_id"],
            folder_type=row["folder_type"],
            filter_json=row["filter_json"],
            created_at=row["created_at"],
        )


class CitationRepository(BaseRepository):
    def get_citations_by_paper(self, paper_id: int) -> list[Citation]:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM citations WHERE source_paper_id = ?",
                (paper_id,)
            )
            return [self._row_to_citation(row) for row in cursor.fetchall()]

    def get_cited_by(self, paper_id: int) -> list[Citation]:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM citations WHERE target_paper_id = ?",
                (paper_id,)
            )
            return [self._row_to_citation(row) for row in cursor.fetchall()]

    def add_citation(self, source_id: int, target_id: int) -> None:
        if source_id == target_id:
            return
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                INSERT OR IGNORE INTO citations (source_paper_id, target_paper_id)
                VALUES (?, ?)
            """, (source_id, target_id))

    def remove_citation(self, source_id: int, target_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM citations
                WHERE source_paper_id = ? AND target_paper_id = ?
            """, (source_id, target_id))

    def get_citation_count(self, paper_id: int) -> int:
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM citations WHERE target_paper_id = ?",
                (paper_id,)
            )
            return cursor.fetchone()[0]

    def get_all_citations(self) -> list[Citation]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM citations")
            return [self._row_to_citation(row) for row in cursor.fetchall()]

    def _row_to_citation(self, row) -> Citation:
        return Citation(
            id=row["id"],
            source_paper_id=row["source_paper_id"],
            target_paper_id=row["target_paper_id"],
            created_at=row["created_at"],
        )


class SearchRepository(BaseRepository):
    def _build_fts_query(self, raw_query: str) -> str:
        raw_query = raw_query.strip()
        if not raw_query:
            return ""

        tokens = []
        i = 0
        while i < len(raw_query):
            ch = raw_query[i]
            if ch.isspace():
                i += 1
                continue
            if ch == '"':
                j = raw_query.find('"', i + 1)
                if j > i:
                    phrase = raw_query[i + 1:j]
                    if phrase.strip():
                        tokens.append(f'"{phrase.strip()}"')
                    i = j + 1
                    continue
            if ch in "()*":
                i += 1
                continue

            token = ""
            while i < len(raw_query) and not raw_query[i].isspace() and raw_query[i] not in '"()*':
                token += raw_query[i]
                i += 1

            if token in ("AND", "OR", "NOT"):
                tokens.append(token)
            elif token.startswith("-") and len(token) > 1:
                tokens.append(f"NOT {token[1:]}*")
            elif token:
                if all(ord(c) > 127 for c in token):
                    if len(token) <= 2:
                        tokens.append(f'"{token}"')
                    else:
                        parts = [f'"{token[j:j+2]}"' for j in range(0, len(token) - 1)]
                        tokens.extend(parts)
                else:
                    tokens.append(f"{token}*")

        if not tokens:
            return f'"{raw_query}"'

        operators = {"AND", "OR", "NOT"}
        cleaned = []
        prev_op = True
        for t in tokens:
            if t in operators:
                if not prev_op and cleaned:
                    cleaned.append(t)
                    prev_op = True
            else:
                if cleaned and not prev_op:
                    cleaned.append("AND")
                cleaned.append(t)
                prev_op = False

        if cleaned and cleaned[-1] in operators:
            cleaned.pop()

        return " ".join(cleaned)

    def full_text_search(self, query: str, limit: int = 50) -> list[tuple[int, float]]:
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return []

        results = []
        with self.db.get_cursor() as cursor:
            tried = False
            try:
                cursor.execute("""
                    SELECT rowid, bm25(papers_fts) as score
                    FROM papers_fts
                    WHERE papers_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_query, limit))
                results = [(row[0], row[1]) for row in cursor.fetchall()]
                tried = True
            except Exception:
                pass

            if not results:
                try:
                    simple_query = f'"{query.strip()}"'
                    cursor.execute("""
                        SELECT rowid, bm25(papers_fts) as score
                        FROM papers_fts
                        WHERE papers_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                    """, (simple_query, limit))
                    results = [(row[0], row[1]) for row in cursor.fetchall()]
                    tried = True
                except Exception:
                    pass

        if not results:
            results = self._fallback_search(query, limit)
        return results

    def _fallback_search(self, query: str, limit: int = 50) -> list[tuple[int, float]]:
        query_lower = query.lower().strip()
        if not query_lower:
            return []

        like_pattern = f"%{query_lower}%"
        results = []
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT id FROM papers
                WHERE LOWER(COALESCE(title, '')) LIKE ?
                   OR LOWER(COALESCE(authors, '')) LIKE ?
                   OR LOWER(COALESCE(journal, '')) LIKE ?
                   OR LOWER(COALESCE(doi, '')) LIKE ?
                   OR LOWER(COALESCE(abstract, '')) LIKE ?
                   OR LOWER(COALESCE(full_text, '')) LIKE ?
                   OR LOWER(COALESCE(notes, '')) LIKE ?
                   OR LOWER(COALESCE(summary, '')) LIKE ?
                   OR LOWER(COALESCE(keywords, '')) LIKE ?
                ORDER BY
                    CASE WHEN LOWER(COALESCE(title, '')) LIKE ? THEN 0
                         WHEN LOWER(COALESCE(authors, '')) LIKE ? THEN 1
                         WHEN LOWER(COALESCE(abstract, '')) LIKE ? THEN 2
                         WHEN LOWER(COALESCE(keywords, '')) LIKE ? THEN 3
                         ELSE 4 END,
                    added_at DESC
                LIMIT ?
            """, (
                like_pattern, like_pattern, like_pattern, like_pattern,
                like_pattern, like_pattern, like_pattern, like_pattern, like_pattern,
                like_pattern, like_pattern, like_pattern, like_pattern,
                limit
            ))
            for i, row in enumerate(cursor.fetchall()):
                results.append((row[0], float(i)))
        return results

    def search_simple(self, query: str, limit: int = 50, offset: int = 0) -> list[Paper]:
        if not query or not query.strip():
            return []

        fts_query = self._build_fts_query(query)
        papers = []
        from .models import Paper

        with self.db.get_cursor() as cursor:
            executed = False

            try:
                cursor.execute("""
                    SELECT DISTINCT p.* FROM papers p
                    WHERE p.id IN (
                        SELECT rowid FROM papers_fts
                        WHERE papers_fts MATCH ?
                        ORDER BY rank
                    )
                    LIMIT ? OFFSET ?
                """, (fts_query, limit, offset))
                executed = True
            except Exception:
                pass

            if not executed or not cursor.description:
                try:
                    simple_q = f'"{query.strip()}"'
                    cursor.execute("""
                        SELECT DISTINCT p.* FROM papers p
                        WHERE p.id IN (
                            SELECT rowid FROM papers_fts
                            WHERE papers_fts MATCH ?
                            ORDER BY rank
                        )
                        LIMIT ? OFFSET ?
                    """, (simple_q, limit, offset))
                    executed = True
                except Exception:
                    pass

            if not executed or not cursor.description:
                like_pattern = f"%{query.lower().strip()}%"
                cursor.execute("""
                    SELECT DISTINCT p.* FROM papers p
                    WHERE LOWER(COALESCE(p.title, '')) LIKE ?
                       OR LOWER(COALESCE(p.authors, '')) LIKE ?
                       OR LOWER(COALESCE(p.abstract, '')) LIKE ?
                       OR LOWER(COALESCE(p.full_text, '')) LIKE ?
                       OR LOWER(COALESCE(p.keywords, '')) LIKE ?
                       OR LOWER(COALESCE(p.summary, '')) LIKE ?
                    ORDER BY
                        CASE WHEN LOWER(COALESCE(p.title, '')) LIKE ? THEN 0 ELSE 1 END,
                        p.added_at DESC
                    LIMIT ? OFFSET ?
                """, (
                    like_pattern, like_pattern, like_pattern, like_pattern,
                    like_pattern, like_pattern, like_pattern, limit, offset
                ))

            for row in cursor.fetchall():
                paper = Paper(
                    id=row["id"],
                    title=row["title"],
                    authors=row["authors"],
                    year=row["year"],
                    journal=row["journal"],
                    doi=row["doi"],
                    url=row["url"],
                    file_path=row["file_path"],
                    file_hash=row["file_hash"],
                    page_count=row["page_count"],
                    file_size=row["file_size"],
                    reading_status=row["reading_status"],
                    rating=row["rating"],
                    notes=row["notes"],
                    summary=row["summary"],
                    keywords=row["keywords"],
                    added_at=row["added_at"],
                    updated_at=row["updated_at"],
                    last_read_at=row["last_read_at"],
                    is_archived=row["is_archived"],
                    abstract=row["abstract"],
                    full_text=row["full_text"],
                )
                papers.append(paper)

        return papers


class AICacheRepository(BaseRepository):
    def get_cache(self, paper_id: int, cache_type: str) -> Optional[str]:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT cache_data FROM ai_cache
                WHERE paper_id = ? AND cache_type = ?
            """, (paper_id, cache_type))
            row = cursor.fetchone()
            if row:
                return row[0]
        return None

    def set_cache(self, paper_id: int, cache_type: str, cache_data: str) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO ai_cache (paper_id, cache_type, cache_data, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (paper_id, cache_type, cache_data))

    def clear_cache(self, paper_id: int) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute("DELETE FROM ai_cache WHERE paper_id = ?", (paper_id,))

    def clear_all_cache(self) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute("DELETE FROM ai_cache")

    def get_vector(self, paper_id: int) -> bytes | None:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT vector FROM paper_vectors WHERE paper_id = ?", (paper_id,))
            row = cursor.fetchone()
            if row:
                return row[0]
        return None

    def set_vector(self, paper_id: int, vector: bytes) -> None:
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO paper_vectors (paper_id, vector, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (paper_id, vector))

    def get_all_vectors(self) -> dict[int, bytes]:
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT paper_id, vector FROM paper_vectors")
            return {row[0]: row[1] for row in cursor.fetchall()}
