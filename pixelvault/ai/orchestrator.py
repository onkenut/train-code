import logging
from typing import List, Optional, Callable

import numpy as np

from pixelvault.config import AI_BATCH_SIZE
from pixelvault.database.dao import AssetDAO, ClipVectorDAO, FaceDAO
from pixelvault.database.models import Asset, ClipVector, Face, AssetStatus
from pixelvault.ai.clip_engine import CLIPEngine
from pixelvault.ai.face_engine import FaceEngine

logger = logging.getLogger(__name__)


class AIOrchestrator:
    def __init__(self, device: str = "cpu"):
        self.asset_dao = AssetDAO()
        self.clip_dao = ClipVectorDAO()
        self.face_dao = FaceDAO()
        self.clip_engine = CLIPEngine(device=device)
        self.face_engine = FaceEngine(device=device)
        self._running = False
        self._progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable) -> None:
        self._progress_callback = callback

    def _notify_progress(self, message: str, current: int = 0, total: int = 0) -> None:
        if self._progress_callback:
            self._progress_callback(message, current, total)

    def initialize(self) -> bool:
        clip_ok = self.clip_engine.initialize()
        face_ok = self.face_engine.initialize()
        return clip_ok or face_ok

    def process_pending_assets(self, limit: int = 100) -> int:
        assets = self.asset_dao.get_pending(limit)
        if not assets:
            return 0

        self._running = True
        total = len(assets)
        processed = 0

        self._notify_progress("AI processing...", 0, total)

        batch_images = []
        batch_assets = []

        for i, asset in enumerate(assets):
            if not self._running:
                break

            try:
                image = self._load_image(asset)
                if image is None:
                    self.asset_dao.update_status(asset.id, AssetStatus.CORRUPT)
                    continue

                batch_images.append(image)
                batch_assets.append(asset)

                if len(batch_images) >= AI_BATCH_SIZE:
                    self._process_batch(batch_images, batch_assets)
                    processed += len(batch_images)
                    self._notify_progress(f"AI processing: {processed}/{total}", processed, total)
                    batch_images = []
                    batch_assets = []

            except Exception as e:
                logger.error(f"Failed to process asset {asset.id}: {e}")
                self.asset_dao.update_status(asset.id, AssetStatus.CORRUPT)

        if batch_images:
            self._process_batch(batch_images, batch_assets)
            processed += len(batch_images)

        self._running = False
        self._notify_progress("AI processing complete", total, total)
        return processed

    def _process_batch(self, images: List[np.ndarray], assets: List[Asset]) -> None:
        if self.clip_engine.is_available:
            vectors = self.clip_engine.encode_images_batch(images)
            clip_records = []
            for asset, vec in zip(assets, vectors):
                clip_records.append(ClipVector(
                    asset_id=asset.id,
                    vector_type="image",
                    frame_index=0,
                    vector_data=vec,
                ))
            self.clip_dao.insert_batch(clip_records)

        if self.face_engine.is_available:
            for asset, image in zip(assets, images):
                faces_data = self.face_engine.extract_features(image)
                if faces_data:
                    import json
                    face_records = []
                    for info, feature in faces_data:
                        face_records.append(Face(
                            asset_id=asset.id,
                            bbox_json=json.dumps(info["bbox"]),
                            feature_vector=feature,
                            confidence=info.get("confidence", 0.0),
                        ))
                    self.face_dao.insert_batch(face_records)

        for asset in assets:
            self.asset_dao.update_status(asset.id, AssetStatus.INDEXED)

    def _load_image(self, asset: Asset) -> Optional[np.ndarray]:
        try:
            import cv2
            if asset.media_type == "image":
                img = cv2.imread(asset.absolute_path)
                if img is None:
                    return None
                return img
            elif asset.media_type == "video":
                cap = cv2.VideoCapture(asset.absolute_path)
                ret, frame = cap.read()
                cap.release()
                if not ret:
                    return None
                return frame
        except Exception as e:
            logger.error(f"Failed to load image {asset.absolute_path}: {e}")
            return None

    def stop(self) -> None:
        self._running = False

    def generate_clip_vector(self, asset_id: int) -> bool:
        asset = self.asset_dao.get_by_id(asset_id)
        if not asset:
            return False
        image = self._load_image(asset)
        if image is None:
            return False

        vector = self.clip_engine.encode_image(image)
        record = ClipVector(asset_id=asset_id, vector_type="image", frame_index=0, vector_data=vector)
        self.clip_dao.insert(record)
        return True

    def detect_faces_for_asset(self, asset_id: int) -> int:
        asset = self.asset_dao.get_by_id(asset_id)
        if not asset:
            return 0
        image = self._load_image(asset)
        if image is None:
            return 0

        faces_data = self.face_engine.extract_features(image)
        if not faces_data:
            return 0

        import json
        count = 0
        for info, feature in faces_data:
            face = Face(
                asset_id=asset_id,
                bbox_json=json.dumps(info["bbox"]),
                feature_vector=feature,
                confidence=info.get("confidence", 0.0),
            )
            self.face_dao.insert(face)
            count += 1
        return count
