from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from typing import Dict
from app.models.response_models import ScreeningResponse, HRDecisionRequest
from app.services.pipeline_service import pipeline_service
from app.services.interview_service import interview_service
from app.db.database import get_db

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "running"}

@router.post("/screen", response_model=ScreeningResponse)
async def run_screening():
    try:
        results = await pipeline_service.run_screening()
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

@router.post("/screen-stream")
async def run_screening_stream():
    from fastapi.responses import StreamingResponse
    try:
        return StreamingResponse(
            pipeline_service.run_screening_stream(),
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
