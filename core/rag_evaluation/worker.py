"""
Enterprise RAG Evaluation Background Worker.
Decouples LLM-based RAG evaluation from the main FastAPI uvicorn process.
Prevents Windows event loop timeouts by enforcing WindowsSelectorEventLoopPolicy.
"""
import sys
import time
import json
import asyncio

# Critical enforcement for RAGAS concurrency on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Need to make sure backend is in path if script is run directly
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

# Enforce LangSmith RAGAS Project tracing for the entire worker
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "RAGAS"

from config.logging_config import get_logger
from app.db.database import SessionLocal
from app.db import repository
from core.rag_evaluation.ragas_evaluator import EnterpriseRAGASEvaluator
from core.rag_evaluation.llm_rag_judge import EnterpriseLLMRAGJudge
from core.llama_indexing.resume_rag import ResumeRAGEvidenceBuilder

logger = get_logger(__name__)

def process_deterministic_job(db, job):
    logger.info(f"[JOB PICKED] Processing Deterministic RAG evaluation job {job.id} for candidate {job.candidate_id}")
    
    # Update to RUNNING
    repository.update_rag_evaluation_job_status(db, job.id, "RUNNING")
    
    try:
        # Load necessary data
        active_jd = repository.get_active_jd(db)
        if not active_jd:
            raise ValueError("No active job description found.")
            
        candidate = repository.get_candidate(db, job.candidate_id)
        if not candidate:
            raise ValueError(f"Candidate {job.candidate_id} not found.")

        str_cand_id = candidate.email.split('@')[0].upper() if candidate.email else str(job.candidate_id)

        rag_builder = ResumeRAGEvidenceBuilder()
        evidence = rag_builder.build_evidence(str_cand_id, active_jd.jd_text)
        
        chunks = evidence.get("raw_chunks", [])
        resume_summary = candidate.name
        
        evaluator = EnterpriseRAGASEvaluator()
        result = evaluator.evaluate(
            candidate_id=str_cand_id,
            job_description=active_jd.jd_text,
            retrieved_chunks=chunks,
            generated_answer=resume_summary,
            jd_hash=active_jd.jd_hash
        )

        metrics_dict = {
            "precision": result.precision,
            "recall": result.recall,
            "faithfulness": result.faithfulness,
            "answer_relevancy": result.answer_relevancy,
            "overall_score": result.overall_score,
            "rag_health_status": result.rag_health_status.value if hasattr(result.rag_health_status, 'value') else result.rag_health_status,
            "gate_decision": result.gate_decision.value if hasattr(result.gate_decision, 'value') else result.gate_decision,
            "failure_reasons": result.failure_reasons,
            "gating_reason": result.gating_reason
        }
        
        repository.update_rag_evaluation_job_status(db, job.id, "COMPLETED", metrics_json=json.dumps(metrics_dict))
        logger.info(f"[DETERMINISTIC COMPLETED] Job {job.id} finished successfully.")

    except Exception as e:
        logger.error(f"[DETERMINISTIC FAILED] Job {job.id} failed: {str(e)}")
        repository.update_rag_evaluation_job_status(db, job.id, "FAILED", error_message=str(e))

