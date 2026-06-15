import logging
from typing import Optional, List, Tuple

import numpy as np

from pixelvault.config import FACE_VECTOR_DIM, MODEL_DIR

logger = logging.getLogger(__name__)


class FaceEngine:
    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        self.model_path = model_path or str(MODEL_DIR / "insightface")
        self.device = device
        self._detector = None
        self._recognizer = None
        self._initialized = False

    def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            import insightface
            from insightface.app import FaceAnalysis

            self._detector = FaceAnalysis(name="buffalo_l", root=str(MODEL_DIR))
            self._detector.prepare(ctx_id=0 if self.device == "cuda" else -1, det_size=(640, 640))
            self._initialized = True
            logger.info("FaceEngine initialized with InsightFace")
            return True
        except ImportError:
            logger.warning("insightface not installed, face detection disabled")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize FaceEngine: {e}")
            return False

    def detect_faces(self, image: np.ndarray) -> List[dict]:
        if not self._initialized:
            if not self.initialize():
                return []

        try:
            faces = self._detector.get(image)
            results = []
            for face in faces:
                bbox = face.bbox.astype(int).tolist()
                results.append({
                    "bbox": bbox,
                    "confidence": float(face.det_score),
                    "landmark": face.kps.tolist() if hasattr(face, "kps") else None,
                    "feature": face.embedding if hasattr(face, "embedding") else None,
                })
            return results
        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return []

    def extract_features(self, image: np.ndarray) -> List[Tuple[dict, np.ndarray]]:
        if not self._initialized:
            if not self.initialize():
                return []

        try:
            faces = self._detector.get(image)
            results = []
            for face in faces:
                bbox = face.bbox.astype(int).tolist()
                info = {
                    "bbox": bbox,
                    "confidence": float(face.det_score),
                    "landmark": face.kps.tolist() if hasattr(face, "kps") else None,
                }
                feature = face.embedding if hasattr(face, "embedding") else np.zeros(FACE_VECTOR_DIM, dtype=np.float32)
                if feature is not None:
                    feature = feature / (np.linalg.norm(feature) + 1e-8)
                results.append((info, feature))
            return results
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return []

    def align_face(self, image: np.ndarray, bbox: List[int], landmark: Optional[List[List[float]]] = None) -> Optional[np.ndarray]:
        try:
            import cv2
            x1, y1, x2, y2 = bbox
            padding = int(max(x2 - x1, y2 - y1) * 0.2)
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(image.shape[1], x2 + padding)
            y2 = min(image.shape[0], y2 + padding)
            aligned = image[y1:y2, x1:x2]
            aligned = cv2.resize(aligned, (112, 112))
            return aligned
        except Exception as e:
            logger.error(f"Face alignment failed: {e}")
            return None

    @property
    def is_available(self) -> bool:
        return self._initialized or self.initialize()
