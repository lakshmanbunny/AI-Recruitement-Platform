import sys
import time
import json
import asyncio
import os
import logging

# Critical enforcement for async on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Navigate to the 'exp' root directory relative to this file
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
backend_dir = os.path.join(project_root, "backend")

sys.path.append(project_root)
sys.path.append(backend_dir)

# Configure logging locally
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("RAG_LLM_WORKER")

from backend.app.db.database import SessionLocal
from backend.app.db import repository
from core.rag_evaluation.llm_rag_judge import EnterpriseLLMRAGJudge
from core.llama_indexing.resume_rag import ResumeRAGEvidenceBuilder
from core.github_vector_store import GitHubVectorStore

def process_job(db, job):
    str_cand_id = "UNKNOWN"
    try:
        candidate = repository.get_candidate(db, job.candidate_id)
        if not candidate:
            raise ValueError(f"Candidate {job.candidate_id} not found.")

        str_cand_id = candidate.email.split('@')[0].upper() if candidate.email else str(job.candidate_id)
        logger.info(f"[POST-LLM EVAL] Picked job {job.id} for {str_cand_id}")

        # Update to RUNNING
        repository.update_llm_job_status(db, job.id, "RUNNING")
        
        # 1. Fetch JD
        active_jd = repository.get_active_jd(db)
        if not active_jd:
            raise ValueError("No active job description found.")
        
        # 2. Extract Chunks (Resume + GitHub)
        rag_builder = ResumeRAGEvidenceBuilder()
        resume_evidence = rag_builder.build_evidence(str_cand_id, active_jd.jd_text)
        resume_chunks = [c.get("text", "") for c in resume_evidence.get("raw_chunks", []) if c.get("text")]
        
        gh_store = GitHubVectorStore()
        gh_chunks_raw = gh_store.search(active_jd.jd_text, candidate_id=str_cand_id, top_k=5)
        gh_chunks = [c.get("chunk_text", "") for c in gh_chunks_raw if c.get("chunk_text")]
        
        all_chunks = resume_chunks + gh_chunks
        
        if not all_chunks:
            logger.warning(f"[POST-LLM EVAL] No chunks found for {str_cand_id}")
            all_chunks = ["No context retrieved."]
            
        # 3. Get Final Answer
        screening = repository.get_screening_result(db, job.candidate_id, active_jd.id)
        if not screening:
            raise ValueError(f"No screening result found for {str_cand_id}.")
            
        answer_text = ""
        try:
            decision_data = json.loads(screening.final_synthesized_decision_json)
            answer_text += f"{decision_data.get('final_decision', '')}\n"
            justification = json.loads(screening.justification_json)
            if isinstance(justification, list):
                answer_text += "\n".join(justification)
        except Exception:
            answer_text = screening.recommendation or "No answer found."
            
        if not answer_text.strip():
            answer_text = "No generated answer."

        # 4. Evaluate
        logger.info(f"[POST-LLM EVAL] Judging 4 metrics for {str_cand_id}")
        judge = EnterpriseLLMRAGJudge()
        metrics = judge.evaluate(
            question=active_jd.jd_text,
            retrieved_chunks=all_chunks,
            answer=answer_text
        )
        
        # 5. Store & Complete
        repository.save_rag_llm_metrics(db, job.candidate_id, metrics)
        repository.update_llm_job_status(db, job.id, "COMPLETED", metrics_json=json.dumps(metrics))
        logger.info(f"[POST-LLM EVAL] Job {job.id} for {str_cand_id} COMPLETED. Score: {metrics.get('overall_score')}")

    except Exception as e:
        logger.error(f"[POST-LLM EVAL] Job {job.id} for {str_cand_id} FAILED: {str(e)}")
        repository.update_llm_job_status(db, job.id, "FAILED", error_message=str(e))

def run_worker():
    logger.info("[POST-LLM WORKER] Started. Polling for rag_llm_eval_jobs...")
    while True:
        try:
            db = SessionLocal()
            job = repository.get_pending_llm_job(db)
            
            if job:
                process_job(db, job)
            else:
                time.sleep(5)
                
        except Exception as e:
            logger.error(f"[POST-LLM WORKER ERROR] Unexpected failure in worker loop: {e}")
            time.sleep(5)
        finally:
            if 'db' in locals():
                db.close()

if __name__ == "__main__":
    run_worker()
