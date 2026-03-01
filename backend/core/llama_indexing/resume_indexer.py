import os
import faiss
from llama_index.core import Document, VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.embeddings.gemini import GeminiEmbedding
from core.settings import settings
from config.logging_config import get_logger
from .metadata_utils import chunk_resume_sections

logger = get_logger(__name__)

class ResumeLlamaIndexer:
    """
    Indexer for candidate resumes using LlamaIndex and FAISS.
    """
    def __init__(self, persist_dir="storage/llama_resume.index"):
        self.persist_dir = persist_dir
        self.embed_model = GeminiEmbedding(api_key=settings.GOOGLE_API_KEY, model_name="models/gemini-embedding-001")
        self.index = None
        
        # Ensure directory exists
        if not os.path.exists("storage"):
            os.makedirs("storage")

    def build_index(self, resume_dicts, force_rebuild=False):
        """
        Builds the LlamaIndex from a list of resume dictionaries.
        """
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
                    excluded_llm_metadata_keys=["candidate_id"], # Hide from LLM if needed
                    excluded_embed_metadata_keys=["candidate_id", "candidate_name"]
                )
                documents.append(doc)
        
        logger.info(f"Created {len(documents)} LlamaIndex documents/chunks.")

        # Initialize FAISS vector store
        d = 768 # Gemini embedding dimension
        faiss_index = faiss.IndexFlatL2(d)
        vector_store = FaissVectorStore(faiss_index=faiss_index)
        
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        self.index = VectorStoreIndex.from_documents(
            documents, 
            storage_context=storage_context,
            embed_model=self.embed_model
        )
        
        # Persist to disk
        self.index.storage_context.persist(persist_dir=self.persist_dir)
        logger.info(f"[LLAMA INDEX BUILT] Persisted to {self.persist_dir}")

    def _try_load_index(self):
        """
        Tries to load an existing index from the persist directory.
        """
        if not os.path.exists(self.persist_dir):
            return False
        
        try:
            # Initialize FAISS vector store for loading
            vector_store = FaissVectorStore.from_persist_dir(self.persist_dir)
            storage_context = StorageContext.from_defaults(
                vector_store=vector_store, persist_dir=self.persist_dir
            )
            self.index = load_index_from_storage(
                storage_context, 
                embed_model=self.embed_model
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to load LlamaIndex: {str(e)}. A fresh build might be needed.")
            return False

    def get_query_engine(self):
        """
        Returns a query engine for the index.
        """
        if not self.index:
            if not self._try_load_index():
                raise ValueError("Index not built or loaded.")
        
        return self.index.as_query_engine()
    
    def get_retriever(self, similarity_top_k=20):
        """
        Returns a retriever for the index.
        """
        if not self.index:
            if not self._try_load_index():
                raise ValueError("Index not built or loaded.")
        
        return self.index.as_retriever(similarity_top_k=similarity_top_k)

    def is_llama_index_ready(self) -> bool:
        """
        Returns True if the persisted LlamaIndex exists on disk and can be loaded.
        Called by pipeline_service to decide whether to bypass the full rebuild.
        """
        if not os.path.exists(self.persist_dir):
            return False
        # Check for the docstore JSON which is always written by LlamaIndex persist()
        docstore_path = os.path.join(self.persist_dir, "docstore.json")
        return os.path.exists(docstore_path)
