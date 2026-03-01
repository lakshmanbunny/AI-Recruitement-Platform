import sys
import os
import asyncio
import json
import logging
from typing import List, Dict, Any

# Setup paths
backend_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, "../"))
if backend_dir not in sys.path: sys.path.insert(0, backend_dir)
if project_root not in sys.path: sys.path.insert(0, project_root)

from app.db.database import SessionLocal
from app.db import models
from app.services.pipeline_service import PipelineService

# Setup minimal logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("woxsen_trigger")

def parse_extracted_sections(raw_json_str: str) -> Dict[str, str]:
    """
    Parses the structured JSON output from Gemini and maps its sections
    (Education, Skills, Experience, Projects) to a flat dictionary for the pipeline.
    """
    if not raw_json_str:
        return {"skills": "", "experience": "", "education": "", "projects": ""}
        
    try:
        data = json.loads(raw_json_str)
        # We no longer statically map headers. 
        # We just want LlamaIndex to natively chew on the entire raw text.
        return raw_json_str
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        return ""

async def run_woxsen_cohort():
    """
    Fetches all Woxsen candidates from the DB, maps their parsed JSON to the pipeline schema,
    and runs the LangGraph evaluation.
    """
    db = SessionLocal()
    candidates_to_screen: List[Dict[str, Any]] = []
    
    try:
        # 1. Fetch Candidates
        woxsen_db_candidates = db.query(models.WoxsenCandidate).filter(
            models.WoxsenCandidate.raw_resume_text.isnot(None)
        ).all()
        
        logger.info(f"Loaded {len(woxsen_db_candidates)} Woxsen Candidates with valid JSON from the database.")
        
        # 2. Map Data
        for cand in woxsen_db_candidates:
            raw_text = parse_extracted_sections(cand.raw_resume_text)
            
            # Construct dictionary, bypassing the rigid legacy structure
            mapped_candidate = {
                "candidate_id": cand.roll_number,
                "name": cand.name,
                "email": cand.email,
                "links": {
                    "github": cand.github_url or "",
                    "linkedin": cand.linkedin_url or ""
                },
                "raw_resume_text": raw_text # Inject entire dynamic JSON here
            }
            candidates_to_screen.append(mapped_candidate)
            
        if not candidates_to_screen:
            logger.error("No valid candidates mapped. Exiting.")
            return

        logger.info("Successfully mapped cohort. Running on ALL candidates...")
        
        # 3. Trigger Pipeline
        pipeline = PipelineService()
        
        logger.info(f"Triggering LangGraph evaluation for {len(candidates_to_screen)} candidates...")
        # Since force_eval=False, if the result already exists for the current RETRIEVAL_VERSION, 
        # it will instantly return from cache. Otherwise it runs the graph.
        result = await pipeline.run_screening(
            candidates=candidates_to_screen,
            force_eval=True # We force evaluation for this first bulk run to ensure semantic injection
        )
        
        # 4. Success summary
        ranking = result.get("ranking", [])
        logger.info(f"\n✅ Successfully evaluated and ranked {len(ranking)} Woxsen Candidates!")
        for rank in ranking[:10]: # Print top 10
            logger.info(f"Rank {rank.get('rank')}: {rank.get('candidate_id')} - Score: {rank.get('score')} - Name: {rank.get('name')}")
            
    except Exception as e:
        logger.error(f"Pipeline trigger failed: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_woxsen_cohort())
