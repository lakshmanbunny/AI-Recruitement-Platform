import os
from fastapi import APIRouter, HTTPException, Depends, Body, File, UploadFile
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from app.models.response_models import ScreeningResponse, HRDecisionRequest
from app.services.pipeline_service import pipeline_service
from app.services.interview_service import interview_service
from app.db.database import get_db

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "running"}

class ScreeningRequest(BaseModel):
    evaluation_weights: Optional[Dict[str, float]] = None

@router.post("/screen", response_model=ScreeningResponse)
async def run_screening(req: ScreeningRequest = Body(default=None)):
    try:
        weights = req.evaluation_weights if req else None
        results = await pipeline_service.run_screening(evaluation_weights=weights)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline screening failed: {str(e)}")

@router.get("/results", response_model=ScreeningResponse)
async def get_results():
    try:
        results = await pipeline_service.get_stored_results()
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch results: {str(e)}")

@router.post("/re-evaluate/{candidate_id}")
async def re_evaluate_candidate(candidate_id: str):
    try:
        results = await pipeline_service.re_evaluate(candidate_id)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-evaluation failed: {str(e)}")

@router.post("/candidate/{candidate_id}/approve-interview")
async def approve_interview(candidate_id: str):
    try:
        result = await pipeline_service.approve_interview(candidate_id)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to approve interview: {str(e)}")

class ForceEvaluateRequest(BaseModel):
    evaluation_weights: Optional[Dict[str, float]] = None

@router.post("/force-evaluate/{candidate_id}")
async def force_evaluate_candidate(candidate_id: str, req: ForceEvaluateRequest = Body(default=None)):
    try:
        weights = req.evaluation_weights if req else None
        results = await pipeline_service.force_evaluate(candidate_id, evaluation_weights=weights)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Force evaluation failed: {str(e)}")

