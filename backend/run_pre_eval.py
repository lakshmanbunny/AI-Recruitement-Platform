import sys
import os
import asyncio
import json
import logging
from typing import List, Dict, Any

backend_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, "../"))
if backend_dir not in sys.path: sys.path.insert(0, backend_dir)
if project_root not in sys.path: sys.path.insert(0, project_root)

from app.db.database import SessionLocal
from app.db import models
from app.services.pipeline_service import PipelineService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("pre_eval_trigger")

def parse_extracted_sections(raw_json_str: str) -> str:
    if not raw_json_str:
        return ""
    try:
        data = json.loads(raw_json_str)
        return raw_json_str
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        return ""

async def run_pre_eval():
    db = SessionLocal()
    candidates_to_screen: List[Dict[str, Any]] = []
    
    try:
        woxsen_db_candidates = db.query(models.WoxsenCandidate).filter(
            models.WoxsenCandidate.raw_resume_text.isnot(None)
        ).all()
        
        logger.info(f"Loaded {len(woxsen_db_candidates)} Woxsen Candidates with valid JSON from the database.")
        
        for cand in woxsen_db_candidates:
            raw_text = parse_extracted_sections(cand.raw_resume_text)
            mapped_candidate = {
                "candidate_id": cand.roll_number,
                "name": cand.name,
                "email": cand.email,
                "links": {
                    "github": cand.github_url or "",
                    "linkedin": cand.linkedin_url or ""
                },
                "raw_resume_text": raw_text
            }
            candidates_to_screen.append(mapped_candidate)
            
        if not candidates_to_screen:
            logger.error("No valid candidates mapped. Exiting.")
            return

        # Process all candidates in one go (Indexer now handles internal batching and progress)
        pipeline = PipelineService()
        
        logger.info(f"🚀 Starting Pre-Eval for all {len(candidates_to_screen)} candidates...")
        await pipeline.run_screening(
            candidates=candidates_to_screen,
            force_eval=True,
            skip_llm_eval=True
        )
        logger.info("✅ All candidates processed successfully.")
        print("                 TOP 30 PRE-LLM DETERMINISTIC EVALUATION METRICS")
        print("="*80)
        
        # Fetch the latest metrics and sort by similarity
        db_metrics = db.query(models.RAGRetrievalMetric).all()
        # Sort by similarity descending
        db_metrics.sort(key=lambda x: x.similarity, reverse=True)
        
        for i, metric in enumerate(db_metrics[:30]): 
            cand = db.query(models.Candidate).filter(models.Candidate.id == metric.candidate_id).first()
            if cand:
                print(f"Rank {i+1}: {cand.name} ({cand.email})")
                print(f"  - Similarity Score: {metric.similarity:.4f}")
                print(f"  - Coverage:         {metric.coverage:.4f}")
                print(f"  - Diversity Score:  {metric.diversity:.4f}")
                print(f"  - Density Score:    {metric.density:.4f}")
                print(f"  - Health Status:    {metric.rag_health_status}")
                print("-" * 50)
                
    except Exception as e:
        logger.error(f"Failed: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_pre_eval())
