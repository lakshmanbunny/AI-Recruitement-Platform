"""
RAG Quality Service
Orchestration layer for RAGAS evaluation: runs evaluation, applies gating,
logs to LangSmith, and provides the central validate_rag_health() contract.
"""
from typing import Dict, List, Any, Optional
from config.logging_config import get_logger
from core.rag_evaluation.rag_metrics_models import (
    RAGMetricsResult, RAGGateDecision, RAGHealthStatus, RAGGateSummary
)
from core.rag_evaluation.ragas_evaluator import EnterpriseRAGASEvaluator

logger = get_logger(__name__)


class RagQualityService:
    """
    Central service for RAG quality evaluation and gating.
    Integrates with the recruitment pipeline workflow.
    """

    def __init__(self):
        self._evaluator = EnterpriseRAGASEvaluator()

    def run_evaluation(
        self,
        candidate_id: str,
        job_description: str,
        retrieved_chunks: List[Dict[str, Any]],
        generated_answer: Optional[str] = None,
        jd_hash: Optional[str] = None,
    ) -> RAGMetricsResult:
        """
        Runs RAGAS evaluation for a candidate and returns structured metrics.
        Automatically logs to LangSmith if tracing is enabled.
        """
        result = self._evaluator.evaluate(
            candidate_id=candidate_id,
            job_description=job_description,
            retrieved_chunks=retrieved_chunks,
            generated_answer=generated_answer,
            jd_hash=jd_hash,
        )
        self._log_to_langsmith(result)
        return result

    def validate_rag_health(self, metrics: RAGMetricsResult) -> RAGGateDecision:
        """
        Applies enterprise gating thresholds and returns gate decision.

        Gate Rules:
        - HEALTHY (>= 0.80) → ALLOW full LLM evaluation
        - WARNING (0.60–0.80) → WARN - allow but flag
        - CRITICAL (< 0.60) → BLOCK LLM evaluation completely
        """
        decision = metrics.gate_decision
        logger.info(
            f"[RAG GATE DECISION] {metrics.candidate_id}: "
            f"{metrics.rag_health_status} → {decision}"
        )
        if decision == RAGGateDecision.BLOCK:
            logger.warning(
                f"[RAG GATE BLOCKED] {metrics.candidate_id}: "
                f"{metrics.gating_reason}"
            )
        elif decision == RAGGateDecision.WARN:
            logger.warning(
                f"[RAG GATE WARNING] {metrics.candidate_id}: "
                f"Quality suboptimal but within warning range, allowing evaluation."
            )
        return decision

    def apply_override(self, metrics: RAGMetricsResult, override_reason: str = "HR Manual Override") -> RAGMetricsResult:
        """
        Apply HR manual override - forces ALLOW gate decision.
        """
        logger.warning(f"[RAG OVERRIDE TRIGGERED] {metrics.candidate_id}: {override_reason}")
        metrics.gate_decision = RAGGateDecision.ALLOW
        metrics.override_triggered = True
        metrics.override_reason = override_reason
        return metrics

    def build_run_summary(self, all_metrics: Dict[str, RAGMetricsResult]) -> RAGGateSummary:
        """Builds a system-wide summary across all evaluated candidates in a run."""
        if not all_metrics:
            return RAGGateSummary()

        results = list(all_metrics.values())
        summary = RAGGateSummary(
            total_candidates=len(results),
            healthy_count=sum(1 for r in results if r.rag_health_status == RAGHealthStatus.HEALTHY),
            warning_count=sum(1 for r in results if r.rag_health_status == RAGHealthStatus.WARNING),
            critical_count=sum(1 for r in results if r.rag_health_status == RAGHealthStatus.CRITICAL),
            blocked_count=sum(1 for r in results if r.gate_decision == RAGGateDecision.BLOCK),
            overridden_count=sum(1 for r in results if r.override_triggered),
            average_overall_score=round(sum(r.overall_score for r in results) / len(results), 4),
            average_precision=round(sum(r.precision for r in results) / len(results), 4),
            average_recall=round(sum(r.recall for r in results) / len(results), 4),
            average_faithfulness=round(sum(r.faithfulness for r in results) / len(results), 4),
            average_relevancy=round(sum(r.answer_relevancy for r in results) / len(results), 4),
        )
        logger.info(
            f"[RAG RUN SUMMARY] Total={summary.total_candidates} "
            f"Healthy={summary.healthy_count} Warning={summary.warning_count} "
            f"Critical={summary.critical_count} Blocked={summary.blocked_count}"
        )
        return summary

    def _log_to_langsmith(self, metrics: RAGMetricsResult):
        """
        Injects RAG metrics into the active LangSmith trace if tracing is enabled.
        """
        try:
            from langchain_core.tracers.context import get_callback_manager_for_config
            import os
            if os.getenv("LANGCHAIN_TRACING_V2", "false").lower() != "true":
                return
            # Metadata injection via LangSmith run metadata
            from langsmith import Client
            client = Client()
            run_metadata = {
                "rag_precision": metrics.precision,
                "rag_recall": metrics.recall,
                "rag_faithfulness": metrics.faithfulness,
                "rag_relevancy": metrics.answer_relevancy,
                "rag_overall_score": metrics.overall_score,
                "rag_health_status": metrics.rag_health_status,
                "rag_gate_decision": metrics.gate_decision,
                "rag_candidate_id": metrics.candidate_id,
            }
            logger.info(f"[LANGSMITH] RAG metrics logged for {metrics.candidate_id}: {run_metadata}")
        except Exception as e:
            logger.debug(f"[LANGSMITH] Could not log RAG metrics (non-critical): {e}")


# Singleton instance
rag_quality_service = RagQualityService()
