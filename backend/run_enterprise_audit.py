import sys
import os
import asyncio
import logging
from sqlalchemy.orm import Session

# Setup paths
backend_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, "../"))
if backend_dir not in sys.path: sys.path.insert(0, backend_dir)
if project_root not in sys.path: sys.path.insert(0, project_root)

from app.db.database import SessionLocal
from app.db import models, repository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("enterprise_audit")

async def trigger_enterprise_audit():
    """
    Identifies all candidates who have been screened (Stage 1 completed)
    and triggers a Post-LLM RAG Audit job for them.
    """
    db = SessionLocal()
    try:
        # 1. Get all candidates who have a ScreeningResult
        screened_candidates = db.query(models.Candidate).join(
            models.ScreeningResult, models.Candidate.id == models.ScreeningResult.candidate_id
        ).all()
        
        if not screened_candidates:
            logger.warning("No screened candidates found. Run Stage 1 (Screening) first.")
            return

        logger.info(f"Found {len(screened_candidates)} candidates ready for enterprise audit.")
        
        jobs_created = 0
        for cand in screened_candidates:
            # Check if an LLM Audit job already exists and is completed
            existing_metrics = repository.get_rag_llm_metrics(db, cand.id)
            if existing_metrics:
                logger.info(f"[SKIP] {cand.name} ({cand.email}) already has LLM-based RAG metrics.")
                continue
                
            # Create a new job in the queue
            repository.create_llm_eval_job(db, cand.id)
            logger.info(f"[QUEUED] Created LLM Audit job for {cand.name} ({cand.email})")
            jobs_created += 1
            
        if jobs_created > 0:
            logger.info(f"Successfully queued {jobs_created} enterprise audit jobs.")
            logger.info("Please ensure the RAG worker is running: `python -m core.rag_evaluation.worker`")
        else:
            logger.info("All candidates already have up-to-date audits.")
            
    except Exception as e:
        logger.error(f"Audit trigger failed: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(trigger_enterprise_audit())
