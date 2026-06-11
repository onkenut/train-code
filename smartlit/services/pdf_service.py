import hashlib
import re
from pathlib import Path
from typing import Optional

from ..db.models import Paper
from ..infrastructure.logger import get_logger

logger = get_logger(__name__)

try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    fitz = None
    logger.warning("PyMuPDF (fitz) not installed, PDF functionality will be limited")


class PDFService:
    def __init__(self):
        if not HAS_PYMUPDF:
            logger.warning("PDFService: PyMuPDF not available")

    def _ensure_fitz(self):
        if not HAS_PYMUPDF:
            raise RuntimeError(
                "PyMuPDF 未安装。请运行: pip install PyMuPDF\n"
                "PyMuPDF not installed. Please run: pip install PyMuPDF"
            )

    def parse_metadata(self, file_path: str) -> Paper:
        self._ensure_fitz()
        doc = fitz.open(file_path)
        try:
            metadata = doc.metadata
            page_count = len(doc)
            file_size = Path(file_path).stat().st_size
            file_hash = self._compute_file_hash(file_path)

            title = metadata.get("title") or self._extract_title_from_first_page(doc)
            authors = metadata.get("author")
            year = self._extract_year(metadata)
            doi = self._extract_doi(doc)
            abstract = self._extract_abstract(doc)

            paper = Paper(
                title=title,
                authors=authors,
                year=year,
                journal=metadata.get("subject"),
                doi=doi,
                file_path=file_path,
                file_hash=file_hash,
                page_count=page_count,
                file_size=file_size,
                abstract=abstract,
            )
            return paper
        finally:
            doc.close()

    def extract_full_text(self, file_path: str, max_pages: int = 100) -> str:
        doc = fitz.open(file_path)
        try:
            texts = []
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                texts.append(page.get_text())
            return "\n\n".join(texts)
        finally:
            doc.close()

    def get_page_count(self, file_path: str) -> int:
        doc = fitz.open(file_path)
        try:
            return len(doc)
        finally:
            doc.close()

    def render_page(self, file_path: str, page_num: int, scale: float = 2.0) -> bytes:
        doc = fitz.open(file_path)
        try:
            page = doc[page_num]
            matrix = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=matrix)
            return pix.tobytes("png")
        finally:
            doc.close()

    def get_page_text(self, file_path: str, page_num: int) -> str:
        doc = fitz.open(file_path)
        try:
            return doc[page_num].get_text()
        finally:
            doc.close()

    def search_in_pdf(self, file_path: str, query: str) -> list[tuple[int, str]]:
        doc = fitz.open(file_path)
        try:
            results = []
            for i, page in enumerate(doc):
                text_instances = page.search_for(query)
                if text_instances:
                    context = page.get_text()[:200]
                    results.append((i, context))
            return results
        finally:
            doc.close()

    def extract_references(self, file_path: str) -> list[str]:
        doc = fitz.open(file_path)
        try:
            full_text = ""
            for page in doc:
                full_text += page.get_text()

            refs = self._parse_references(full_text)
            return refs
        finally:
            doc.close()

    def _compute_file_hash(self, file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _extract_title_from_first_page(self, doc) -> Optional[str]:
        if len(doc) == 0:
            return None
        page = doc[0]
        text = page.get_text()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if lines:
            return lines[0][:200]
        return None

    def _extract_year(self, metadata: dict) -> Optional[int]:
        date_str = metadata.get("creationDate", "")
        if date_str:
            match = re.search(r"D:(\d{4})", date_str)
            if match:
                return int(match.group(1))
        return None

    def _extract_doi(self, doc) -> Optional[str]:
        doi_pattern = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
        for i in range(min(3, len(doc))):
            text = doc[i].get_text()
            match = doi_pattern.search(text)
            if match:
                return match.group(0)
        return None

    def _extract_abstract(self, doc) -> Optional[str]:
        if len(doc) == 0:
            return None
        text = doc[0].get_text()
        abstract_match = re.search(
            r"(?:abstract|摘要)\s*[:：]?\s*(.+?)(?:\n\s*\n|1\.?\s*introduction|关键词|keywords)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if abstract_match:
            return abstract_match.group(1).strip()[:1000]
        return None

    def _parse_references(self, full_text: str) -> list[str]:
        refs_section = re.search(
            r"(?:references|bibliography|参考文献)\s*[\n:：]",
            full_text,
            re.IGNORECASE
        )
        if not refs_section:
            return []

        ref_text = full_text[refs_section.end():]
        ref_pattern = re.compile(r"^\[?\d+\]?\s*(.+)", re.MULTILINE)
        refs = ref_pattern.findall(ref_text[:5000])
        return [ref.strip() for ref in refs[:100] if ref.strip()]

    def extract_dois_from_references(self, file_path: str) -> list[str]:
        refs = self.extract_references(file_path)
        doi_pattern = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
        dois = []
        for ref in refs:
            match = doi_pattern.search(ref)
            if match:
                dois.append(match.group(0))
        return dois


def get_pdf_service() -> PDFService:
    return PDFService()
