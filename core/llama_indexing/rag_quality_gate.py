from typing import Dict, List, Any
from config.logging_config import get_logger

logger = get_logger(__name__)

class RAGQualityGate:
    """
    Enterprise Quality Gate for RAG-based systems.
    Ensures that LLM evaluations only occur when retrieval quality is sufficient.
    """
    
    def __init__(
        self, 
        min_resume_chunks: int = 2,
        min_github_chunks: int = 2,
        min_similarity_score: float = 0.6
    ):
        self.min_resume_chunks = min_resume_chunks
        self.min_github_chunks = min_github_chunks
        self.min_similarity_score = min_similarity_score

    def evaluate_quality(
        self, 
        candidate_id: str,
        resume_rag_evidence: Dict[str, Any],
        github_evidence: List[Dict[str, Any]],
        force_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluates retrieval metrics against defined enterprise thresholds.
        """
        if force_mode:
            logger.info(f"[RAG QUALITY GATE] Force mode active for {candidate_id}. Bypassing checks.")
            return {
                "status": "READY",
                "score": 1.0,
                "reason": "Manual override (Force Mode)",
                "metrics": {
                    "resume_chunk_count": len(resume_rag_evidence.get("raw_chunks", [])),
                    "github_chunk_count": len(github_evidence),
                    "avg_similarity": 1.0
                }
            }

        resume_chunks = resume_rag_evidence.get("raw_chunks", [])
        resume_count = len(resume_chunks)
        github_count = len(github_evidence)
        
        # Calculate average similarity score for resume chunks
        avg_sim = 0.0
        if resume_chunks:
            avg_sim = sum(float(c.get("score", 0)) for c in resume_chunks) / resume_count
            
        metrics = {
            "resume_chunk_count": resume_count,
            "github_chunk_count": github_count,
            "avg_similarity": round(avg_sim, 4)
        }

        # Threshold Validation
        reasons = []
        if resume_count < self.min_resume_chunks:
            reasons.append(f"Insufficient resume evidence ({resume_count} < {self.min_resume_chunks})")
        if github_count < self.min_github_chunks:
            reasons.append(f"Insufficient GitHub evidence ({github_count} < {self.min_github_chunks})")
        if avg_sim < self.min_similarity_score:
            reasons.append(f"Low retrieval precision ({avg_sim:.2f} < {self.min_similarity_score})")

        if not reasons:
            logger.info(f"[RAG QUALITY READY] Candidate {candidate_id} passed quality gate. Metrics: {metrics}")
            return {
                "status": "READY",
                "score": avg_sim,
                "metrics": metrics
            }
        else:
            logger.warning(f"[RAG QUALITY LOW] LLM evaluation blocked for {candidate_id}. Reasons: {reasons}")
            return {
                "status": "RAG_NOT_READY",
                "score": avg_sim,
                "reason": "; ".join(reasons),
                "metrics": metrics
            }
