import os
import faiss
import pickle
import numpy as np
from typing import List, Dict, Any
from core.embedding_service import EmbeddingService
from config.logging_config import get_logger

logger = get_logger(__name__)

class GitHubCodeVectorStore:
    """
    Persistent FAISS vector store for candidate GitHub repository content (READMEs, Code).
    """
    def __init__(self, index_path: str = "storage/github_vector.index", metadata_path: str = "storage/github_metadata.pkl"):
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.embedding_service = EmbeddingService()
        self.dimension = 3072  # gemini-embedding-001 dimension
        
        # Initialize or load FAISS index
        if os.path.exists(self.index_path):
            logger.info("Loading existing GitHub vector index")
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)
        else:
            logger.info("Creating new GitHub vector index")
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []  # List of {candidate_id, repo_name, type, chunk_text}

    def _chunk_text(self, text: str, chunk_size: int = 1000) -> List[str]:
        """Simple character-based chunking."""
        if not text:
            return []
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    def add_repo_content(self, candidate_id: str, repo_data: Dict[str, Any]):
        """
        Chunks, embeds, and stores repository content.
        repo_data: {name, description, readme, code_snippets: []}
        """
        repo_name = repo_data.get("name", "unknown")
        
        # Prepare content parts
        content_parts = [
            {"type": "meta", "text": f"Repo: {repo_name}. Description: {repo_data.get('description', '')}"},
            {"type": "readme", "text": repo_data.get("readme", "")}
        ]
        
        for idx, snippet in enumerate(repo_data.get("code_snippets", [])):
            content_parts.append({"type": f"code_{idx}", "text": snippet})

        for part in content_parts:
            chunks = self._chunk_text(part["text"])
            for chunk in chunks:
                # Check for duplicates (basic check)
                if any(m['candidate_id'] == candidate_id and m['repo_name'] == repo_name and m['chunk_text'] == chunk for m in self.metadata):
                    logger.debug(f"Chunk already exists for {candidate_id}/{repo_name}, skipping")
                    continue
                
                try:
                    embedding = self.embedding_service.generate_embedding(chunk)
                    vector = np.array([embedding]).astype('float32')
                    
                    self.index.add(vector)
                    self.metadata.append({
                        "candidate_id": candidate_id,
                        "repo_name": repo_name,
                        "type": part["type"],
                        "chunk_text": chunk
                    })
                    logger.info(f"Indexed GitHub chunk successfully for {candidate_id}")
                except Exception as e:
                    logger.error(f"Failed to index GitHub chunk for {candidate_id}: {str(e)}")

        self.save()

    def save(self):
        """Persists the index and metadata to disk."""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)
        logger.info(f"GitHub vector store saved. Total chunks: {len(self.metadata)}")

    def get_candidate_chunks(self, candidate_id: str) -> List[Dict]:
        """Returns all chunks associated with a candidate."""
        return [m for m in self.metadata if m['candidate_id'] == candidate_id]

    def search(self, query: str, candidate_id: str, top_k: int = 5) -> List[Dict]:
        """
        Performs similarity search for a specific candidate's repository content.
        """
        if self.index.ntotal == 0:
            return []

        try:
            # Generate query embedding
            query_vector = self.embedding_service.generate_embedding(query)
            query_np = np.array([query_vector]).astype('float32')
            
            # Search FAISS (get more than top_k to account for candidate filtering)
            distances, indices = self.index.search(query_np, k=min(self.index.ntotal, 50))
            
            results = []
            for idx in indices[0]:
                if idx == -1: continue
                meta = self.metadata[idx]
                if meta['candidate_id'] == candidate_id:
                    results.append(meta)
                    if len(results) >= top_k:
                        break
            
            return results
        except Exception as e:
            logger.error(f"GitHub RAG search failed for {candidate_id}: {str(e)}")
            return []
