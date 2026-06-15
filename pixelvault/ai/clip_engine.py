import logging
from typing import Optional, List, Tuple

import numpy as np

from pixelvault.config import CLIP_VECTOR_DIM, MODEL_DIR, AI_BATCH_SIZE

logger = logging.getLogger(__name__)


class CLIPEngine:
    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        self.model_path = model_path or str(MODEL_DIR / "clip.onnx")
        self.device = device
        self._session = None
        self._tokenizer = None
        self._preprocess = None
        self._initialized = False

    def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            import onnxruntime as ort

            providers = ["CPUExecutionProvider"]
            if self.device == "cuda":
                providers.insert(0, "CUDAExecutionProvider")

            self._session = ort.InferenceSession(self.model_path, providers=providers)
            self._initialized = True
            logger.info(f"CLIP model loaded from {self.model_path}")
            return True
        except ImportError:
            logger.warning("onnxruntime not installed, CLIP engine disabled")
            return False
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            return False

    def encode_image(self, image_array: np.ndarray) -> np.ndarray:
        if not self._initialized:
            if not self.initialize():
                return np.zeros(CLIP_VECTOR_DIM, dtype=np.float32)

        try:
            preprocessed = self._preprocess_image(image_array)
            input_name = self._session.get_inputs()[0].name
            output = self._session.run(None, {input_name: preprocessed})
            vector = output[0].flatten()
            vector = vector / (np.linalg.norm(vector) + 1e-8)
            return vector.astype(np.float32)
        except Exception as e:
            logger.error(f"Image encoding failed: {e}")
            return np.zeros(CLIP_VECTOR_DIM, dtype=np.float32)

    def encode_images_batch(self, images: List[np.ndarray]) -> np.ndarray:
        if not self._initialized:
            if not self.initialize():
                return np.zeros((len(images), CLIP_VECTOR_DIM), dtype=np.float32)

        results = []
        for i in range(0, len(images), AI_BATCH_SIZE):
            batch = images[i : i + AI_BATCH_SIZE]
            batch_array = np.array([self._preprocess_image(img) for img in batch])
            try:
                input_name = self._session.get_inputs()[0].name
                output = self._session.run(None, {input_name: batch_array})
                vectors = output[0].reshape(len(batch), -1)
                norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-8
                vectors = (vectors / norms).astype(np.float32)
                results.append(vectors)
            except Exception as e:
                logger.error(f"Batch encoding failed: {e}")
                results.append(np.zeros((len(batch), CLIP_VECTOR_DIM), dtype=np.float32))

        return np.vstack(results) if results else np.zeros((0, CLIP_VECTOR_DIM), dtype=np.float32)

    def encode_text(self, text: str) -> np.ndarray:
        if not self._initialized:
            if not self.initialize():
                return np.zeros(CLIP_VECTOR_DIM, dtype=np.float32)

        try:
            tokens = self._tokenize(text)
            input_name = self._session.get_inputs()[0].name
            output = self._session.run(None, {input_name: tokens})
            vector = output[0].flatten()
            vector = vector / (np.linalg.norm(vector) + 1e-8)
            return vector.astype(np.float32)
        except Exception as e:
            logger.error(f"Text encoding failed: {e}")
            return np.zeros(CLIP_VECTOR_DIM, dtype=np.float32)

    def encode_texts_batch(self, texts: List[str]) -> np.ndarray:
        results = []
        for text in texts:
            vec = self.encode_text(text)
            results.append(vec)
        return np.array(results, dtype=np.float32)

    def compute_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        return float(np.dot(vec1, vec2))

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        import cv2
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        elif image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        image = cv2.resize(image, (224, 224), interpolation=cv2.INTER_LINEAR)
        image = image.astype(np.float32) / 255.0
        mean = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
        std = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
        image = (image - mean) / std
        image = np.transpose(image, (2, 0, 1))
        return np.expand_dims(image, axis=0).astype(np.float32)

    def _tokenize(self, text: str) -> np.ndarray:
        try:
            from clip_tokenizer import SimpleTokenizer
            tokenizer = SimpleTokenizer()
            tokens = tokenizer.encode(text)
            tokens = tokens[:77]
            padding = [0] * (77 - len(tokens))
            return np.array([tokens + padding], dtype=np.int64)
        except ImportError:
            logger.warning("clip_tokenizer not available, using dummy tokens")
            return np.zeros((1, 77), dtype=np.int64)

    @property
    def is_available(self) -> bool:
        return self._initialized or self.initialize()
