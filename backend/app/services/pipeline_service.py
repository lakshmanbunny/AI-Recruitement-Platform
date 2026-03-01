import sys
import os
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

# Ensure root directory is in path to import existing modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from core.settings import settings
from workflows.init_workflow import create_workflow
from config.logging_config import get_logger
from core.llama_indexing.resume_indexer import ResumeLlamaIndexer

import json
from fastapi.responses import StreamingResponse

from app.db.database import SessionLocal
from app.db import repository
from app.db.models import JobDescription
from data.sample_resumes import SAMPLE_RESUMES

logger = get_logger(__name__)

class PipelineService:
    def __init__(self):
        self.workflow = create_workflow()
        self.llama_indexer = ResumeLlamaIndexer()
        
        # Clear stale results on startup if version mismatch
        db = SessionLocal()
        try:
            cleared = repository.clear_stale_results(db, settings.RETRIEVAL_VERSION)
            if cleared > 0:
                logger.info(f"[CACHE INVALIDATION] Cleared {cleared} stale results for version {settings.RETRIEVAL_VERSION}")
        finally:
            db.close()

    async def _get_or_create_active_jd(self, db):
        jd = repository.get_active_jd(db)
        if not jd:
            jd_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../NEW-JD"))
            logger.info(f"No active JD found in DB. Reading from {jd_path}")
            try:
                with open(jd_path, "r", encoding="utf-8") as f:
                    jd_text = f.read()
            except Exception as e:
                logger.error(f"Failed to read NEW-JD from {jd_path}: {e}")
                jd_text = "Fallback Job Description: AI Engineer"
            jd = repository.create_job_description(db, jd_text)
        return jd

    async def run_screening(self, force_eval: bool = False, target_candidate_id: Optional[str] = None, evaluation_weights: Optional[Dict[str, float]] = None, candidates: Optional[List[Dict[str, Any]]] = None, skip_llm_eval: bool = False) -> Dict[str, Any]:
        """
        Runs the full AI recruitment screening pipeline with smart caching.
        """
        db = SessionLocal()
        try:
            active_jd = await self._get_or_create_active_jd(db)
            
            # Identify candidates (Default to Woxsen candidates from DB if none provided)
            candidates_to_screen = candidates
            if candidates_to_screen is None:
                db_woxsen = repository.list_woxsen_candidates(db)
                candidates_to_screen = []
                for wc in db_woxsen:
                    candidates_to_screen.append({
                        "candidate_id": wc.roll_number,
                        "name": wc.name,
                        "links": {
                            "github": wc.github_url or "",
                            "linkedin": wc.linkedin_url or ""
                        }
                    })
            
            if not candidates_to_screen:
                candidates_to_screen = SAMPLE_RESUMES
            
            all_cached = True
            cached_ranking = []
            cached_evaluations = {}
            
            # ALWAYS load cache for partial updates (e.g force-evaluate 1 candidate)
            if True:
                for res in candidates_to_screen:
                    cand = repository.get_candidate_by_fuzzy_id(db, res['candidate_id'])
                    
                    if not cand:
                        all_cached = False
                        break
                        
                    result = repository.get_screening_result(db, cand.id, active_jd.id)
                    
                    # STRICT CACHE LOOKUP: Must match version and be healthy
                    if not result or result.retrieval_version != settings.RETRIEVAL_VERSION:
                        all_cached = False
                        break
                    
                    if result.rag_status != "healthy" or not result.rag_enabled:
                        all_cached = False
                        break
                    
                    # Verify index exists on disk
                    if not self.llama_indexer.is_llama_index_ready():
                        logger.warning("[CACHE BYPASS] LlamaIndex not ready on disk. Forcing fresh run.")
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
                        "ai_evidence": safe_json_load(getattr(result, 'ai_evidence_json', None), []),
                        "rag_quality": {
                            "status": getattr(result, 'rag_quality_status', "READY"),
                            "score": getattr(result, 'rag_quality_score', 1.0)
                        },
                        "evaluation_blocked": getattr(result, 'rag_quality_status', "READY") != "READY",
                        "interview_status": getattr(result, 'interview_status', "PENDING"),
                        "evaluation_locked": getattr(result, 'evaluation_locked', False),
                        "interview_session_id": getattr(result, 'interview_session_id', None)
                    }
                    cached_ranking.append({
                        "candidate_id": res['candidate_id'],
                        "name": cand.name,
                        "score": result.overall_score,
                        "github_url": cand.github_url
                    })

                if all_cached and cached_ranking and not force_eval:
                    logger.info("[DB CACHE HIT] Returning results from database.")
                    # Sort ranking
                    cached_ranking.sort(key=lambda x: x["score"], reverse=True)
                    for idx, item in enumerate(cached_ranking, 1):
                        item["rank"] = idx
                    return {
                        "ranking": cached_ranking,
                        "evaluations": cached_evaluations
                    }



            logger.info(f"[PIPELINE] Invoking AI Recruitment Pipeline (Force Eval: {force_eval})")
            # Invoke the pipeline
            result = self.workflow.invoke({
                "message": "Starting API-driven screening...",
                "force_evaluation": force_eval,
                "target_candidate_id": target_candidate_id,
                "evaluation_weights": evaluation_weights,
                "resumes": candidates_to_screen, # Pass injected resumes
                "skip_llm_eval": skip_llm_eval
            })
            
            # Extract and Format results
            ranking_results = result.get("ranking_results", [])
            llm_evaluations = result.get("llm_evaluations", {})
            github_raw_data = result.get("github_raw_data", {})
            github_features = result.get("github_features", {})
            interview_readiness = result.get("interview_readiness", {})
            skeptic_analysis = result.get("skeptic_analysis", {})
            final_synthesized_decision = result.get("final_synthesized_decision", {})
            rag_metrics = result.get("rag_metrics", {})
            rag_health_status = result.get("rag_health_status", {})
            rag_gate_decisions = result.get("rag_gate_decisions", {})
            ragas_metrics_full = result.get("ragas_metrics_full", {})
            
            # Save candidates and results to DB
            logger.info("[SAVING SCREENING RESULT] Persisting intelligence to database.")
            
            # --- PHASE 1: Persistent Stage 1 Metrics for ALL evaluated candidates ---
            # This ensures even non-shortlisted candidates have metrics in the grid
            for cand_id, metrics in rag_metrics.items():
                resume_obj = next((r for r in candidates_to_screen if r["candidate_id"] == cand_id), {})
                email = resume_obj.get("email") or f"{cand_id.lower()}@example.com"
                
                db_cand = repository.get_candidate_by_email(db, email)
                if not db_cand:
                    db_cand = repository.create_candidate(
                        db, 
                        name=resume_obj.get("name", cand_id),
                        email=email,
                        github_url=resume_obj.get("links", {}).get("github", ""),
                        linkedin_url=resume_obj.get("links", {}).get("linkedin", "")
                    )
                
                if metrics:
                    try:
                        repository.save_rag_retrieval_metrics(db, db_cand.id, metrics)
                    except Exception as e:
                        logger.error(f"Failed to save deterministic retrieval metrics for {cand_id}: {str(e)}")

            formatted_ranking = []
            formatted_evaluations = {}
            
            for idx, item in enumerate(ranking_results, 1):
                cand_id = item["candidate_id"]
                
                # If target_candidate_id was provided and this is NOT the target candidate,
                # we preserve their existing data from the database cache
                if force_eval and target_candidate_id and cand_id != target_candidate_id:
                    if cand_id in cached_evaluations:
                        formatted_evaluations[cand_id] = cached_evaluations[cand_id]
                        cached_item = next((r for r in cached_ranking if r["candidate_id"] == cand_id), None)
                        if cached_item:
                            formatted_ranking.append(cached_item)
                    continue

                eval_data = llm_evaluations.get(cand_id, {})
                gh_feat = github_features.get(cand_id, {})
                readiness_data = interview_readiness.get(cand_id, {})
                skeptic_data = skeptic_analysis.get(cand_id, {})
                final_decision_data = final_synthesized_decision.get(cand_id, {})
                health = rag_health_status.get(cand_id, "CRITICAL")
                metrics = rag_metrics.get(cand_id, {})
                rag_override = False
                
                # Get resume for metadata
                resume_obj = next((r for r in candidates_to_screen if r["candidate_id"] == cand_id), {})
                email = resume_obj.get("email") or f"{cand_id.lower()}@example.com"
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
                    db_cand.github_url = resume_obj.get("links", {}).get("github", "")
                    db_cand.linkedin_url = linkedin_url
                    db.commit()
                
                # Prepare Result Data
                # Fallback: If Stage 2 LLM scores are missing (e.g. bypassed), use Stage 1 metrics
                stage1_score_scaled = (metrics.get("overall_rag_score", 0.0) * 100) if metrics else 0
                
                res_data = {
                    "resume_score": eval_data.get("resume_score") if eval_data.get("resume_score") is not None else int(stage1_score_scaled),
                    "github_score": eval_data.get("github_score", 0),
                    "overall_score": eval_data.get("overall_score") if eval_data.get("overall_score") is not None else stage1_score_scaled,
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
                    "rank_position": idx,
                    "retrieval_mode": "llama_index",
                    "retrieval_version": settings.RETRIEVAL_VERSION,
                    "rag_enabled": True,
                    "rag_status": "healthy" if health == "HEALTHY" else "failed",
                    "rag_quality_status": health, # Keep legacy field for compatibility
                    "rag_quality_score": metrics.get("overall_rag_score", 0.0),
                    "rag_override": rag_override,
                    "judge_audit": eval_data.get("judge_audit", {}),
                    "rubric_scores": eval_data.get("rubric_scores", {})
                }
                
                # Save to DB
                saved_res = repository.save_screening_result(db, db_cand.id, active_jd.id, res_data)
                
                # Save legacy RAG Metrics
                legacy_metrics_payload = metrics.copy() if metrics else {}
                
                # Inject Stage 2 AI-Assessed Precision/Recall
                if "precision_score" in eval_data:
                    legacy_metrics_payload["precision_score"] = eval_data["precision_score"]
                if "recall_score" in eval_data:
                    legacy_metrics_payload["recall_score"] = eval_data["recall_score"]

                if cand_id in ragas_metrics_full:
                    rm = ragas_metrics_full[cand_id]
                    if isinstance(rm, dict):
                        legacy_metrics_payload.update({
                            "recall": rm.get("recall", 0.0),
                            "answer_relevancy": rm.get("answer_relevancy", 0.0),
                        })
                    else:
                        legacy_metrics_payload.update({
                            "recall": getattr(rm, "recall", 0.0),
                            "answer_relevancy": getattr(rm, "answer_relevancy", 0.0),
                        })
                repository.save_rag_metrics(db, db_cand.id, saved_res.id, legacy_metrics_payload)
                
                # Deterministic Metrics already saved in Phase 1 above

                # Process RAGAS evaluation queue or save override results
                if cand_id in ragas_metrics_full:
                    metric_data = ragas_metrics_full[cand_id]
                    if isinstance(metric_data, dict) and metric_data.get("status") == "PENDING":
                        job = repository.create_rag_evaluation_job(db, db_cand.id)
                        logger.info(f"[JOB ENQUEUED] Pushed job {job.id} to background queue for {cand_id}")
                    elif isinstance(metric_data, dict) and metric_data.get("status") == "OVERRIDE":
                        pass # Nothing to save, it bypassed the gate
                    else:
                        try:
                            # If it was actually evaluated, save it
                            repository.save_rag_evaluation_result(db, db_cand.id, metric_data)
                        except Exception as re:
                            logger.error(f"Failed to save RAGAS metrics for {cand_id}: {str(re)}")

                
                # Format for API
                formatted_ranking.append({
                    "candidate_id": cand_id,
                    "name": db_cand.name,
                    "score": int(eval_data.get("overall_score", 0)),
                    "github_url": db_cand.github_url
                })
                
                formatted_evaluations[cand_id] = {
                    "overall_score": int(eval_data.get("overall_score", 0)),
                    "resume_score": int(eval_data.get("resume_score", 0)),
                    "github_score": int(eval_data.get("github_score", 0)),
                    "precision_score": int(eval_data.get("precision_score", 0)),
                    "recall_score": int(eval_data.get("recall_score", 0)),
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
                    "ai_evidence": eval_data.get("ai_evidence", []),
                    "rag_quality": {
                        "status": getattr(saved_res, 'rag_status', 'failed') or 'failed',
                        "score": metrics.get("overall_rag_score", 1.0) if metrics else 1.0
                    },
                    "evaluation_blocked": health != "HEALTHY",
                    "judge_audit": eval_data.get("judge_audit"),
                    "rubric_scores": eval_data.get("rubric_scores"),
                    "interview_status": "PENDING",
                    "evaluation_locked": False,
                    "interview_session_id": None,
                    "rag_override": rag_override
                }
            formatted_ranking.sort(key=lambda x: x["score"], reverse=True)
            for i, rank_item in enumerate(formatted_ranking, 1):
                rank_item["rank"] = i
            
            return {
                "ranking": formatted_ranking,
                "evaluations": formatted_evaluations
            }
        except Exception as e:
            logger.error(f"Pipeline execution failed: {str(e)}")
            raise e
        finally:
            db.close()

    async def run_bulk_screening(self, file_path: str, evaluation_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Ingests candidates from a file and runs screening for them.
        """
        from app.services.data_ingestion import data_ingestion_service
        logger.info(f"[PIPELINE] Bulk screening triggered for file: {file_path}")
        
        candidates = data_ingestion_service.parse_file(file_path)
        return await self.run_screening(candidates=candidates, evaluation_weights=evaluation_weights)

    async def force_evaluate(self, candidate_id: str, evaluation_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Force-run the pipeline by bypassing RAG quality gate.
        """
        logger.info(f"[API] Force evaluating candidate: {candidate_id}")
        return await self.run_screening(force_eval=True, target_candidate_id=candidate_id, evaluation_weights=evaluation_weights)

    async def toggle_rag_override(self, candidate_id: str, override: bool) -> Dict[str, Any]:
        """
        Toggles the RAG override flag for a candidate's latest screening result.
        Logs override action to RAGEvaluationResult table.
        """
        db = SessionLocal()
        try:
            cand = repository.get_candidate_by_fuzzy_id(db, candidate_id)
            if not cand:
                raise Exception("Candidate not found")

            jd = await self._get_or_create_active_jd(db)
            result = repository.get_screening_result(db, cand.id, jd.id)
            if not result:
                raise Exception("Screening result not found")

            updated = repository.update_rag_override(db, result.id, override)

            # Log override to RAGEvaluationResult table
            if override:
                logger.warning(f"[RAG OVERRIDE TRIGGERED] HR override applied for {candidate_id}")
                repository.log_rag_override(db, cand.id, "HR Dashboard override button clicked")

            return {"candidate_id": candidate_id, "rag_override": updated.rag_override if updated else override}
        finally:
            db.close()

    async def get_candidate_rag_metrics(self, candidate_id: str) -> Dict[str, Any]:
        """
        Returns the full RAGAS evaluation result for a candidate (from RAGEvaluationResult table),
        with fallback to legacy RAGMetric if no RAGAS result exists.
        """
        db = SessionLocal()
        try:
            cand = repository.get_candidate_by_fuzzy_id(db, candidate_id)
            if not cand:
                raise Exception(f"Candidate {candidate_id} not found")

            # Try full RAGAS evaluation result first
            ragas_result = repository.get_rag_evaluation_by_candidate(db, cand.id)
            if ragas_result:
                return {
                    "candidate_id": candidate_id,
                    "precision": ragas_result.precision,
                    "recall": ragas_result.recall,
                    "faithfulness": ragas_result.faithfulness,
                    "relevancy": ragas_result.relevancy,
                    "overall_score": ragas_result.overall_score,
                    "health_status": ragas_result.health_status,
                    "gate_decision": ragas_result.gate_decision,
                    "failure_reasons": json.loads(ragas_result.failure_reasons_json or "[]"),
                    "gating_reason": ragas_result.gating_reason,
                    "override_triggered": ragas_result.override_triggered,
                    "override_reason": ragas_result.override_reason,
                    "timestamp": str(ragas_result.timestamp),
                    "source": "ragas",
                }

            # Fallback to deterministic retrieval metrics
            metrics = repository.get_rag_retrieval_metrics(db, cand.id)
            if not metrics:
                return {"candidate_id": candidate_id, "error": "No RAG metrics found"}

            return {
                "candidate_id": candidate_id,
                "coverage": metrics.coverage,
                "similarity": metrics.similarity,
                "diversity": metrics.diversity,
                "density": metrics.density,
                "overall_score": metrics.overall_score,
                "health_status": metrics.rag_health_status,
                "source": "deterministic_retrieval",
            }
        finally:
            db.close()

    async def get_rag_run_summary(self) -> Dict[str, Any]:
        """
        Returns system-wide RAG health summary across all candidates in the latest run.
        """
        from app.db.models import RAGEvaluationResult
        db = SessionLocal()
        try:
            all_results = db.query(RAGEvaluationResult).all()
            if not all_results:
                return {"total_candidates": 0, "message": "No RAG evaluation results found."}

            healthy = sum(1 for r in all_results if r.health_status == "HEALTHY")
            warning = sum(1 for r in all_results if r.health_status == "WARNING")
            critical = sum(1 for r in all_results if r.health_status == "CRITICAL")
            blocked = sum(1 for r in all_results if r.gate_decision == "BLOCK")
            overridden = sum(1 for r in all_results if r.override_triggered)
            
            all_scores = [r.overall_score for r in all_results if r.overall_score is not None]
            avg_overall = round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0

            return {
                "total_candidates": len(all_results),
                "healthy_count": healthy,
                "warning_count": warning,
                "critical_count": critical,
                "blocked_count": blocked,
                "overridden_count": overridden,
                "average_overall_score": avg_overall,
                "average_precision": round(sum(r.precision for r in all_results) / len(all_results), 4),
                "average_recall": round(sum(r.recall for r in all_results) / len(all_results), 4),
                "average_faithfulness": round(sum(r.faithfulness for r in all_results) / len(all_results), 4),
                "average_relevancy": round(sum(r.relevancy for r in all_results) / len(all_results), 4),
            }
        finally:
            db.close()


    async def re_evaluate(self, candidate_id: str) -> Dict[str, Any]:
        """
        Deletes existing result and re-runs the pipeline.
        """
        db = SessionLocal()
        try:
            active_jd = await self._get_or_create_active_jd(db)
            target_cand = repository.get_candidate_by_fuzzy_id(db, candidate_id)
            
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
            stage2_results = repository.list_screening_results(db, active_jd.id)

            # Helper for robust JSON loading
            def safe_json_load(val, default=None):
                if not val or val == '{}' or val == '[]':
                    return default
                try:
                    data = json.loads(val)
                    return data if data else default
                except:
                    return default

            formatted_ranking = []
            formatted_evaluations = {}
            stage2_candidate_ids = set()

            # --- Phase 1: Build Stage 2 (LLM-evaluated) entries ---
            sorted_stage2 = sorted(stage2_results, key=lambda x: (x.overall_score or 0.0, -(x.rank_position or 9999)), reverse=True)
            for idx, res in enumerate(sorted_stage2, 1):
                cand = res.candidate
                cand_id = cand.email.split('@')[0].upper()
                stage2_candidate_ids.add(cand.id)

                metric_rec = repository.get_rag_retrieval_metrics(db, cand.id)
                metrics = {}
                if metric_rec:
                    metrics = {
                        "coverage": metric_rec.coverage,
                        "similarity": metric_rec.similarity,
                        "diversity": metric_rec.diversity,
                        "density": metric_rec.density,
                        "overall_score": metric_rec.overall_score
                    }

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
                    "precision_score": int(metrics.get("precision_score", 0)),
                    "recall_score": int(metrics.get("recall_score", 0)),
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
                    "ai_evidence": safe_json_load(getattr(res, 'ai_evidence_json', None), []),
                    "judge_audit": safe_json_load(getattr(res, 'judge_audit_json', None)),
                    "rubric_scores": safe_json_load(getattr(res, 'rubric_scores_json', None)),
                    "rag_quality": {
                        "status": getattr(res, 'rag_status', 'CRITICAL') or 'CRITICAL',
                        "score": metrics.get("overall_score", 0.0),
                        "metrics": metrics
                    },
                    "evaluation_blocked": (getattr(res, 'rag_status', 'CRITICAL') != "healthy") and not getattr(res, 'rag_override', False),
                    "stage": "stage2"
                }

            # --- Phase 2: Append Stage 1-only candidates (not shortlisted for Stage 2) ---
            all_stage1 = repository.list_all_rag_retrieval_metrics(db)
            stage1_only = [m for m in all_stage1 if m.candidate_id not in stage2_candidate_ids]

            stage2_count = len(formatted_ranking)
            for idx, m in enumerate(stage1_only, stage2_count + 1):
                cand = m.candidate
                cand_id = cand.email.split('@')[0].upper()

                metrics = {
                    "coverage": m.coverage,
                    "similarity": m.similarity,
                    "diversity": m.diversity,
                    "density": m.density,
                    "overall_score": m.overall_score
                }

                formatted_ranking.append({
                    "rank": idx,
                    "candidate_id": cand_id,
                    "name": cand.name,
                    "score": 0,  # No Stage 2 score
                    "github_url": cand.github_url
                })

                formatted_evaluations[cand_id] = {
                    "overall_score": 0,
                    "resume_score": 0,
                    "github_score": 0,
                    "precision_score": 0,
                    "recall_score": 0,
                    "repo_count": 0,
                    "ai_projects": 0,
                    "justification": [],
                    "repos": [],
                    "interview_readiness": None,
                    "skeptic_analysis": None,
                    "final_decision": "PENDING DEEP EVALUATION",
                    "final_synthesized_decision": None,
                    "hr_decision": {"decision": None, "notes": None, "status": "PENDING"},
                    "ai_evidence": [],
                    "judge_audit": None,
                    "rubric_scores": None,
                    "rag_quality": {
                        "status": m.rag_health_status,
                        "score": m.overall_score,
                        "metrics": metrics
                    },
                    "evaluation_blocked": m.rag_health_status != "HEALTHY",
                    "stage": "stage1_only"
                }

            return {
                "ranking": formatted_ranking,
                "evaluations": formatted_evaluations
            }
        finally:
            db.close()

    async def run_screening_stream(self, evaluation_weights: Optional[Dict[str, float]] = None):
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
                results = await self.run_screening(evaluation_weights=evaluation_weights)
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

            results = await self.run_screening(evaluation_weights=evaluation_weights)
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
            
            # Find candidate using robust fuzzy lookup
            target_cand = repository.get_candidate_by_fuzzy_id(db, request.candidate_id)
            
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

    async def approve_interview(self, candidate_identifier: str) -> Dict[str, Any]:
        """
        Locks evaluation, validates state, and triggers the HITL Interview generation flow.
        """
        print(f"DEBUG: approve_interview called for {candidate_identifier}")
        db = SessionLocal()
        try:
            print(f"DEBUG: Starting DB query for {candidate_identifier}")
            cand = repository.get_candidate_by_fuzzy_id(db, candidate_identifier)
            if not cand:
                print(f"DEBUG: Candidate not found")
                raise ValueError(f"Candidate not found: {candidate_identifier}")
                
            print(f"DEBUG: Getting screening result for cand_id {cand.id}")
            screening = repository.get_latest_screening_result(db, cand.id)
            if not screening:
                print(f"DEBUG: No evaluation found")
                raise ValueError("No unified evaluation found to lock")

            print(f"DEBUG: Found screening. Locking...")
            # 1. Lock evaluation & update status
            screening.evaluation_locked = True
            screening.interview_status = "APPROVED"
            
            # 2. Trigger Session Creation (To be implemented in session_manager.py)
            from core.interview.session_manager import create_interview_session
            session_meta = create_interview_session(db, cand.id, screening.id)
            screening.interview_session_id = session_meta['session_id']

            # 3. Trigger Email (To be implemented in interview_email.py)
            from core.notifications.interview_email import send_interview_invite
            invite_sent = send_interview_invite(cand.email, session_meta['link'], cand.name)
            if invite_sent:
                screening.interview_invite_sent = True
                screening.interview_status = "INTERVIEW_SENT"

            db.commit()
            
            return {
                "message": "Candidate approved. Interview session created and invitation sent.",
                "candidate_id": candidate_identifier,
                "interview_status": screening.interview_status,
                "evaluation_locked": screening.evaluation_locked,
                "session_id": screening.interview_session_id
            }
        finally:
            db.close()

pipeline_service = PipelineService()
