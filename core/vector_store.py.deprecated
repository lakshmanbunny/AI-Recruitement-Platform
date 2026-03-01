import faiss
import numpy as np
import pickle
import os
from config.logging_config import get_logger

logger = get_logger(__name__)

class ResumeVectorStore:
    """
    Persistent vector store using FAISS for candidate resume section embeddings.
    """
    def __init__(self, index_path="storage/vector.index", metadata_path="storage/metadata.pkl"):
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.dimension = 3072  # Gemini embedding dimension (gemini-embedding-001)
        self.index = None
        self.metadata = []  # List of {"candidate_id": str, "section": str}
        
        self._load_index()

    def _load_index(self):
        """Loads FAISS index and metadata from disk if available."""
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)
                logger.info("Loaded existing vector index and metadata")
            except Exception as e:
                logger.error(f"Failed to load vector store: {str(e)}")
                self._create_empty_index()
        else:
            self._create_empty_index()

    def _create_empty_index(self):
        """Initializes a new empty FAISS index."""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata = []
        logger.info("Created new vector index")

    def _save_index(self):
        """Persists the FAISS index and metadata to disk."""
        try:
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            faiss.write_index(self.index, self.index_path)
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.metadata, f)
        except Exception as e:
            logger.error(f"Failed to save vector store: {str(e)}")

    def add_candidate_section_embedding(self, candidate_id: str, section_name: str, vector: list[float]):
        """
        Stores an embedding vector in FAISS with duplication check.
        """
        # Check for duplication
        if any(m["candidate_id"] == candidate_id and m["section"] == section_name for m in self.metadata):
            logger.info(f"Vector already exists for {candidate_id} - {section_name}, skipping insertion")
            return

        # FAISS expects float32 np arrays
        vector_np = np.array([vector]).astype('float32')
        self.index.add(vector_np)
        
        self.metadata.append({
            "candidate_id": candidate_id,
            "section": section_name
        })
        
        logger.info(f"Vector added to FAISS for {candidate_id} - {section_name}")
        self._save_index()

    def get_all_embeddings(self) -> dict:
        """
        Maintains backward compatibility for the retrieval node.
        Returns: {candidate_id: {section_name: vector}}
        """
        result = {}
        # This is slightly inefficient but keeps current retrieval logic working without major refactor
        # In a real system, we'd use index.search() directly in retrieval_node
        for i, meta in enumerate(self.metadata):
            cid = meta["candidate_id"]
            sec = meta["section"]
            vector = self.index.reconstruct(i).tolist()
            
            if cid not in result:
                result[cid] = {}
            result[cid][sec] = vector
            
        return result
