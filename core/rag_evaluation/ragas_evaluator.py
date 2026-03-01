"""
Enterprise RAGAS Evaluator
Uses the official RAGAS library to compute retrieval quality metrics.
Wraps RAGAS EvaluationDataset for context_precision, context_recall,
faithfulness, and answer_relevancy.
"""
from typing import Dict, List, Any, Optional
from config.logging_config import get_logger
from core.rag_evaluation.rag_metrics_models import (
    RAGMetricsResult, RAGHealthStatus, RAGGateDecision
)

logger = get_logger(__name__)

# Enterprise gating thresholds
THRESHOLDS = {
    "precision": 0.65,
    "recall": 0.60,
    "faithfulness": 0.80,
    "answer_relevancy": 0.70,
}


class EnterpriseRAGASEvaluator:
    """
    Enterprise RAG evaluation using the RAGAS framework.
    Computes context_precision, context_recall, faithfulness, answer_relevancy.
    Falls back to embedding-based scoring if RAGAS is unavailable.
    """

    def __init__(self):
        self._ragas_available = self._check_ragas()

    def _check_ragas(self) -> bool:
        try:
            import ragas  # noqa: F401
            return True
        except ImportError:
            logger.warning("[RAGAS] Library not available. Embedding-based fallback will be used.")
            return False

    def evaluate(
        self,
        candidate_id: str,
        job_description: str,
        retrieved_chunks: List[Dict[str, Any]],
        generated_answer: Optional[str] = None,
        jd_hash: Optional[str] = None,
    ) -> RAGMetricsResult:
        """
        Main evaluation entry point.
        Runs RAGAS evaluation if available, else falls back to embedding-based.
        """
        logger.info(f"[RAGAS EVALUATION STARTED] Candidate: {candidate_id}")

        if self._ragas_available:
            try:
                return self._run_ragas_evaluation(
                    candidate_id, job_description, retrieved_chunks, generated_answer, jd_hash
                )
            except Exception as e:
                logger.warning(f"[RAGAS] Evaluation failed for {candidate_id}: {e}. Falling back.")

        return self._run_embedding_fallback(candidate_id, job_description, retrieved_chunks, jd_hash)

    def _run_ragas_evaluation(
        self,
        candidate_id: str,
        job_description: str,
        retrieved_chunks: List[Dict[str, Any]],
        generated_answer: Optional[str],
        jd_hash: Optional[str],
    ) -> RAGMetricsResult:
        """
        Run full RAGAS evaluation using the ragas library.
        Executes natively without ThreadPoolExecutor (relies on isolated worker process).
        """
        from ragas import evaluate, EvaluationDataset
        from ragas.metrics import (
            context_precision,
            context_recall,
            faithfulness,
            answer_relevancy,
        )
        from ragas.llms import LangchainLLMWrapper
        from ragas.run_config import RunConfig
        from langchain_google_genai import ChatGoogleGenerativeAI
        from core.settings import settings as core_settings
        from core.rag_evaluation.google_embedding_adapter import GoogleGenerativeAIEmbeddingsAdapter

        # Prepare contexts from retrieved chunks
        contexts = [c.get("text", "") for c in retrieved_chunks if c.get("text")]
        if not contexts:
            logger.warning(f"[RAGAS] No valid contexts for {candidate_id}. Using empty metrics.")
            return self._empty_result(candidate_id, jd_hash, "No contexts available")

        # Use chunk summary as generated answer proxy if not provided
        answer = generated_answer or f"Candidate {candidate_id} profile: " + " | ".join(contexts[:2])[:400]

        # Build dataset for RAGAS
        sample = {
            "user_input": job_description,
            "retrieved_contexts": contexts,
            "response": answer,
            "reference": job_description,
        }

        try:
            dataset = EvaluationDataset.from_list([sample])
        except Exception as e:
            logger.error(f"[RAGAS] Dataset construction failed: {e}")
            return self._run_embedding_fallback(candidate_id, job_description, retrieved_chunks, jd_hash)

        # Configure RAGAS to use Gemini with custom robust embedding adapter
        try:
            llm = LangchainLLMWrapper(
                ChatGoogleGenerativeAI(
                    model="gemini-2.5-pro",
                    google_api_key=core_settings.GOOGLE_API_KEY,
                    temperature=0.0,
                    request_timeout=25,
                )
            )
            emb = GoogleGenerativeAIEmbeddingsAdapter()
        except Exception as e:
            logger.warning(f"[RAGAS] LLM/Embedding setup failed: {e}. Falling back.")
            return self._run_embedding_fallback(candidate_id, job_description, retrieved_chunks, jd_hash)

        metrics_to_run = [context_precision, context_recall, faithfulness, answer_relevancy]
        for m in metrics_to_run:
            m.llm = llm
            if hasattr(m, "embeddings"):
                m.embeddings = emb

        # Disable concurrency (max_workers=1) to prevent Windows event loop drops
        run_cfg = RunConfig(timeout=30, max_retries=1, max_wait=30, max_workers=1)

        try:
            logger.info(f"[RAGAS] Running single-threaded evaluation for {candidate_id}")
            import os
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            
            from langchain_core.tracers.context import tracing_v2_enabled
            
            with tracing_v2_enabled(project_name="RAGAS"):
                result = evaluate(dataset=dataset, metrics=metrics_to_run, run_config=run_cfg)

            result_df = result.to_pandas()
            if result_df.empty:
                raise ValueError("RAGAS returned empty dataframe")
            row = result_df.iloc[0]

            precision = float(row.get("context_precision", 0.0) or 0.0)
            recall = float(row.get("context_recall", 0.0) or 0.0)
            faith = float(row.get("faithfulness", 0.0) or 0.0)
            relevancy = float(row.get("answer_relevancy", 0.0) or 0.0)

            logger.info(f"[RAGAS] Evaluation succeeded for {candidate_id}: "
                        f"P={precision:.2f} R={recall:.2f} F={faith:.2f} Rel={relevancy:.2f}")

        except Exception as e:
            logger.error(f"[RAGAS] evaluate() failed for {candidate_id}: {e}")
            return self._run_embedding_fallback(candidate_id, job_description, retrieved_chunks, jd_hash)

        return self._build_result(candidate_id, jd_hash, precision, recall, faith, relevancy)

    def _run_embedding_fallback(
        self,
        candidate_id: str,
        job_description: str,
        retrieved_chunks: List[Dict[str, Any]],
        jd_hash: Optional[str],
    ) -> RAGMetricsResult:
        """
        Embedding-based fallback evaluation (no LLM calls needed).
        Maps existing engine metrics to RAGAS metric names for compatibility.
        """
        from core.rag_evaluation.engine import RAGEvaluationEngine
        from core.embedding_service import EmbeddingService

        logger.info(f"[RAGAS FALLBACK] Using embedding-based evaluation for {candidate_id}")
        engine = RAGEvaluationEngine()
        emb_service = EmbeddingService()

        jd_vector = emb_service.generate_embedding(job_description)
        chunks = retrieved_chunks if retrieved_chunks else []

        # Map existing engine metrics to RAGAS names  
        precision = engine.compute_precision_score(chunks)
        # Recall: proportion of JD keywords covered (normalized)
        recall = engine.compute_coverage_score(job_description, chunks)
        # Faithfulness: chunk-to-chunk consistency (using retrieval score as proxy)  
        faithfulness = engine.compute_retrieval_score(jd_vector, chunks)
        # Answer relevancy: average retrieval score
        relevancy = faithfulness

        return self._build_result(candidate_id, jd_hash, precision, recall, faithfulness, relevancy)

    def _build_result(
        self,
        candidate_id: str,
        jd_hash: Optional[str],
        precision: float,
        recall: float,
        faithfulness: float,
        answer_relevancy: float,
    ) -> RAGMetricsResult:
        """Builds a complete RAGMetricsResult from raw metric values."""
        import math
        # Guard against NaN values from failed RAGAS jobs
        precision = 0.0 if (math.isnan(precision) or precision is None) else float(precision)
        recall = 0.0 if (math.isnan(recall) or recall is None) else float(recall)
        faithfulness = 0.0 if (math.isnan(faithfulness) or faithfulness is None) else float(faithfulness)
        answer_relevancy = 0.0 if (math.isnan(answer_relevancy) or answer_relevancy is None) else float(answer_relevancy)
        overall = (precision + recall + faithfulness + answer_relevancy) / 4

        if overall >= 0.80:
            health = RAGHealthStatus.HEALTHY
            gate = RAGGateDecision.ALLOW
        elif overall >= 0.60:
            health = RAGHealthStatus.WARNING
            gate = RAGGateDecision.WARN
        else:
            health = RAGHealthStatus.CRITICAL
            gate = RAGGateDecision.BLOCK

        # Identify which thresholds failed
        failure_reasons = []
        if precision < THRESHOLDS["precision"]:
            failure_reasons.append(f"Precision {precision:.2f} below threshold {THRESHOLDS['precision']}")
        if recall < THRESHOLDS["recall"]:
            failure_reasons.append(f"Recall {recall:.2f} below threshold {THRESHOLDS['recall']}")
        if faithfulness < THRESHOLDS["faithfulness"]:
            failure_reasons.append(f"Faithfulness {faithfulness:.2f} below threshold {THRESHOLDS['faithfulness']}")
        if answer_relevancy < THRESHOLDS["answer_relevancy"]:
            failure_reasons.append(f"Answer Relevancy {answer_relevancy:.2f} below threshold {THRESHOLDS['answer_relevancy']}")

        gating_reason = None
        if gate == RAGGateDecision.BLOCK:
            gating_reason = "Evaluation blocked: " + "; ".join(failure_reasons) if failure_reasons else "Overall score below critical threshold."
        elif gate == RAGGateDecision.WARN:
            gating_reason = "Warning: LLM evaluation allowed but retrieval quality is suboptimal."

        logger.info(
            f"[RAGAS METRICS COMPUTED] {candidate_id} | "
            f"Precision={precision:.2f} Recall={recall:.2f} "
            f"Faithfulness={faithfulness:.2f} Relevancy={answer_relevancy:.2f} "
            f"Overall={overall:.2f} | Health={health.value} | Gate={gate.value}"
        )
        logger.info(f"[RAG HEALTH STATUS] {candidate_id}: {health.value}")
        if gate == RAGGateDecision.BLOCK:
            logger.warning(f"[RAG GATE BLOCKED] {candidate_id}: {gating_reason}")

        return RAGMetricsResult(
            candidate_id=candidate_id,
            jd_hash=jd_hash,
            precision=round(precision, 4),
            recall=round(recall, 4),
            faithfulness=round(faithfulness, 4),
            answer_relevancy=round(answer_relevancy, 4),
            overall_score=round(overall, 4),
            rag_health_status=health,
            gate_decision=gate,
            failure_reasons=failure_reasons,
            gating_reason=gating_reason,
            threshold_precision=THRESHOLDS["precision"],
            threshold_recall=THRESHOLDS["recall"],
            threshold_faithfulness=THRESHOLDS["faithfulness"],
            threshold_relevancy=THRESHOLDS["answer_relevancy"],
        )

    def _empty_result(self, candidate_id: str, jd_hash: Optional[str], reason: str) -> RAGMetricsResult:
        logger.warning(f"[RAGAS] Empty result for {candidate_id}: {reason}")
        return RAGMetricsResult(
            candidate_id=candidate_id,
            jd_hash=jd_hash,
            rag_health_status=RAGHealthStatus.CRITICAL,
            gate_decision=RAGGateDecision.BLOCK,
            gating_reason=reason,
            failure_reasons=[reason],
        )
