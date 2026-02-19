from google import genai
from core.settings import settings
from config.logging_config import get_logger
from core.embedding_cache import EmbeddingCache

logger = get_logger(__name__)

class EmbeddingService:
    """
    Service to generate embeddings using Gemini API.
    """
    def __init__(self):
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.model_id = "models/gemini-embedding-001"
        self.cache = EmbeddingCache()

    def generate_embedding(self, text: str) -> list[float]:
        """
        Generates an embedding vector for the given text.
        """
        # Check cache first
        cached_vector = self.cache.get_embedding(text)
        if cached_vector:
            return cached_vector

        # Cache MISS: Generate using Gemini
        logger.info(f"Generating new embedding for text of length: {len(text)}")
        try:
            result = self.client.models.embed_content(
                model=self.model_id,
                contents=[text]
            )
            vector = result.embeddings[0].values
            
            # Store in cache
            self.cache.add_to_cache(text, vector)
            
            return vector
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            raise e
