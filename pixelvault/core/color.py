import logging
from typing import List, Tuple

import numpy as np
from PIL import Image

from pixelvault.config import PHASH_THRESHOLD
from pixelvault.database.dao import AssetDAO
from pixelvault.core.hasher import compute_phash, compute_dhash, phash_similarity

logger = logging.getLogger(__name__)


class ColorAnalyzer:
    def __init__(self, n_colors: int = 5):
        self.n_colors = n_colors

    def extract_dominant_colors(self, filepath: str) -> List[Tuple[str, float]]:
        try:
            from sklearn.cluster import KMeans
            img = Image.open(filepath).convert("RGB")
            img = img.resize((150, 150), Image.Resampling.LANCZOS)
            pixels = np.array(img).reshape(-1, 3)

            kmeans = KMeans(n_clusters=min(self.n_colors, len(pixels)), random_state=42, n_init="auto")
            kmeans.fit(pixels)

            counts = np.bincount(kmeans.labels_)
            total = sum(counts)

            colors = []
            for i, (center, count) in enumerate(zip(kmeans.cluster_centers_, counts)):
                hex_color = "#{:02x}{:02x}{:02x}".format(
                    int(center[0]), int(center[1]), int(center[2])
                )
                ratio = count / total
                colors.append((hex_color, round(ratio, 4)))

            colors.sort(key=lambda x: x[1], reverse=True)
            return colors
        except Exception as e:
            logger.warning(f"Color extraction failed for {filepath}: {e}")
            return []

    def find_by_color(self, target_hex: str, assets_limit: int = 100) -> List[int]:
        from pixelvault.database.dao import MetadataDAO
        meta_dao = MetadataDAO()
        return meta_dao.search_by_color(target_hex, assets_limit)
