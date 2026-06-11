import time
import json
from cachetools import TTLCache, LRUCache
from typing import Optional, Any

from ..config import get_config


class CacheManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        config = get_config()

        self._summary_cache: LRUCache = LRUCache(maxsize=100)
        self._keyword_cache: LRUCache = LRUCache(maxsize=100)
        self._vector_cache: LRUCache = LRUCache(maxsize=1000)
        self._ttl_cache: TTLCache = TTLCache(maxsize=1000, ttl=config.ai_cache_ttl)

    def get_summary(self, paper_id: int) -> Optional[str]:
        return self._summary_cache.get(paper_id)

    def set_summary(self, paper_id: int, summary: str):
        self._summary_cache[paper_id] = summary

    def get_keywords(self, paper_id: int) -> Optional[list[str]]:
        return self._keyword_cache.get(paper_id)

    def set_keywords(self, paper_id: int, keywords: list[str]):
        self._keyword_cache[paper_id] = keywords

    def get_vector(self, paper_id: int) -> Optional[Any]:
        return self._vector_cache.get(paper_id)

    def set_vector(self, paper_id: int, vector: Any):
        self._vector_cache[paper_id] = vector

    def get_ttl(self, key: str) -> Optional[Any]:
        return self._ttl_cache.get(key)

    def set_ttl(self, key: str, value: Any):
        self._ttl_cache[key] = value

    def clear_paper_cache(self, paper_id: int):
        self._summary_cache.pop(paper_id, None)
        self._keyword_cache.pop(paper_id, None)
        self._vector_cache.pop(paper_id, None)

    def clear_all(self):
        self._summary_cache.clear()
        self._keyword_cache.clear()
        self._vector_cache.clear()
        self._ttl_cache.clear()


def get_cache_manager() -> CacheManager:
    return CacheManager()
