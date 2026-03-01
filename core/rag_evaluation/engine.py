from typing import Dict, List, Any
import numpy as np
from core.similarity import cosine_similarity
from core.embedding_service import EmbeddingService
from config.logging_config import get_logger

logger = get_logger(__name__)

class RAGEvaluationEngine:
    """
    Enterprise RAG Evaluation Engine.
    Computes RAGAS-inspired metrics without additional LLM calls
    by utilizing embeddings and retrieval metadata.
    """
    
    def __init__(self):
        self.embedding_service = EmbeddingService()

    def compute_all_metrics(
        self, 
        job_description: str, 
        retrieved_evidence: Dict[str, Any],
        candidate_summary: str = ""
    ) -> Dict[str, Any]:
        """
        Computes all RAG metrics for a candidate.
        """
        logger.info(f"[RAG EVAL START] Evaluating candidate {retrieved_evidence.get('candidate_id')}")
        
        jd_vector = self.embedding_service.generate_embedding(job_description)
        raw_chunks = retrieved_evidence.get("raw_chunks", [])
        
        if not raw_chunks:
            return self._empty_metrics("CRITICAL", "No chunks retrieved")

        # 1. Retrieval Quality Score
        retrieval_score = self.compute_retrieval_score(jd_vector, raw_chunks)
        
        # 2. Precision Score
        precision_score = self.compute_precision_score(raw_chunks)
        
        # 3. Coverage Score
        coverage_score = self.compute_coverage_score(job_description, raw_chunks)
        
        # 4. Faithfulness Score (Proxy: Context vs Personal Profile)
        faithfulness_score = self.compute_faithfulness_score(raw_chunks, candidate_summary)
        
        # Combined Health Score
        avg_score = (retrieval_score + precision_score + coverage_score + faithfulness_score) / 4
        health_status = self.classify_health(avg_score)
        
        logger.info(f"[RAG METRICS COMPUTED] Health: {health_status} | Avg Score: {avg_score:.2f}")
        
        return {
            "retrieval_score": round(retrieval_score, 4),
            "precision_score": round(precision_score, 4),
            "coverage_score": round(coverage_score, 4),
            "faithfulness_score": round(faithfulness_score, 4),
            "rag_health_status": health_status,
            "overall_rag_score": round(avg_score, 4)
        }

    def compute_retrieval_score(self, jd_vector: List[float], chunks: List[Dict[str, Any]]) -> float:
        """Average similarity to JD."""
        scores = [float(c.get("score", 0)) for c in chunks]
        return sum(scores) / len(scores) if scores else 0.0

    def compute_precision_score(self, chunks: List[Dict[str, Any]], threshold: float = 0.6) -> float:
        """Ratio of relevant chunks vs total."""
        relevant = [c for c in chunks if float(c.get("score", 0)) >= threshold]
        return len(relevant) / len(chunks) if chunks else 0.0

    def compute_coverage_score(self, jd: str, chunks: List[Dict[str, Any]]) -> float:
        """Word overlap or keyword discovery proxy."""
        # Simple keyword overlap proxy on cleaned text
        jd_words = set(jd.lower().split())
        chunk_text = " ".join([c.get("text", "").lower() for c in chunks])
        chunk_words = set(chunk_text.split())
        
        intersection = jd_words.intersection(chunk_words)
        # Small normalization factor to avoid JD length bias
        return min(len(intersection) / 100, 1.0) 

    def compute_faithfulness_score(self, chunks: List[Dict[str, Any]], candidate_summary: str) -> float:
        """Ensures retrieved chunks are consistent with the overall candidate profile."""
        if not candidate_summary: return 0.7 # Default baseline if no summary
        
        profile_vector = self.embedding_service.generate_embedding(candidate_summary)
        chunk_similarities = []
        
        for chunk in chunks:
            chunk_vector = self.embedding_service.generate_embedding(chunk["text"])
            sim = cosine_similarity(profile_vector, chunk_vector)
            chunk_similarities.append(sim)
            
        return sum(chunk_similarities) / len(chunk_similarities) if chunk_similarities else 0.0

    def classify_health(self, score: float) -> str:
        if score >= 0.75: return "HEALTHY"
        if score >= 0.5: return "DEGRADED"
        return "CRITICAL"

    def _empty_metrics(self, status: str, reason: str) -> Dict[str, Any]:
        return {
            "retrieval_score": 0.0,
            "precision_score": 0.0,
            "coverage_score": 0.0,
            "faithfulness_score": 0.0,
            "rag_health_status": status,
            "overall_rag_score": 0.0,
            "gating_reason": reason
        }
