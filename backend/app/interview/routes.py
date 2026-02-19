import os
import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from livekit import api
from app.core.config import settings
from app.interview.email_service import EmailService

router = APIRouter()
logger = logging.getLogger(__name__)
email_service = EmailService()

# Mock storage for POC (In production, use a database)
interviews_db: Dict[str, Dict[str, Any]] = {}

class InterviewCreateRequest(BaseModel):
    candidate_id: str
    candidate_name: str
    candidate_email: str

class InterviewCreateResponse(BaseModel):
    room_id: str
    invite_sent: bool

@router.post("/create", response_model=InterviewCreateResponse)
async def create_interview(request: InterviewCreateRequest):
    """
    Creates a LiveKit room and sends an interview invitation email.
    """
    room_id = f"int_{uuid.uuid4().hex[:8]}"
    
    try:
        # 1. Create LiveKit Room (Optional: You can also just let it auto-create on join)
        lk_api = api.LiveKitAPI(
            settings.LIVEKIT_URL,
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET
        )
        
        # We don't strictly need to call create_room, as joining an empty room creates it.
        # But it's good practice for pre-allocation if needed.
        
        # 2. Send Invitation Email
        invite_sent = await email_service.send_interview_invite(
            candidate_id=request.candidate_id,
            candidate_name=request.candidate_name,
            candidate_email=request.candidate_email,
            room_id=room_id
        )
        
        # 3. Save Metadata
        interviews_db[room_id] = {
            "candidate_id": request.candidate_id,
            "candidate_name": request.candidate_name,
            "status": "pending",
            "created_at": "now" # In real app, use datetime
        }
        
        return InterviewCreateResponse(room_id=room_id, invite_sent=invite_sent)
        
    except Exception as e:
        logger.error(f"Failed to create interview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Interview creation failed: {str(e)}")

@router.get("/config")
async def get_interview_config():
    """
    Returns the LiveKit configuration for the frontend.
    """
    # Ensure protocol is correct for the client (wss://)
    url = settings.LIVEKIT_URL
    if url.startswith("http"):
        url = url.replace("http", "ws", 1)
    
    return {
        "livekit_url": url
    }

@router.get("/token")
async def get_token(room_id: str, identity: str):
    """
    Generates a LiveKit access token for joining a room.
    """
    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise HTTPException(status_code=500, detail="LiveKit credentials not configured")

    token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) \
        .with_identity(identity) \
        .with_name(identity) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_id,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True
        ))
    
    return {"token": token.to_jwt()}

@router.get("/status")
async def get_interview_status(room_id: str):
    """
    Checks the status of an ongoing or pending interview.
    """
    interview = interviews_db.get(room_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    return interview
