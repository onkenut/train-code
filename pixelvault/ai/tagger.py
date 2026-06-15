import logging
from typing import List, Tuple

import numpy as np

from pixelvault.config import SCENE_TAGS
from pixelvault.database.dao import TagDAO, AssetTagDAO, ClipVectorDAO
from pixelvault.database.models import Tag
from pixelvault.ai.clip_engine import CLIPEngine

logger = logging.getLogger(__name__)

DEFAULT_TAG_TEMPLATES = [
    ("indoor", "scene"), ("outdoor", "scene"), ("landscape", "scene"),
    ("portrait", "scene"), ("animal", "object"), ("architecture", "scene"),
    ("food", "object"), ("vehicle", "object"), ("nature", "scene"),
    ("sky", "scene"), ("water", "scene"), ("night", "scene"),
    ("sunset", "scene"), ("beach", "scene"), ("mountain", "scene"),
    ("forest", "scene"), ("city", "scene"), ("street", "scene"),
    ("room", "scene"), ("garden", "scene"), ("snow", "scene"),
    ("rain", "scene"), ("black and white", "style"), ("colorful", "style"),
    ("minimalist", "style"), ("vintage", "style"), ("modern", "style"),
]


class AutoTagger:
    def __init__(self, clip_engine: CLIPEngine):
        self.clip_engine = clip_engine
        self.tag_dao = TagDAO()
        self.asset_tag_dao = AssetTagDAO()
        self._ensure_tags()

    def _ensure_tags(self) -> None:
        existing = {t.name for t in self.tag_dao.get_all()}
        for name, category in DEFAULT_TAG_TEMPLATES:
            if name not in existing:
                self.tag_dao.insert(Tag(name=name, category=category))

    def auto_tag_asset(self, asset_id: int, threshold: float = 0.25) -> List[Tuple[str, float]]:
        if not self.clip_engine.is_available:
            return []

        clip_dao = ClipVectorDAO()
        vectors = clip_dao.get_by_asset(asset_id)
        if not vectors:
            return []

        _, image_vector = vectors[0]

        tags = self.tag_dao.get_all()
        tag_names = [t.name for t in tags]
        tag_ids = [t.id for t in tags]

        text_vectors = self.clip_engine.encode_texts_batch(tag_names)

        similarities = text_vectors @ image_vector

        results = []
        pairs = []
        for i, (sim, tag_id, tag_name) in enumerate(zip(similarities, tag_ids, tag_names)):
            if sim >= threshold:
                results.append((tag_name, float(sim)))
                pairs.append((asset_id, tag_id, float(sim)))

        if pairs:
            self.asset_tag_dao.assign_batch(pairs)

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def auto_tag_batch(self, asset_ids: List[int], threshold: float = 0.25) -> None:
        for i, aid in enumerate(asset_ids):
            try:
                self.auto_tag_asset(aid, threshold)
            except Exception as e:
                logger.error(f"Auto-tag failed for asset {aid}: {e}")