def process_llm_job(db, job):
    logger.info(f"[JOB PICKED] Processing LLM RAG Audit job {job.id} for candidate {job.candidate_id}")
    
    # Update to RUNNING
    repository.update_llm_job_status(db, job.id, "RUNNING")
    
    try:
        active_jd = repository.get_active_jd(db)
        candidate = repository.get_candidate(db, job.candidate_id)
        if not candidate: raise ValueError("Candidate not found")
        
        str_cand_id = candidate.email.split('@')[0].upper() if candidate.email else str(job.candidate_id)
        
        # We need the LLM-generated screening result to audit the faithfulness/hallucination
        screening_res = repository.get_latest_screening_result(db, job.candidate_id)
        if not screening_res:
            raise ValueError("No unified screening result found to audit.")
            
        ai_evidence = json.loads(screening_res.ai_evidence_json) if screening_res.ai_evidence_json else []
        
        # 1. Rebuild Exact Resume Chunks String
        resume_chunks_str = ""
        resume_count = 0
        chunks = [] # Raw text chunks for RAGAS
        
        for item in ai_evidence:
            if item.get("source", "").startswith("Resume"):
                resume_count += 1
                r_id = f"R{resume_count}"
                resume_chunks_str += f"[RESUME_CHUNK_ID: {r_id}]\nSection: {item.get('section', 'Unknown').capitalize()}\nContent: {item.get('snippet', '')}\n\n"
                chunks.append(item.get('snippet', ''))
                
        if not resume_chunks_str:
            resume_chunks_str = "No high-relevance resume evidence retrieved (Similarity < 0.45)."

        # 2. Rebuild Exact GitHub Chunks String
        gh_chunks_str = ""
        gh_count = 0
        for item in ai_evidence:
            if item.get("source", "").startswith("GitHub"):
                gh_count += 1
                g_id = f"G{gh_count}"
                gh_chunks_str += f"[GITHUB_CHUNK_ID: {g_id}]\nRepo: {item.get('repo', 'Unknown')}\nContent: {item.get('snippet', '')}\n\n"
                chunks.append(item.get('snippet', ''))
                
        if not gh_chunks_str:
            gh_chunks_str = "No high-relevance GitHub code evidence retrieved (Similarity < 0.45)."
            
        full_context_str = resume_chunks_str + gh_chunks_str
        
        from core.utils.context_hasher import compute_context_hash
        judge_hash = compute_context_hash(full_context_str)
        logger.info(f"[TRACE] Judge context hash: {judge_hash}")

        # If no GitHub chunks, we MUST explicitly inject the empty metric template as a context chunk
        # so RAGAS judge doesn't penalize the LLM for referencing 0/100 Github metrics.
        if gh_count == 0:
            chunks.append(
                "VERIFIED GITHUB EVIDENCE\n"
                "-------------------------\n"
                "GitHub Metrics:\n"
                "- Activity Score: 0/100\n"
                "- AI Relevance Score: 0/100\n"
                "- Total Repositories: 0\n\n"
                "Retrieved Code Evidence Chunks (cite as [G-ID]):\n\n"
                "No high-relevance GitHub code evidence retrieved (Similarity < 0.45)."
            )

        justification_list = json.loads(screening_res.justification_json) if screening_res.justification_json else []
        justification = ". ".join(justification_list)
        
        logger.info(f"[LLM AUDIT] Injected {resume_count} Resume chunks and {gh_count} GitHub chunks into judge context.")
        
        judge = EnterpriseLLMRAGJudge()
        metrics = judge.evaluate(
            question=active_jd.jd_text,
            retrieved_chunks=chunks,
            answer=justification
        )
        
        # Save results
        repository.save_rag_llm_metrics(db, job.candidate_id, metrics)
        repository.update_llm_job_status(db, job.id, "COMPLETED", metrics_json=json.dumps(metrics))
        logger.info(f"[LLM AUDIT COMPLETED] Job {job.id} finished successfully.")

    except Exception as e:
        logger.error(f"[LLM AUDIT FAILED] Job {job.id} failed: {str(e)}")
        repository.update_llm_job_status(db, job.id, "FAILED", error_message=str(e))

def run_worker():
    logger.info("[RAG WORKER STARTED] Waiting for jobs...")
    while True:
        db = SessionLocal()
        try:
            # 1. Check for Deterministic Jobs
            det_jobs = repository.get_pending_rag_evaluation_jobs(db, limit=1)
            if det_jobs:
                process_deterministic_job(db, det_jobs[0])
                continue

            # 2. Check for LLM Audit Jobs
            llm_job = repository.get_pending_llm_job(db)
            if llm_job:
                process_llm_job(db, llm_job)
                continue
                
            time.sleep(5)
        except Exception as e:
            logger.error(f"[WORKER ERROR] {e}")
            time.sleep(5)
        finally:
            db.close()

if __name__ == "__main__":
    run_worker()
