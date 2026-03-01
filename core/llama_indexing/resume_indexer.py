import os
import traceback
from llama_index.core import Document, VectorStoreIndex, StorageContext, load_index_from_storage, Settings
from llama_index.embeddings.gemini import GeminiEmbedding
from core.settings import settings
from config.logging_config import get_logger
from .metadata_utils import chunk_resume_sections

# Ensure absolute path resolution so API and Worker both target /backend/storage
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_INDEX_DIR = os.path.join(PROJECT_ROOT, "backend", "storage", "llama_resume.index")

logger = get_logger(__name__)

class ResumeLlamaIndexer:
    def __init__(self, persist_dir=DEFAULT_INDEX_DIR):
        self.persist_dir = persist_dir
        # Explicitly use specialized GeminiEmbedding for LlamaIndex
        self.embed_model = GeminiEmbedding(
            api_key=settings.GOOGLE_API_KEY, 
            model_name="models/gemini-embedding-001"
        )
        Settings.embed_model = self.embed_model
        # Ensure we use a chunk size that matches our metadata strategy
        Settings.chunk_size = 1024
        # Enable conservative batching to handle large candidate pools reliably
        Settings.embed_batch_size = 10
        
        self.index = None
        if not os.path.exists("storage"):
            os.makedirs("storage")

    def is_llama_index_ready(self):
        """Health check to verify if index is loaded and retriever can be initialized."""
        try:
            if not self.index:
                if not self._try_load_index():
                    return False
            # Test retriever initialization
            self.index.as_retriever()
            return True
        except:
            logger.error(f"[LLAMA HEALTH] Check failed: {traceback.format_exc()}")
            return False

    def build_index(self, resume_dicts, force_rebuild=False):
        try:
            if not force_rebuild and self._try_load_index():
                logger.info("[LLAMA INDEX LOADED] Index already exists and was loaded from storage.")
                return

            logger.info("[LLAMA INDEX BUILDING] Creating fresh LlamaIndex from resume data...")
            documents = []
            for resume in resume_dicts:
                chunks = chunk_resume_sections(resume)
                for chunk in chunks:
                    doc = Document(
                        text=chunk["text"],
                        metadata=chunk["metadata"],
                        excluded_llm_metadata_keys=["candidate_id"],
                        excluded_embed_metadata_keys=["candidate_id", "candidate_name"]
                    )
                    documents.append(doc)
            
            logger.info(f"Created {len(documents)} LlamaIndex documents/chunks.")
            
            if not documents:
                logger.warning("[LLAMA INDEX] No documents created. Skipping index build.")
                return

            # Ensure persist directory exists
            if not os.path.exists(self.persist_dir):
                os.makedirs(self.persist_dir, exist_ok=True)

            # Use the optimized from_documents with progress bar
            logger.info(f"[LLAMA INDEX] Indexing {len(documents)} chunks (Batch Size: {Settings.embed_batch_size})...")
            self.index = VectorStoreIndex.from_documents(
                documents, 
                show_progress=True,
                embed_model=self.embed_model
            )
            
            self.index.storage_context.persist(persist_dir=self.persist_dir)
            logger.info(f"[LLAMA INDEX BUILT] Persisted {len(documents)} units to {self.persist_dir}")
        except Exception as e:
            logger.error(f"[LLAMA INDEX ERROR] Build failed: {traceback.format_exc()}")
            raise e

    def _try_load_index(self):
        if not os.path.exists(self.persist_dir) or not os.listdir(self.persist_dir):
            return False
        try:
            storage_context = StorageContext.from_defaults(persist_dir=self.persist_dir)
            self.index = load_index_from_storage(storage_context, embed_model=self.embed_model)
            return True
        except Exception as e:
            logger.warning(f"Failed to load LlamaIndex: {traceback.format_exc()}")
            return False

    def get_retriever(self, similarity_top_k=20, **kwargs):
        if not self.index:
            if not self._try_load_index():
                raise ValueError("Index not built or loaded.")
        return self.index.as_retriever(similarity_top_k=similarity_top_k, **kwargs)
