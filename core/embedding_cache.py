import json
import hashlib
import os
from config.logging_config import get_logger

logger = get_logger(__name__)

class EmbeddingCache:
    """
    Handles local caching of embeddings to minimize API calls.
    """
    def __init__(self, cache_path="storage/embedding_cache.json"):
        self.cache_path = cache_path
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Loads cache from disk if it exists."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load cache: {str(e)}")
        return {}

    def _save_cache(self):
        """Saves current cache state to disk."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, 'w') as f:
                json.dump(self._cache, f)
        except Exception as e:
            logger.error(f"Failed to save cache: {str(e)}")

    def _get_hash(self, text: str) -> str:
        """Generates a stable hash for the given text."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def get_embedding(self, text: str) -> list[float] | None:
        """Retrieves an embedding from cache if it exists."""
        key = self._get_hash(text)
        if key in self._cache:
            logger.info("Cache HIT: Using stored embedding")
            return self._cache[key]
        return None

    def add_to_cache(self, text: str, vector: list[float]):
        """Adds a new embedding to the cache and persists to disk."""
        key = self._get_hash(text)
        self._cache[key] = vector
        logger.info("Cache MISS: Storing new embedding")
        self._save_cache()
