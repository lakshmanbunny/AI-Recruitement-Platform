import numpy as np
import re
from typing import List, Dict, Any
from config.logging_config import get_logger
from core.rag_evaluation.google_embedding_adapter import GoogleGenerativeAIEmbeddingsAdapter

logger = get_logger(__name__)

class DeterministicRetrievalEvaluator:
    """
    Zero-LLM Retrieval Quality Evaluation Engine.
    Computes Precision, Recall, Coverage, and Similarity strictly via deterministic rules.
    """
    def __init__(self):
        self.embedding_service = GoogleGenerativeAIEmbeddingsAdapter()
        
        # Stopwords for keyword extraction
        self.stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with",
            "about", "against", "between", "into", "through", "during", "before", "after",
            "above", "below", "from", "up", "down", "out", "off", "over", "under", "again",
            "further", "then", "once", "here", "there", "when", "where", "why", "how", "all",
            "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor",
            "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will",
            "just", "don", "should", "now", "we", "you", "they", "it", "is", "are", "am", "be",
            "been", "being", "have", "has", "had", "do", "does", "did", "our", "your", "their",
            "this", "that", "these", "those", "year", "years", "experience", "work", "job",
            "role", "team", "company", "project", "using", "used", "knowledge", "skill", "skills",
            "required", "preferred", "strong", "good", "excellent", "ability", "able", "must",
            "demonstrated", "proven", "understanding", "looking", "candidate"
        }

    def _extract_keywords(self, text: str) -> set:
        """Extract unique, lowercase alphanumeric keywords (excluding stopwords)."""
        words = re.findall(r'\b[a-z0-9]+\b', text.lower())
        return set(w for w in words if w not in self.stopwords and len(w) > 2)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 0.0
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

    def evaluate_retrieval(
        self, 
        candidate_id: str,
        jd_text: str, 
        jd_embedding: List[float],
        retrieved_chunks: List[Dict[str, Any]],
        total_corpus_chunks: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate retrieved chunks against JD text and embedding deterministicly.
        """
        try:
            logger.info(f"[Retrieval Gate] Starting evaluation for {candidate_id}")
            
            if not retrieved_chunks:
                logger.warning(f"[Retrieval Gate] No retrieved chunks for {candidate_id}. Providing empty metrics.")
                return self._empty_metrics()

            # 1. SIMILARITY SCORE: Average of top 3 chunks (Sustained Relevance)
            # Since LlamaIndex returns already sorted by similarity
            scores = [chunk.get("score", 0.0) for chunk in retrieved_chunks]
            top_3_scores = sorted(scores, reverse=True)[:3]
            avg_top_3_similarity = sum(top_3_scores) / len(top_3_scores) if top_3_scores else 0.0
            
            # Extract or dynamically compute Vector Embeddings
            chunk_embeddings = []
            for chunk in retrieved_chunks:
                emb = chunk.get("embedding")
                if not emb:
                    # Fallback if LlamaIndex stripped the embedding from the retrieved node
                    text = chunk.get("text", "")
                    if text:
                        try:
                            # Note: self.embedding_service uses Google Generative AI
                            emb = self.embedding_service.embed_query(text)
                        except Exception as e:
                            logger.error(f"Embedding computation failed: {e}")
                if emb:
                    chunk_embeddings.append(emb)
            
            # 2. COVERAGE SCORE: Aggregate Vector vs JD Vector
            # We mean-pool all retrieved chunk embeddings for this candidate
            if chunk_embeddings:
                aggregate_vector = np.mean(chunk_embeddings, axis=0).tolist()
                coverage_score = self._cosine_similarity(aggregate_vector, jd_embedding)
            else:
                coverage_score = 0.0

            # 3. DIVERSITY & DENSITY (For symmetrical 4x4 UI)
            sections = set()
            for chunk in retrieved_chunks:
                # Handle metadata from dictionary
                meta = chunk.get("metadata", {})
                sec = meta.get("section", "Other")
                sections.add(sec)
            
            # Diversity: How many unique resume sections are represented? (Target: 5+ sections)
            diversity_score = min(1.0, len(sections) / 5.0) 
            
            # Density: Average similarity across ALL retrieved chunks
            all_scores = [c.get("score", 0.0) for c in retrieved_chunks]
            density_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

            # 4. SET THRESHOLDS
            SIMILARITY_THRESHOLD = 0.65 
            COVERAGE_THRESHOLD = 0.60
            
            health_status = "HEALTHY"
            if avg_top_3_similarity < SIMILARITY_THRESHOLD or coverage_score < COVERAGE_THRESHOLD:
                health_status = "CRITICAL"

            overall_score = (avg_top_3_similarity * 0.4) + (coverage_score * 0.4) + (diversity_score * 0.1) + (density_score * 0.1)

            logger.info(f"[Retrieval Gate] {candidate_id} | Cov: {coverage_score:.4f}, Sim: {avg_top_3_similarity:.4f}, Div: {diversity_score:.4f} | Gate: {health_status}")

            return {
                "coverage": coverage_score,
                "similarity": avg_top_3_similarity,
                "diversity": diversity_score,
                "density": density_score,
                "overall_score": overall_score,
                "rag_health_status": health_status
            }
            
        except Exception as e:
            logger.error(f"[Retrieval Gate] Failed evaluating {candidate_id}: {e}")
            return self._empty_metrics()

    def _empty_metrics(self) -> Dict[str, Any]:
        return {
            "coverage": 0.0,
            "similarity": 0.0,
            "diversity": 0.0,
            "density": 0.0,
            "overall_score": 0.0,
            "rag_health_status": "CRITICAL"
        }