@router.post("/screen-stream")
async def run_screening_stream(req: ScreeningRequest = Body(default=None)):
    from fastapi.responses import StreamingResponse
    try:
        weights = req.evaluation_weights if req else None
        return StreamingResponse(
            pipeline_service.run_screening_stream(evaluation_weights=weights),
            media_type="application/x-ndjson"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming Pipeline failed: {str(e)}")

@router.post("/hr-decision")
async def submit_hr_decision(request: HRDecisionRequest):
    try:
        return await pipeline_service.submit_hr_decision(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit HR decision: {str(e)}")

@router.get("/rag/metrics/{candidate_id}")
async def get_rag_metrics(candidate_id: str):
    try:
        return await pipeline_service.get_candidate_rag_metrics(candidate_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/rag-override/{candidate_id}")
async def toggle_rag_override(candidate_id: str, payload: Dict[str, bool] = Body(...)):
    try:
        override = payload.get("override", False)
        return await pipeline_service.toggle_rag_override(candidate_id, override)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rag/evaluation/{candidate_id}")
async def get_rag_evaluation(candidate_id: str):
    """Returns the full RAGAS evaluation result for a candidate."""
    try:
        return await pipeline_service.get_candidate_rag_metrics(candidate_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/rag/summary")
async def get_rag_summary():
    """Returns a system-wide summary of RAG health for the latest screening run."""
    try:
        return await pipeline_service.get_rag_run_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rag/evaluation-status/{candidate_id}")
async def get_rag_evaluation_status(candidate_id: str, db: Session = Depends(get_db)):
    """
    Returns the status of the background RAGAS evaluation job for a candidate.
    """
    try:
        from app.db import repository
        
        db_cand = repository.get_candidate_by_fuzzy_id(db, candidate_id)
        if not db_cand:
            raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found in database")
            
        job = repository.get_latest_rag_evaluation_job(db, db_cand.id)
        if not job:
            return {"status": "none"}
            
        import json
        metrics = None
        if job.metrics_json:
            try:
                metrics = job.metrics_json if isinstance(job.metrics_json, dict) else json.loads(job.metrics_json)
            except Exception as e:
                pass
        
        return {
            "job_id": job.id,
            "status": job.status,
            "metrics": metrics,
            "error": job.error_message
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rag/retrieval-metrics/{candidate_id}")
async def get_rag_retrieval_metrics_api(candidate_id: str, db: Session = Depends(get_db)):
    """
    Returns deterministic zero-LLM retrieval quality metrics.
    """
    try:
        from app.db import repository
        
        db_cand = repository.get_candidate_by_fuzzy_id(db, candidate_id)
        if not db_cand:
            raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")
            
        metrics = repository.get_rag_retrieval_metrics(db, db_cand.id)
        if not metrics:
            return None
            
        return {
            "precision": metrics.precision,
            "recall": metrics.recall,
            "coverage": metrics.coverage,
            "similarity": metrics.similarity,
            "diversity": metrics.diversity,
            "density": metrics.density,
            "overall_score": metrics.overall_score,
            "rag_health_status": metrics.rag_health_status,
            "evaluated_at": metrics.evaluated_at
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RunLLMEvaluationRequest(BaseModel):
    candidate_ids: List[str]
    evaluation_weights: Optional[Dict[str, float]] = None

@router.post("/rag/run-llm-evaluation")
async def run_llm_evaluation(request: RunLLMEvaluationRequest, db: Session = Depends(get_db)):
    """
    Triggers an async background job for Post-LLM RAG evaluation for selected candidates.
    """
    try:
        from app.db import repository
        
        job_ids = []
        for cand_id in request.candidate_ids:
            db_cand = repository.get_candidate_by_fuzzy_id(db, cand_id)
            if db_cand:
                job = repository.create_llm_eval_job(db, db_cand.id, request.evaluation_weights)
                job_ids.append(job.id)
                
        return {"status": "success", "jobs_created": len(job_ids), "job_ids": job_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rag/llm-evaluation-status/{candidate_id}")
async def get_llm_evaluation_status(candidate_id: str, db: Session = Depends(get_db)):
    """
    Returns the background job status of Post-LLM RAG Audit for a candidate.
    """
    try:
        from app.db import repository
        
        db_cand = repository.get_candidate_by_fuzzy_id(db, candidate_id)
        if not db_cand:
            raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")
            
        job = repository.get_llm_eval_job_by_candidate(db, db_cand.id)
        if not job:
            return {"status": "none"}
            
        return {
            "job_id": job.id,
            "status": job.status,
            "error": job.error_message
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rag/llm-metrics/{candidate_id}")
async def get_llm_rag_metrics_api(candidate_id: str, db: Session = Depends(get_db)):
    """
    Returns the Post-LLM RAG Evaluation metrics.
    """
    try:
        from app.db import repository
        
        db_cand = repository.get_candidate_by_fuzzy_id(db, candidate_id)
        if not db_cand:
            raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")
            
        metrics = repository.get_rag_llm_metrics(db, db_cand.id)
        if not metrics:
            return None
            
        return {
            "precision": metrics.precision if hasattr(metrics, 'precision') else 0.0,
            "recall": metrics.recall if hasattr(metrics, 'recall') else 0.0,
            "faithfulness": metrics.faithfulness,
            "answer_relevance": metrics.answer_relevance,
            "hallucination_score": metrics.hallucination_score,
            "context_utilization": metrics.context_utilization,
            "overall_score": metrics.overall_score,
            "rag_health_status": metrics.rag_health_status,
            "explanation": metrics.explanation,
            "evaluated_at": metrics.evaluated_at
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Interview Intelligence Routes ---

@router.post("/interview/start")
async def start_interview(candidate_id: int, job_id: int):
    try:
        return await interview_service.start_interview(candidate_id, job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/interview/{session_id}/state")
async def get_interview_state(session_id: str):
    try:
        return await interview_service.get_interview_state(session_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/interview/{session_id}/answer")
async def submit_answer(session_id: str, payload: Dict[str, str] = Body(...)):
    try:
        answer = payload.get("answer")
        if not answer:
            raise HTTPException(status_code=400, detail="Answer is required")
        return await interview_service.submit_answer(session_id, answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/candidates/upload")
async def upload_candidates(file: UploadFile = File(...)):
    """
    Uploads a CSV/Excel file of candidates and returns a preview.
    """
    import shutil
    import tempfile
    
    # Save uploaded file to temp
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
        
    try:
        from app.services.data_ingestion import data_ingestion_service
        candidates = data_ingestion_service.parse_file(tmp_path)
        return {"filename": file.filename, "count": len(candidates), "candidates": candidates[:10]} # Preview first 10
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@router.post("/candidates/upload-screen")
async def upload_and_screen(file: UploadFile = File(...), req: Optional[Dict[str, Any]] = Body(None)):
    """
    Uploads a file and immediately runs the screening pipeline.
    """
    import shutil
    import tempfile
    
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
        
    try:
        weights = req.get("evaluation_weights") if req else None
        results = await pipeline_service.run_bulk_screening(tmp_path, evaluation_weights=weights)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk screening failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
