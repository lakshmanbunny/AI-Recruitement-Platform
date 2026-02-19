import sys
import os
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

# Ensure root directory is in path to import existing modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from workflows.init_workflow import create_workflow
from config.logging_config import get_logger

import json
from fastapi.responses import StreamingResponse

from app.db.database import SessionLocal
from app.db import repository
from app.db.models import JobDescription
from data.sample_resumes import SAMPLE_RESUMES, SAMPLE_JOB_DESCRIPTION

logger = get_logger(__name__)

class PipelineService:
    def __init__(self):
        self.workflow = create_workflow()

    async def _get_or_create_active_jd(self, db):
        jd = repository.get_active_jd(db)
        if not jd:
            logger.info("No active JD found in DB. Creating default from sample.")
            jd = repository.create_job_description(db, SAMPLE_JOB_DESCRIPTION)
        return jd

    async def run_screening(self) -> Dict[str, Any]:
        """
        Runs the full AI recruitment screening pipeline with smart caching.
        """
        db = SessionLocal()
        try:
            active_jd = await self._get_or_create_active_jd(db)
            
            # Identify candidates from sample resumes (In prod, these would be in DB)
            candidates_to_screen = SAMPLE_RESUMES
            
            all_cached = True
            cached_ranking = []
            cached_evaluations = {}
            
            for res in candidates_to_screen:
                email = f"{res['candidate_id'].lower()}@example.com"
                cand = repository.get_candidate_by_email(db, email)
                
                if not cand:
                    all_cached = False
                    break
                    
                result = repository.get_screening_result(db, cand.id, active_jd.id)
                if not result:
                    all_cached = False
                    break
                
                # Robust parsing: ensure we don't pass empty dicts to Pydantic if we want None
                def safe_json_load(val, default=None):
                    if not val or val == '{}' or val == '[]':
                        return default
                    try:
                        data = json.loads(val)
                        return data if data else default
                    except:
                        return default

                cached_evaluations[res['candidate_id']] = {
                    "overall_score": int(result.overall_score or 0),
                    "resume_score": int(result.resume_score or 0),
                    "github_score": int(result.github_score or 0),
                    "repo_count": getattr(result, 'repo_count', 0) or 0,
                    "ai_projects": getattr(result, 'ai_projects', 0) or 0,
                    "justification": safe_json_load(getattr(result, 'justification_json', None), [result.recommendation] if result.recommendation else []),
                    "repos": safe_json_load(getattr(result, 'repos_json', None), []),
                    "interview_readiness": safe_json_load(getattr(result, 'interview_readiness_json', None)),
                    "skeptic_analysis": safe_json_load(getattr(result, 'skeptic_analysis_json', None)),
                    "final_decision": result.recommendation,
                    "final_synthesized_decision": safe_json_load(getattr(result, 'final_synthesized_decision_json', None)),
                    "hr_decision": {
                        "decision": getattr(result, 'hr_decision', None),
                        "notes": getattr(result, 'hr_notes', None)
                    },
                    "ai_evidence": safe_json_load(getattr(result, 'ai_evidence_json', None), [])
                }
                cached_ranking.append({
                    "candidate_id": res['candidate_id'],
                    "name": cand.name,
                    "score": result.overall_score,
                    "github_url": cand.github_url
                })

            if all_cached and cached_ranking:
                logger.info("[DB CACHE HIT] Returning results from database.")
                # Sort ranking
                cached_ranking.sort(key=lambda x: x["score"], reverse=True)
                for idx, item in enumerate(cached_ranking, 1):
                    item["rank"] = idx
                return {
                    "ranking": cached_ranking,
                    "evaluations": cached_evaluations
                }

            logger.info("[DB CACHE MISS] Invoking AI Recruitment Pipeline")
            # Invoke the pipeline
            result = self.workflow.invoke({"message": "Starting API-driven screening..."})
            
            # Extract and Format results
            ranking_results = result.get("ranking_results", [])
            llm_evaluations = result.get("llm_evaluations", {})
            github_raw_data = result.get("github_raw_data", {})
            github_features = result.get("github_features", {})
            interview_readiness = result.get("interview_readiness", {})
            skeptic_analysis = result.get("skeptic_analysis", {})
            final_synthesized_decision = result.get("final_synthesized_decision", {})
            
            # Save candidates and results to DB
            logger.info("[SAVING SCREENING RESULT] Persisting intelligence to database.")
            formatted_ranking = []
            formatted_evaluations = {}
            
            for idx, item in enumerate(ranking_results, 1):
                cand_id = item["candidate_id"]
                eval_data = llm_evaluations.get(cand_id, {})
                gh_feat = github_features.get(cand_id, {})
                readiness_data = interview_readiness.get(cand_id, {})
                skeptic_data = skeptic_analysis.get(cand_id, {})
                final_decision_data = final_synthesized_decision.get(cand_id, {})
                
                # Get resume for metadata
                resume_obj = next((r for r in candidates_to_screen if r["candidate_id"] == cand_id), {})
                email = f"{cand_id.lower()}@example.com"
                linkedin_url = resume_obj.get("links", {}).get("linkedin", "")
                
                # Create/Get Candidate
                db_cand = repository.get_candidate_by_email(db, email)
                if not db_cand:
                    db_cand = repository.create_candidate(
                        db, 
                        name=resume_obj.get("name", cand_id),
                        email=email,
                        github_url=resume_obj.get("links", {}).get("github", ""),
                        linkedin_url=linkedin_url
                    )
                else:
                    # Update GitHub/LinkedIn URL if they changed or were missing
                    db_cand.github_url = resume_obj.get("links", {}).get("github", "")
                    db_cand.linkedin_url = linkedin_url
                    db.commit()
                
                # Prepare Result Data
                res_data = {
                    "resume_score": eval_data.get("resume_score", 0),
                    "github_score": eval_data.get("github_score", 0),
                    "overall_score": eval_data.get("overall_score", 0),
                    "risk_level": skeptic_data.get("risk_level", "LOW") if skeptic_data else "LOW",
                    "readiness_level": readiness_data.get("readiness_level", "MEDIUM") if readiness_data else "MEDIUM",
                    "recommendation": final_decision_data.get("final_decision", "PROCEED WITH CAUTION") if final_decision_data else "PROCEED WITH CAUTION",
                    "repo_count": github_raw_data.get(cand_id, {}).get("total_repos", 0),
                    "ai_projects": len(github_raw_data.get(cand_id, {}).get("ai_relevant_repos", [])),
                    "skill_gaps": readiness_data.get("skill_gaps", []) if readiness_data else [],
                    "interview_focus": readiness_data.get("interview_focus", []) if readiness_data else [],
                    "github_features": gh_feat,
                    "repos": result.get("github_code_data", {}).get(cand_id, {}).get("repos", []),
                    "interview_readiness": readiness_data if readiness_data else None,
                    "skeptic_analysis": skeptic_data if skeptic_data else None,
                    "final_synthesized_decision": final_decision_data if final_decision_data else None,
                    "ai_evidence": eval_data.get("ai_evidence", []),
                    "justification": eval_data.get("justification", []),
                    "rank_position": idx
                }
                
                # Save to DB
                saved_res = repository.save_screening_result(db, db_cand.id, active_jd.id, res_data)
                
                # Format for API
                formatted_ranking.append({
                    "rank": idx,
                    "candidate_id": cand_id,
                    "name": db_cand.name,
                    "score": round(float(item["score"]), 4),
                    "github_url": db_cand.github_url
                })
                
                formatted_evaluations[cand_id] = {
                    "overall_score": int(eval_data.get("overall_score", 0)),
                    "resume_score": int(eval_data.get("resume_score", 0)),
                    "github_score": int(eval_data.get("github_score", 0)),
                    "repo_count": github_raw_data.get(cand_id, {}).get("total_repos", 0),
                    "ai_projects": len(github_raw_data.get(cand_id, {}).get("ai_relevant_repos", [])),
                    "justification": eval_data.get("justification", []) or [eval_data.get("recommendation", "N/A")],
                    "repos": result.get("github_code_data", {}).get(cand_id, {}).get("repos", []),
                    "interview_readiness": readiness_data if readiness_data else None,
                    "skeptic_analysis": skeptic_data if skeptic_data else None,
                    "final_decision": final_decision_data.get("final_decision", "PROCEED WITH CAUTION") if final_decision_data else "PROCEED WITH CAUTION",
                    "final_synthesized_decision": final_decision_data if final_decision_data else None,
                    "hr_decision": {
                        "decision": saved_res.hr_decision,
                        "notes": saved_res.hr_notes
                    },
                    "ai_evidence": eval_data.get("ai_evidence", [])
                }
            
            return {
                "ranking": formatted_ranking,
                "evaluations": formatted_evaluations
            }
        except Exception as e:
            logger.error(f"Pipeline execution failed: {str(e)}")
            raise e
        finally:
            db.close()

    async def re_evaluate(self, candidate_id: str) -> Dict[str, Any]:
        """
        Deletes existing result and re-runs the pipeline.
        """
        db = SessionLocal()
        try:
            active_jd = await self._get_or_create_active_jd(db)
            candidates = repository.list_candidates(db)
            target_cand = next((c for c in candidates if candidate_id in [c.name, str(c.id)]), None)
            
            if target_cand:
                repository.delete_screening_result(db, target_cand.id, active_jd.id)
            
            return await self.run_screening()
        finally:
            db.close()

    async def get_stored_results(self) -> Dict[str, Any]:
        """
        Fetches existing results from DB. Returns empty data if nothing found.
        """
        db = SessionLocal()
        try:
            active_jd = await self._get_or_create_active_jd(db)
            all_results = repository.list_screening_results(db, active_jd.id)
            
            if not all_results:
                return {"ranking": [], "evaluations": {}}
                
            formatted_ranking = []
            formatted_evaluations = {}
            
            # Helper for robust JSON loading
            def safe_json_load(val, default=None):
                if not val or val == '{}' or val == '[]':
                    return default
                try:
                    data = json.loads(val)
                    return data if data else default
                except:
                    return default

            for idx, res in enumerate(sorted(all_results, key=lambda x: x.overall_score, reverse=True), 1):
                cand = res.candidate
                cand_id = cand.email.split('@')[0].upper() # Reconstruct C001 style ID
                
                formatted_ranking.append({
                    "rank": idx,
                    "candidate_id": cand_id,
                    "name": cand.name,
                    "score": res.overall_score,
                    "github_url": cand.github_url
                })
                
                formatted_evaluations[cand_id] = {
                    "overall_score": int(res.overall_score or 0),
                    "resume_score": int(res.resume_score or 0),
                    "github_score": int(res.github_score or 0),
                    "repo_count": getattr(res, 'repo_count', 0) or 0,
                    "ai_projects": getattr(res, 'ai_projects', 0) or 0,
                    "justification": safe_json_load(getattr(res, 'justification_json', None), [res.recommendation] if res.recommendation else []),
                    "repos": safe_json_load(getattr(res, 'repos_json', None), []),
                    "interview_readiness": safe_json_load(getattr(res, 'interview_readiness_json', None)),
                    "skeptic_analysis": safe_json_load(getattr(res, 'skeptic_analysis_json', None)),
                    "final_decision": res.recommendation,
                    "final_synthesized_decision": safe_json_load(getattr(res, 'final_synthesized_decision_json', None)),
                    "hr_decision": {
                        "decision": res.hr_decision,
                        "notes": res.hr_notes,
                        "status": "COMPLETED" if res.hr_decision else "PENDING"
                    },
                    "ai_evidence": safe_json_load(getattr(res, 'ai_evidence_json', None), [])
                }
                
            return {
                "ranking": formatted_ranking,
                "evaluations": formatted_evaluations
            }
        finally:
            db.close()

    async def run_screening_stream(self):
        """
        Runs the screening pipeline and yields progress updates as NDJSON.
        Optimized to skip simulation on cache hits.
        """
        import json
        db = SessionLocal()
        try:
            active_jd = await self._get_or_create_active_jd(db)
            
            # Check for cache hit
            candidates_to_screen = SAMPLE_RESUMES
            all_cached = True
            for res in candidates_to_screen:
                email = f"{res['candidate_id'].lower()}@example.com"
                cand = repository.get_candidate_by_email(db, email)
                if not cand:
                    all_cached = False
                    break
                result = repository.get_screening_result(db, cand.id, active_jd.id)
                if not result:
                    all_cached = False
                    break
            
            if all_cached:
                logger.info("[STREAM] Cache Hit detected. Skipping simulation.")
                results = await self.run_screening()
                yield json.dumps({"step": 8, "results": results}) + "\n"
                return

            # If not cached, yield progress stages
            stages = [
                {"step": 0, "status": "System Initialization"},
                {"step": 1, "status": "Data Ingestion"},
                {"step": 2, "status": "Semantic Indexing"},
                {"step": 3, "status": "Neural Retrieval"},
                {"step": 4, "status": "GitHub Validation"},
                {"step": 5, "status": "Holistic Evaluation"},
                {"step": 6, "status": "Readiness Audit"},
                {"step": 7, "status": "Skeptic Review"},
                {"step": 8, "status": "Decision Synthesis"}
            ]
            
            for stage in stages:
                yield json.dumps(stage) + "\n"
                await asyncio.sleep(0.4)

            results = await self.run_screening()
            yield json.dumps({"step": 8, "results": results}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"
        finally:
            db.close()

    async def submit_hr_decision(self, request: Any) -> Dict[str, Any]:
        """
        Persists HR decision to DB and returns the decision object for UI sync.
        """
        db = SessionLocal()
        try:
            active_jd = await self._get_or_create_active_jd(db)
            
            # Find candidate to get the DB ID
            email = f"{str(request.candidate_id).lower()}@example.com"
            target_cand = repository.get_candidate_by_email(db, email)
            
            if not target_cand:
                # Fallback to name/id lookup for safety
                candidates = repository.list_candidates(db)
                target_cand = next((c for c in candidates if str(request.candidate_id).upper() in [c.name.upper(), str(c.id)]), None)
            
            if not target_cand:
                logger.error(f"Candidate not found for decision: {request.candidate_id}")
                raise Exception("Candidate not found")

            # Persist decision
            repository.update_screening_hr_decision(
                db, 
                target_cand.id, 
                active_jd.id, 
                request.decision, 
                request.notes
            )
            
            logger.info(f"HR Decision '{request.decision}' persisted for {target_cand.name}")
            
            return {
                "message": f"Decision '{request.decision}' recorded successfully.",
                "candidate_id": request.candidate_id,
                "hr_decision": {
                    "decision": request.decision,
                    "notes": request.notes,
                    "timestamp": datetime.now().isoformat(),
                    "status": "COMPLETED"
                }
            }
        finally:
            db.close()

pipeline_service = PipelineService()
