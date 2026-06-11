import os
from pathlib import Path
from typing import Optional, Callable
import shutil

from ..db.models import Paper, Tag, Annotation, Note
from ..db.repositories import (
    PaperRepository, TagRepository, AnnotationRepository,
    NoteRepository, FolderRepository, CitationRepository, AICacheRepository
)
from .pdf_service import get_pdf_service
from ..infrastructure.logger import get_logger

logger = get_logger(__name__)


class LibraryService:
    def __init__(self):
        self.paper_repo = PaperRepository()
        self.tag_repo = TagRepository()
        self.annotation_repo = AnnotationRepository()
        self.note_repo = NoteRepository()
        self.folder_repo = FolderRepository()
        self.citation_repo = CitationRepository()
        self.ai_cache_repo = AICacheRepository()
        self.pdf_service = get_pdf_service()

    def add_paper(self, file_path: str, parse_ai: bool = True,
                  progress_callback: Optional[Callable[[str], None]] = None) -> Optional[Paper]:
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None

        existing = self.paper_repo.get_by_file_path(file_path)
        if existing:
            logger.info(f"Paper already exists: {file_path}")
            return existing

        if progress_callback:
            progress_callback("解析 PDF 元数据...")

        try:
            paper = self.pdf_service.parse_metadata(file_path)
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            paper = Paper(file_path=file_path)

        paper = self.paper_repo.create(paper)

        if progress_callback:
            progress_callback("提取全文...")

        try:
            full_text = self.pdf_service.extract_full_text(file_path)
            paper.full_text = full_text
            paper = self.paper_repo.update(paper)
        except Exception as e:
            logger.error(f"Failed to extract full text: {e}")

        if progress_callback:
            progress_callback("文献导入完成")

        logger.info(f"Added paper: {paper.title or file_path}")
        return paper

    def add_papers_batch(self, file_paths: list[str],
                         progress_callback: Optional[Callable[[int, int, str], None]] = None) -> list[Paper]:
        papers = []
        total = len(file_paths)
        for i, path in enumerate(file_paths):
            if progress_callback:
                progress_callback(i + 1, total, f"导入中: {Path(path).name}")
            paper = self.add_paper(path, parse_ai=False)
            if paper:
                papers.append(paper)
        return papers

    def get_paper(self, paper_id: int) -> Optional[Paper]:
        return self.paper_repo.get_by_id(paper_id)

    def get_all_papers(self, include_archived: bool = False,
                       limit: int = 100, offset: int = 0) -> list[Paper]:
        return self.paper_repo.get_all(include_archived=include_archived, limit=limit, offset=offset)

    def update_paper(self, paper: Paper) -> Paper:
        return self.paper_repo.update(paper)

    def delete_paper(self, paper_id: int, delete_file: bool = False) -> None:
        paper = self.paper_repo.get_by_id(paper_id)
        if not paper:
            return

        self.paper_repo.delete(paper_id)

        if delete_file and paper.file_path and os.path.exists(paper.file_path):
            try:
                os.remove(paper.file_path)
            except Exception as e:
                logger.error(f"Failed to delete file: {e}")

        logger.info(f"Deleted paper: {paper_id}")

    def count_papers(self, include_archived: bool = False) -> int:
        return self.paper_repo.count(include_archived=include_archived)

    def update_reading_status(self, paper_id: int, status: str) -> None:
        self.paper_repo.update_reading_status(paper_id, status)

    def update_rating(self, paper_id: int, rating: int) -> None:
        self.paper_repo.update_rating(paper_id, rating)

    def update_last_read(self, paper_id: int) -> None:
        self.paper_repo.update_last_read(paper_id)

    def toggle_archive(self, paper_id: int) -> bool:
        return self.paper_repo.toggle_archive(paper_id)

    def add_tags_to_paper(self, paper_id: int, tag_names: list[str]) -> None:
        paper = self.paper_repo.get_by_id(paper_id)
        if not paper:
            return

        for name in tag_names:
            tag = self.tag_repo.get_by_name(name)
            if not tag:
                tag = Tag(name=name)
                tag = self.tag_repo.create(tag)

        existing_tags = set(paper.tags)
        for name in tag_names:
            existing_tags.add(name)
        paper.tags = list(existing_tags)
        self.paper_repo.update(paper)

    def remove_tag_from_paper(self, paper_id: int, tag_name: str) -> None:
        paper = self.paper_repo.get_by_id(paper_id)
        if not paper:
            return

        if tag_name in paper.tags:
            paper.tags.remove(tag_name)
            self.paper_repo.update(paper)

    def filter_papers(self, **kwargs) -> list[Paper]:
        return self.paper_repo.filter_papers(**kwargs)

    def get_tags(self) -> list[Tag]:
        return self.tag_repo.get_all()

    def create_tag(self, name: str, color: str = "#2196F3") -> Tag:
        tag = Tag(name=name, color=color)
        return self.tag_repo.create(tag)

    def update_tag(self, tag: Tag) -> Tag:
        return self.tag_repo.update(tag)

    def delete_tag(self, tag_id: int) -> None:
        self.tag_repo.delete(tag_id)

    def get_annotations(self, paper_id: int) -> list[Annotation]:
        return self.annotation_repo.get_by_paper(paper_id)

    def add_annotation(self, annotation: Annotation) -> Annotation:
        return self.annotation_repo.create(annotation)

    def update_annotation(self, annotation: Annotation) -> Annotation:
        return self.annotation_repo.update(annotation)

    def delete_annotation(self, annotation_id: int) -> None:
        self.annotation_repo.delete(annotation_id)

    def export_annotations_markdown(self, paper_id: int) -> str:
        paper = self.get_paper(paper_id)
        if not paper:
            return ""

        annotations = self.get_annotations(paper_id)
        lines = [f"# {paper.title or '未知文献'}", ""]
        lines.append(f"**作者**: {paper.authors or '未知'}")
        lines.append(f"**年份**: {paper.year or '未知'}")
        lines.append("")
        lines.append("## 标注列表")
        lines.append("")

        current_page = None
        for ann in annotations:
            if ann.page != current_page:
                current_page = ann.page
                lines.append(f"### 第 {ann.page + 1} 页")
                lines.append("")

            type_label = {
                "highlight": "高亮",
                "underline": "下划线",
                "strikethrough": "删除线",
                "text_box": "文本框",
            }.get(ann.annotation_type, ann.annotation_type)

            lines.append(f"- **[{type_label}]** {ann.content or '无内容'}")
            lines.append("")

        return "\n".join(lines)

    def export_bibtex(self, paper_ids: list[int]) -> str:
        entries = []
        for pid in paper_ids:
            paper = self.get_paper(pid)
            if not paper:
                continue

            key = f"{paper.authors.split(',')[0].split()[-1] if paper.authors else 'unknown'}{paper.year or ''}"
            lines = [f"@article{{{key},"]
            if paper.title:
                lines.append(f"  title = {{{paper.title}}},")
            if paper.authors:
                lines.append(f"  author = {{{paper.authors}}},")
            if paper.year:
                lines.append(f"  year = {{{paper.year}}},")
            if paper.journal:
                lines.append(f"  journal = {{{paper.journal}}},")
            if paper.doi:
                lines.append(f"  doi = {{{paper.doi}}},")
            lines.append("}")
            entries.append("\n".join(lines))

        return "\n\n".join(entries)

    def get_statistics(self) -> dict:
        total = self.count_papers()
        status_dist = self.paper_repo.get_reading_status_distribution()
        year_dist = self.paper_repo.get_year_distribution()
        tag_dist = self.tag_repo.get_tag_distribution()

        return {
            "total": total,
            "status_distribution": status_dist,
            "year_distribution": year_dist,
            "tag_distribution": tag_dist,
        }


def get_library_service() -> LibraryService:
    return LibraryService()
