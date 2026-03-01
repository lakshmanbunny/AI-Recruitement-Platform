import os
from typing import List
import google.generativeai as genai
from ragas.embeddings import BaseRagasEmbeddings
from ragas.run_config import RunConfig
from config.logging_config import get_logger
from core.settings import settings

logger = get_logger(__name__)

class GoogleGenerativeAIEmbeddingsAdapter(BaseRagasEmbeddings):
    """
    Custom embedding adapter for RAGAS.
    Bypasses Langchain wrappers to avoid API versioning issues (e.g., v1beta 404s).
    Uses the official google.generativeai python SDK directly hitting the v1 endpoint.
    """
    def __init__(self, model_name: str = "models/gemini-embedding-001"):
        super().__init__()
        self.model_name = model_name
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        logger.info(f"Initialized GoogleGenerativeAIEmbeddingsAdapter with model: {model_name}")

    def embed_query(self, text: str) -> List[float]:
        return self.embed_text(text)

    def embed_text(self, text: str) -> List[float]:
        try:
            # Task type can be retrieved_document or retrieval_query, default to retrieval_query for single
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_query",
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"[GoogleEmbeddingAdapter] Error embedding text: {e}")
            # Fallback to zero vector if absolutely needed, though it's better to let it fail loudly
            raise e

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Google Generative AI supports batch embedding
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=texts,
                task_type="retrieval_document",
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"[GoogleEmbeddingAdapter] Error embedding texts: {e}")
            raise e

    def set_run_config(self, run_config: RunConfig):
        # Handle optional run config from RAGAS if needed
        pass

    async def aembed_query(self, text: str) -> List[float]:
        # We process sync for stability in the worker process, but RAGAS might call async variants.
        # Fallback to sync.
        return self.embed_query(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embed_documents(texts)
