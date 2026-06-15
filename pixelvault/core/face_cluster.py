import logging
from typing import List, Tuple

import numpy as np
from sklearn.cluster import DBSCAN

from pixelvault.database.dao import FaceDAO, PersonDAO
from pixelvault.database.models import Face, Person

logger = logging.getLogger(__name__)


class FaceClusterEngine:
    def __init__(self, eps: float = 0.6, min_samples: int = 2):
        self.face_dao = FaceDAO()
        self.person_dao = PersonDAO()
        self.eps = eps
        self.min_samples = min_samples

    def cluster_all(self) -> int:
        vectors = self.face_dao.get_all_vectors()
        if not vectors:
            return 0

        face_ids = [v[0] for v in vectors]
        matrix = np.array([v[1] for v in vectors])

        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8
        matrix_norm = matrix / norms

        clustering = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric="cosine").fit(matrix_norm)
        labels = clustering.labels_

        person_map = {}
        new_count = 0

        for face_id, label in zip(face_ids, labels):
            if label == -1:
                self.face_dao.assign_person(face_id, None)
                continue

            if label not in person_map:
                person = Person(name=f"unnamed_{label}")
                pid = self.person_dao.insert(person)
                person_map[label] = pid
                new_count += 1

            self.face_dao.assign_person(face_id, person_map[label])

        logger.info(f"Face clustering complete: {new_count} persons identified")
        return new_count

    def incremental_cluster(self, new_face_ids: List[int]) -> int:
        all_vectors = self.face_dao.get_all_vectors()
        if not all_vectors:
            return 0

        face_ids = [v[0] for v in all_vectors]
        matrix = np.array([v[1] for v in all_vectors])

        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8
        matrix_norm = matrix / norms

        clustering = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric="cosine").fit(matrix_norm)
        labels = clustering.labels_

        person_map = {}
        new_count = 0

        existing_persons = self.person_dao.get_all()
        for p in existing_persons:
            pass

        for face_id, label in zip(face_ids, labels):
            if label == -1:
                continue
            if label not in person_map:
                person = Person(name=f"unnamed_{label}")
                pid = self.person_dao.insert(person)
                person_map[label] = pid
                new_count += 1
            self.face_dao.assign_person(face_id, person_map[label])

        return new_count

    def merge_persons(self, source_id: int, target_id: int) -> None:
        self.person_dao.merge(source_id, target_id)

    def rename_person(self, person_id: int, name: str) -> None:
        self.person_dao.rename(person_id, name)
