import logging
from typing import List, Optional

from pixelvault.database.dao import AssetDAO, ClipVectorDAO, PersonDAO, TagDAO, AssetTagDAO, MetadataDAO
from pixelvault.database.models import SearchResult, Asset
from pixelvault.ai.clip_engine import CLIPEngine
from pixelvault.search.parser import QueryParser, ParsedQuery
from pixelvault.search.rank import reciprocal_rank_fusion, weighted_fusion, normalize_scores

logger = logging.getLogger(__name__)


class SearchEngine:
    def __init__(self, clip_engine: CLIPEngine):
        self.clip_engine = clip_engine
        self.asset_dao = AssetDAO()
        self.clip_dao = ClipVectorDAO()
        self.person_dao = PersonDAO()
        self.tag_dao = TagDAO()
        self.asset_tag_dao = AssetTagDAO()
        self.metadata_dao = MetadataDAO()
        self.parser = QueryParser()

    def search(self, query: str, limit: int = 100) -> List[SearchResult]:
        parsed = self.parser.parse(query)
        result_lists = []

        if parsed.has_semantic:
            semantic_results = self._semantic_search(parsed.semantic_text, limit)
            if semantic_results:
                result_lists.append(semantic_results)

        fts_results = self._fts_search(parsed, limit)
        if fts_results:
            result_lists.append(fts_results)

        filter_results = self._filter_search(parsed, limit)
        if filter_results:
            result_lists.append(filter_results)

        if len(result_lists) == 0:
            return []
        elif len(result_lists) == 1:
            return result_lists[0][:limit]

        if parsed.has_semantic and len(result_lists) >= 2:
            semantic_norm = normalize_scores(result_lists[0]) if result_lists[0] else []
            fts_norm = normalize_scores(result_lists[1]) if len(result_lists) > 1 else []
            fused = weighted_fusion(semantic_norm, fts_norm, semantic_weight=0.6, fts_weight=0.4)
        else:
            fused = reciprocal_rank_fusion(result_lists)

        if filter_results and len(result_lists) > 2:
            filter_ids = {r.asset_id for r in filter_results}
            fused = [r for r in fused if r.asset_id in filter_ids]

        return fused[:limit]

    def _semantic_search(self, text: str, limit: int) -> List[SearchResult]:
        if not self.clip_engine.is_available:
            return []

        try:
            query_vector = self.clip_engine.encode_text(text)
            similar = self.clip_dao.search_similar(query_vector, top_k=limit)
            return [
                SearchResult(asset_id=aid, score=score, match_type="semantic")
                for aid, score in similar
            ]
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def _fts_search(self, parsed: ParsedQuery, limit: int) -> List[SearchResult]:
        try:
            fts_query = self.parser.to_fts_query(parsed)
            if not fts_query:
                return []
            assets = self.asset_dao.search_fts(fts_query, limit)
            return [
                SearchResult(asset_id=a.id, score=1.0 - (i * 0.01), match_type="fts")
                for i, a in enumerate(assets)
            ]
        except Exception as e:
            logger.error(f"FTS search failed: {e}")
            return []

    def _filter_search(self, parsed: ParsedQuery, limit: int) -> List[SearchResult]:
        has_filters = any([
            parsed.media_type, parsed.date_from, parsed.date_to,
            parsed.min_width, parsed.min_height, parsed.camera_model,
        ])
        if not has_filters:
            return []

        try:
            assets = self.asset_dao.search_filtered(
                media_type=parsed.media_type,
                date_from=parsed.date_from,
                date_to=parsed.date_to,
                min_width=parsed.min_width,
                min_height=parsed.min_height,
                camera_model=parsed.camera_model,
                limit=limit,
            )
            return [
                SearchResult(asset_id=a.id, score=1.0, match_type="filter")
                for a in assets
            ]
        except Exception as e:
            logger.error(f"Filter search failed: {e}")
            return []

    def search_by_person(self, person_name: str, limit: int = 100) -> List[SearchResult]:
        persons = self.person_dao.get_all()
        matching = [p for p in persons if person_name.lower() in p.name.lower()]
        if not matching:
            return []

        person_ids = {p.id for p in matching}
        from pixelvault.database.connection import get_connection
        conn = get_connection()
        placeholders = ",".join("?" * len(person_ids))
        rows = conn.execute(
            f"SELECT DISTINCT asset_id FROM faces WHERE person_group_id IN ({placeholders}) LIMIT ?",
            list(person_ids) + [limit],
        ).fetchall()

        return [
            SearchResult(asset_id=r["asset_id"], score=1.0, match_type="person")
            for r in rows
        ]

    def search_by_color(self, color_hex: str, limit: int = 100) -> List[SearchResult]:
        asset_ids = self.metadata_dao.search_by_color(color_hex, limit)
        return [
            SearchResult(asset_id=aid, score=1.0, match_type="color")
            for aid in asset_ids
        ]

    def search_by_tag(self, tag_name: str, limit: int = 100) -> List[SearchResult]:
        tags = self.tag_dao.get_all()
        matching = [t for t in tags if tag_name.lower() in t.name.lower()]
        if not matching:
            return []

        results = []
        for tag in matching:
            asset_ids = self.asset_tag_dao.search_by_tag(tag.id, limit)
            for aid in asset_ids:
                results.append(SearchResult(asset_id=aid, score=1.0, match_type="tag"))

        return results[:limit]
