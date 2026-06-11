from PySide6.QtCore import QThread, Signal, QObject

from ..services.library_service import get_library_service
from ..services.ai_service import get_ai_service
from ..services.pdf_service import get_pdf_service
from ..infrastructure.logger import get_logger

logger = get_logger(__name__)


class ImportWorker(QThread):
    progress = Signal(int, int, str)
    finished_import = Signal(list)
    error = Signal(str)

    def __init__(self, file_paths: list[str]):
        super().__init__()
        self.file_paths = file_paths
        self.library_service = get_library_service()

    def run(self):
        try:
            import os
            papers = []
            total = len(self.file_paths)
            for i, path in enumerate(self.file_paths):
                filename = os.path.basename(path)
                self.progress.emit(i + 1, total, f"导入中: {filename}")
                paper = self.library_service.add_paper(path, parse_ai=False)
                if paper:
                    papers.append(paper)
            self.finished_import.emit(papers)
        except Exception as e:
            logger.error(f"Import error: {e}")
            self.error.emit(str(e))


class AIWorker(QThread):
    progress = Signal(int, int, str)
    finished_ai = Signal()
    error = Signal(str)

    def __init__(self, paper_ids: list[int]):
        super().__init__()
        self.paper_ids = paper_ids
        self.ai_service = get_ai_service()

    def run(self):
        try:
            total = len(self.paper_ids)
            for i, pid in enumerate(self.paper_ids):
                self.progress.emit(i + 1, total, f"AI 处理中...")
                self.ai_service.process_paper_async(pid)
            self.finished_ai.emit()
        except Exception as e:
            logger.error(f"AI error: {e}")
            self.error.emit(str(e))


class SummaryWorker(QThread):
    finished_summary = Signal(int, str)
    error = Signal(str)

    def __init__(self, paper_id: int, force: bool = False):
        super().__init__()
        self.paper_id = paper_id
        self.force = force
        self.ai_service = get_ai_service()

    def run(self):
        try:
            summary = self.ai_service.generate_summary(self.paper_id, force=self.force)
            self.finished_summary.emit(self.paper_id, summary or "")
        except Exception as e:
            logger.error(f"Summary error: {e}")
            self.error.emit(str(e))


class KeywordsWorker(QThread):
    finished_keywords = Signal(int, list)
    error = Signal(str)

    def __init__(self, paper_id: int, force: bool = False):
        super().__init__()
        self.paper_id = paper_id
        self.force = force
        self.ai_service = get_ai_service()

    def run(self):
        try:
            keywords = self.ai_service.generate_keywords(self.paper_id, force=self.force)
            self.finished_keywords.emit(self.paper_id, keywords)
        except Exception as e:
            logger.error(f"Keywords error: {e}")
            self.error.emit(str(e))


class SemanticSearchWorker(QThread):
    finished_search = Signal(list)
    error = Signal(str)

    def __init__(self, query: str, top_k: int = 10):
        super().__init__()
        self.query = query
        self.top_k = top_k
        self.ai_service = get_ai_service()

    def run(self):
        try:
            results = self.ai_service.semantic_search(self.query, top_k=self.top_k)
            self.finished_search.emit(results)
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            self.error.emit(str(e))


class PDFRenderWorker(QThread):
    finished_render = Signal(int, bytes)
    error = Signal(str)

    def __init__(self, file_path: str, page_num: int, scale: float = 2.0):
        super().__init__()
        self.file_path = file_path
        self.page_num = page_num
        self.scale = scale
        self.pdf_service = get_pdf_service()

    def run(self):
        try:
            image_bytes = self.pdf_service.render_page(
                self.file_path, self.page_num, self.scale
            )
            self.finished_render.emit(self.page_num, image_bytes)
        except Exception as e:
            logger.error(f"PDF render error: {e}")
            self.error.emit(str(e))
