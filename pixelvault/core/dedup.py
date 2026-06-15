import logging
from typing import List, Tuple, Optional
from collections import defaultdict

from pixelvault.config import PHASH_THRESHOLD
from pixelvault.database.dao import AssetDAO
from pixelvault.database.models import Asset, DuplicateGroup, SimilarGroup
from pixelvault.core.hasher import phash_similarity

logger = logging.getLogger(__name__)


class Deduplicator:
    def __init__(self):
        self.asset_dao = AssetDAO()

    def find_exact_duplicates(self) -> List[DuplicateGroup]:
        return self.asset_dao.find_duplicates_by_hash()

    def find_similar_images(self, assets: List[Asset], threshold: float = PHASH_THRESHOLD) -> List[SimilarGroup]:
        groups = []
        visited = set()

        for i, a1 in enumerate(assets):
            if a1.id in visited or not a1.perceptual_hash:
                continue
            group = SimilarGroup(assets=[a1], similarity=1.0)
            visited.add(a1.id)

            for j, a2 in enumerate(assets):
                if j <= i or a2.id in visited or not a2.perceptual_hash:
                    continue
                sim = phash_similarity(a1.perceptual_hash, a2.perceptual_hash)
                if sim >= threshold:
                    group.assets.append(a2)
                    visited.add(a2.id)

            if len(group.assets) > 1:
                groups.append(group)

        return groups

    def suggest_cleanup(self, group: List[Asset], strategy: str = "highest_resolution") -> Tuple[Asset, List[Asset]]:
        if not group:
            raise ValueError("Empty group")

        if strategy == "highest_resolution":
            keep = max(group, key=lambda a: (a.width or 0) * (a.height or 0))
        elif strategy == "largest_file":
            keep = max(group, key=lambda a: a.file_size)
        elif strategy == "newest":
            keep = max(group, key=lambda a: a.modified_time or "")
        else:
            keep = group[0]

        to_remove = [a for a in group if a.id != keep.id]
        return keep, to_remove

    def remove_assets(self, assets: List[Asset], use_trash: bool = True) -> List[bool]:
        results = []
        for asset in assets:
            try:
                filepath = asset.absolute_path
                if use_trash:
                    try:
                        import send2trash
                        send2trash.send2trash(filepath)
                    except ImportError:
                        import os
                        os.remove(filepath)
                else:
                    import os
                    os.remove(filepath)
                self.asset_dao.delete(asset.id)
                results.append(True)
                logger.info(f"Removed: {filepath}")
            except Exception as e:
                results.append(False)
                logger.error(f"Failed to remove {asset.absolute_path}: {e}")
        return results

    def scan_similar_by_phash(self, library_id: Optional[int] = None) -> List[SimilarGroup]:
        if library_id:
            assets = self.asset_dao.get_by_library(library_id, limit=100000)
        else:
            from pixelvault.database.connection import get_connection
            rows = get_connection().execute(
                "SELECT * FROM assets WHERE perceptual_hash IS NOT NULL AND status = 'indexed'"
            ).fetchall()
            assets = [Asset(**dict(r)) for r in rows]

        assets_with_hash = [a for a in assets if a.perceptual_hash]
        return self.find_similar_images(assets_with_hash)
