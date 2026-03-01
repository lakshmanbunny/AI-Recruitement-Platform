"""
Enterprise RAG Evaluation - Pydantic Models
Type-safe metric result contracts for the RAGAS evaluation pipeline.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class RAGHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"   # overall_score >= 0.80
    WARNING = "WARNING"   # 0.60 <= overall_score < 0.80
    CRITICAL = "CRITICAL" # overall_score < 0.60


class RAGGateDecision(str, Enum):
    ALLOW = "ALLOW"   # HEALTHY → full LLM evaluation
    WARN = "WARN"     # WARNING → evaluate but log warning
    BLOCK = "BLOCK"   # CRITICAL → block LLM evaluation


class RAGMetricsResult(BaseModel):
    """Structured output from the RAGAS evaluation engine."""
    candidate_id: str
    jd_hash: Optional[str] = None

    # RAGAS Core Metrics (0.0 – 1.0)
    precision: float = Field(0.0, description="Context precision: relevance of retrieved chunks")
    recall: float = Field(0.0, description="Context recall: coverage of relevant information")
    faithfulness: float = Field(0.0, description="Faithfulness: hallucination prevention score")
    answer_relevancy: float = Field(0.0, description="Answer relevancy: alignment to context")

    # Computed
    overall_score: float = Field(0.0, description="Weighted average of all metrics")
    rag_health_status: RAGHealthStatus = RAGHealthStatus.CRITICAL
    gate_decision: RAGGateDecision = RAGGateDecision.BLOCK

    # Failure diagnostics
    failure_reasons: List[str] = Field(default_factory=list)
    gating_reason: Optional[str] = None
    override_triggered: bool = False
    override_reason: Optional[str] = None

    # Thresholds used (for transparency)
    threshold_precision: float = 0.65
    threshold_recall: float = 0.60
    threshold_faithfulness: float = 0.80
    threshold_relevancy: float = 0.70

    class Config:
        use_enum_values = True


class RAGGateSummary(BaseModel):
    """System-wide summary of RAG health across all candidates in a run."""
    total_candidates: int = 0
    healthy_count: int = 0
    warning_count: int = 0
    critical_count: int = 0
    blocked_count: int = 0
    overridden_count: int = 0
    average_overall_score: float = 0.0
    average_precision: float = 0.0
    average_recall: float = 0.0
    average_faithfulness: float = 0.0
    average_relevancy: float = 0.0
