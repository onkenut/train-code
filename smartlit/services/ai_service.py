import json
import re
from typing import Optional

from ..config import get_config
from ..ai_config import get_ai_config_manager
from ..db.repositories import (
    PaperRepository, AICacheRepository, CitationRepository
)
from ..db.models import Paper
from ..infrastructure.cache_manager import get_cache_manager
from ..infrastructure.logger import get_logger
from .ai_providers import create_provider, PROVIDER_REGISTRY

logger = get_logger(__name__)


class AIService:
    def __init__(self):
        self.config = get_config()
        self.ai_config = get_ai_config_manager()
        self.paper_repo = PaperRepository()
        self.ai_cache_repo = AICacheRepository()
        self.citation_repo = CitationRepository()
        self.cache = get_cache_manager()

        self._embedding_model = None
        self._vector_cache: dict[int, list[float]] = {}
        self._vectors_loaded = False
        self._current_provider = None

    def _get_provider(self):
        prov_config = self.ai_config.get_default_provider()
        provider = create_provider(
            prov_config.provider,
            api_key=prov_config.api_key,
            base_url=prov_config.base_url,
            model_name=prov_config.model_name,
            api_version=prov_config.api_version,
        )
        return provider

    def get_available_providers(self) -> list[str]:
        return list(PROVIDER_REGISTRY.keys())

    def set_default_provider(self, provider_name: str):
        self.ai_config.config.default_provider = provider_name
        self.ai_config.save()

    def generate_summary(self, paper_id: int, force: bool = False,
                         provider: str | None = None) -> Optional[str]:
        if not self.ai_config.config.enabled:
            return None

        cached = self.cache.get_summary(paper_id)
        if cached and not force:
            return cached

        if not force:
            db_cache = self.ai_cache_repo.get_cache(paper_id, "summary")
            if db_cache:
                self.cache.set_summary(paper_id, db_cache)
                return db_cache

        paper = self.paper_repo.get_by_id(paper_id)
        if not paper or not paper.full_text:
            return paper.summary if paper else None

        try:
            ai_provider = self._get_provider()
            summary = ai_provider.generate_summary(
                paper.full_text,
                language=self.ai_config.config.summary_language,
                sentences=self.ai_config.config.summary_sentences,
            )
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return paper.summary

        if not summary:
            try:
                local = create_provider("local")
                summary = local.generate_summary(
                    paper.full_text,
                    language=self.ai_config.config.summary_language,
                    sentences=self.ai_config.config.summary_sentences,
                )
            except Exception as e:
                logger.error(f"Local fallback summary failed: {e}")
                return paper.summary

        if summary:
            self.cache.set_summary(paper_id, summary)
            self.ai_cache_repo.set_cache(paper_id, "summary", summary)
            paper.summary = summary
            self.paper_repo.update(paper)

        return summary

    def generate_keywords(self, paper_id: int, num_keywords: int | None = None,
                          force: bool = False, provider: str | None = None) -> list[str]:
        if not self.ai_config.config.enabled:
            return []

        if num_keywords is None:
            num_keywords = self.ai_config.config.keyword_count

        cached = self.cache.get_keywords(paper_id)
        if cached and not force:
            return cached

        if not force:
            db_cache = self.ai_cache_repo.get_cache(paper_id, "keywords")
            if db_cache:
                keywords = json.loads(db_cache)
                self.cache.set_keywords(paper_id, keywords)
                return keywords

        paper = self.paper_repo.get_by_id(paper_id)
        if not paper or not paper.full_text:
            if paper and paper.keywords:
                return paper.keywords.split(",")
            return []

        try:
            ai_provider = self._get_provider()
            keywords = ai_provider.generate_keywords(paper.full_text, count=num_keywords)
        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}")
            keywords = []

        if not keywords:
            try:
                local = create_provider("local")
                keywords = local.generate_keywords(paper.full_text, count=num_keywords)
            except Exception as e:
                logger.error(f"Local fallback keywords failed: {e}")
                if paper and paper.keywords:
                    return paper.keywords.split(",")
                return []

        if keywords:
            self.cache.set_keywords(paper_id, keywords)
            self.ai_cache_repo.set_cache(paper_id, "keywords", json.dumps(keywords))
            paper.keywords = ",".join(keywords)
            self.paper_repo.update(paper)

        return keywords

    def semantic_search(self, query: str, top_k: int | None = None) -> list[tuple[Paper, float]]:
        if not self.ai_config.config.enabled:
            return []

        if top_k is None:
            top_k = self.ai_config.config.semantic_search_top_k

        try:
            self._ensure_vectors_loaded()
            query_vector = self._encode_text(query)
            if query_vector is None:
                return []

            results = []
            for paper_id, paper_vector in self._vector_cache.items():
                if paper_vector is None:
                    continue
                similarity = self._cosine_similarity(query_vector, paper_vector)
                results.append((paper_id, similarity))

            results.sort(key=lambda x: x[1], reverse=True)
            top_results = results[:top_k]

            papers = []
            for paper_id, score in top_results:
                paper = self.paper_repo.get_by_id(paper_id)
                if paper:
                    papers.append((paper, score))

            return papers

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def generate_vector(self, paper_id: int, force: bool = False) -> Optional[list[float]]:
        if not self.ai_config.config.enabled:
            return None

        if paper_id in self._vector_cache and not force:
            return self._vector_cache[paper_id]

        if not force:
            cached = self.cache.get_vector(paper_id)
            if cached is not None:
                self._vector_cache[paper_id] = cached
                return cached

            db_vec = self.ai_cache_repo.get_vector(paper_id)
            if db_vec:
                try:
                    import numpy as np
                    vec = np.frombuffer(db_vec, dtype=np.float32).tolist()
                    self._vector_cache[paper_id] = vec
                    self.cache.set_vector(paper_id, vec)
                    return vec
                except Exception as e:
                    logger.error(f"Failed to load vector: {e}")

        paper = self.paper_repo.get_by_id(paper_id)
        if not paper:
            return None

        text = f"{paper.title or ''} {paper.abstract or ''}"
        if not text.strip():
            return None

        try:
            vector = self._encode_text(text)
        except Exception as e:
            logger.error(f"Vector generation failed: {e}")
            return None

        if vector is not None:
            self._vector_cache[paper_id] = vector
            self.cache.set_vector(paper_id, vector)

            try:
                import numpy as np
                vec_bytes = np.array(vector, dtype=np.float32).tobytes()
                self.ai_cache_repo.set_vector(paper_id, vec_bytes)
            except Exception as e:
                logger.error(f"Failed to save vector: {e}")

        return vector

    def discover_citations(self, paper_id: int) -> int:
        from .pdf_service import get_pdf_service
        pdf_service = get_pdf_service()

        paper = self.paper_repo.get_by_id(paper_id)
        if not paper:
            return 0

        try:
            dois = pdf_service.extract_dois_from_references(paper.file_path)
        except Exception as e:
            logger.error(f"Failed to extract references: {e}")
            return 0

        count = 0
        for doi in dois:
            target_paper = self.paper_repo.get_by_doi(doi)
            if target_paper and target_paper.id != paper_id:
                self.citation_repo.add_citation(paper_id, target_paper.id)
                count += 1

        logger.info(f"Discovered {count} citations for paper {paper_id}")
        return count

    def chat(self, messages: list[dict], temperature: float = 0.7,
             max_tokens: int = 1000, provider: str | None = None) -> Optional[str]:
        if not self.ai_config.config.enabled:
            return None

        try:
            ai_provider = self._get_provider()
            return ai_provider.chat(messages, temperature=temperature, max_tokens=max_tokens)
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return None

    def _ensure_vectors_loaded(self):
        if self._vectors_loaded:
            return

        try:
            all_vectors = self.ai_cache_repo.get_all_vectors()
            import numpy as np
            for paper_id, vec_bytes in all_vectors.items():
                try:
                    vec = np.frombuffer(vec_bytes, dtype=np.float32).tolist()
                    self._vector_cache[paper_id] = vec
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to load vectors: {e}")

        self._vectors_loaded = True

    def _encode_text(self, text: str) -> Optional[list[float]]:
        try:
            from sentence_transformers import SentenceTransformer
            if self._embedding_model is None:
                self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            vector = self._embedding_model.encode(text)
            return vector.tolist()
        except ImportError:
            return None
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    def _cosine_similarity(self, v1: list[float], v2: list[float]) -> float:
        if len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = sum(a * a for a in v1) ** 0.5
        norm2 = sum(b * b for b in v2) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def process_paper_async(self, paper_id: int) -> None:
        self.generate_summary(paper_id)
        self.generate_keywords(paper_id)
        self.generate_vector(paper_id)
        self.discover_citations(paper_id)
        logger.info(f"AI processing complete for paper {paper_id}")


def get_ai_service() -> AIService:
    return AIService()
