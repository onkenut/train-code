from typing import Optional

from ..db.repositories import SearchRepository, PaperRepository
from ..db.models import Paper
from ..infrastructure.logger import get_logger

logger = get_logger(__name__)


class SearchService:
    def __init__(self):
        self.search_repo = SearchRepository()
        self.paper_repo = PaperRepository()

    def full_text_search(self, query: str, limit: int = 50,
                         offset: int = 0) -> list[Paper]:
        if not query or not query.strip():
            return []

        try:
            papers = self.search_repo.search_simple(query, limit=limit, offset=offset)
            for paper in papers:
                paper.tags = self._get_paper_tags(paper.id)
            return papers
        except Exception as e:
            logger.error(f"Full text search failed: {e}")
            return []

    def search_with_score(self, query: str, limit: int = 50) -> list[tuple[Paper, float]]:
        if not query or not query.strip():
            return []

        try:
            results = self.search_repo.full_text_search(query, limit=limit)
            papers = []
            for paper_id, score in results:
                paper = self.paper_repo.get_by_id(paper_id)
                if paper:
                    papers.append((paper, score))
            return papers
        except Exception as e:
            logger.error(f"Full text search failed: {e}")
            return []

    def advanced_search(
        self,
        query: str = "",
        tag_ids: list[int] | None = None,
        reading_status: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        rating_min: int | None = None,
        author: str | None = None,
        sort_by: str = "relevance",
        limit: int = 50,
        offset: int = 0,
    ) -> list[Paper]:
        if query:
            fts_papers = self.full_text_search(query, limit=1000)
            fts_ids = {p.id for p in fts_papers}
        else:
            fts_ids = None

        sort_field = "added_at"
        sort_order = "DESC"
        if sort_by == "relevance":
            sort_field = "added_at"
        elif sort_by == "title":
            sort_field = "title"
            sort_order = "ASC"
        elif sort_by == "year":
            sort_field = "year"
        elif sort_by == "rating":
            sort_field = "rating"

        papers = self.paper_repo.filter_papers(
            tag_ids=tag_ids,
            reading_status=reading_status,
            year_min=year_min,
            year_max=year_max,
            rating_min=rating_min,
            author=author,
            sort_by=sort_field,
            sort_order=sort_order,
            limit=limit + (offset if fts_ids else 0),
            offset=0,
        )

        if fts_ids is not None:
            papers = [p for p in papers if p.id in fts_ids]

        return papers[offset:offset + limit]

    def _get_paper_tags(self, paper_id: int | None) -> list[str]:
        if paper_id is None:
            return []
        from ..db.repositories import PaperRepository
        repo = PaperRepository()
        return repo._get_paper_tags(paper_id)


def get_search_service() -> SearchService:
    return SearchService()
