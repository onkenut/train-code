import logging
from typing import List, Tuple, Dict

from pixelvault.database.models import SearchResult

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    result_lists: List[List[SearchResult]], k: int = 60
) -> List[SearchResult]:
    scores: Dict[int, float] = {}
    match_types: Dict[int, str] = {}

    for results in result_lists:
        for rank, result in enumerate(results):
            if result.asset_id not in scores:
                scores[result.asset_id] = 0.0
                match_types[result.asset_id] = result.match_type
            else:
                match_types[result.asset_id] = "hybrid"

            scores[result.asset_id] += 1.0 / (k + rank + 1)

    fused = [
        SearchResult(asset_id=aid, score=score, match_type=match_types[aid])
        for aid, score in scores.items()
    ]
    fused.sort(key=lambda x: x.score, reverse=True)
    return fused


def weighted_fusion(
    semantic_results: List[SearchResult],
    fts_results: List[SearchResult],
    semantic_weight: float = 0.6,
    fts_weight: float = 0.4,
) -> List[SearchResult]:
    scores: Dict[int, float] = {}
    match_types: Dict[int, str] = {}

    for result in semantic_results:
        scores[result.asset_id] = result.score * semantic_weight
        match_types[result.asset_id] = "semantic"

    for result in fts_results:
        if result.asset_id in scores:
            scores[result.asset_id] += result.score * fts_weight
            match_types[result.asset_id] = "hybrid"
        else:
            scores[result.asset_id] = result.score * fts_weight
            match_types[result.asset_id] = "fts"

    fused = [
        SearchResult(asset_id=aid, score=score, match_type=match_types[aid])
        for aid, score in scores.items()
    ]
    fused.sort(key=lambda x: x.score, reverse=True)
    return fused


def normalize_scores(results: List[SearchResult]) -> List[SearchResult]:
    if not results:
        return results

    scores = [r.score for r in results]
    max_score = max(scores) if scores else 1.0
    min_score = min(scores) if scores else 0.0
    range_score = max_score - min_score

    if range_score < 1e-8:
        return [SearchResult(asset_id=r.asset_id, score=1.0, match_type=r.match_type) for r in results]

    return [
        SearchResult(asset_id=r.asset_id, score=(r.score - min_score) / range_score, match_type=r.match_type)
        for r in results
    ]
