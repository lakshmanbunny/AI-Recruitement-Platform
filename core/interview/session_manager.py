import uuid
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.orm import Session

from app.db import repository
from app.db.models import InterviewSession, ScreeningResult
from core.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)

def create_interview_session(db: Session, candidate_id: int, screening_result_id: int) -> Dict[str, Any]:
    """
    Creates an interview session with exactly 5 adaptive questions 
    based on JD, missing skills, candidate strengths, and unified justification.
    """
    # 1. Fetch data
    candidate = repository.get_candidate(db, candidate_id)
    if not candidate:
        raise ValueError("Candidate not found")
        
    screening = db.query(ScreeningResult).filter(ScreeningResult.id == screening_result_id).first()
    if not screening:
        raise ValueError("Screening result not found")
        
    jd = repository.get_job_description(db, screening.jd_id)
    
    # 2. Extract context
    missing_skills = screening.skill_gaps_json or "None recorded"
    justification = screening.justification_json or "None recorded"
    
    # 3. LLM Generation
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.4,
        convert_system_message_to_human=True
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert technical interviewer. You must generate exactly 5 interview questions for the following candidate."),
        ("user", "Job Description:\n{jd}\n\nCandidate Missing Skills/Weaknesses:\n{missing_skills}\n\nEvaluation Justification:\n{justification}\n\nGenerate exactly 5 adaptive questions. Include a mix of technical depth, conceptual, and scenario-based queries based strictly on the weaknesses and JD. ONLY return a valid JSON array of strings, where each string is a single question.")
    ])
    
    chain = prompt | llm
    
    try:
        response = chain.invoke({
            "jd": jd.jd_text if jd else "General Software Engineer",
            "missing_skills": missing_skills,
            "justification": justification
        })
        
        content = response.content.replace('```json', '').replace('```', '').strip()
        questions = json.loads(content)
        
        # Enforce exact 5 cap
        if not isinstance(questions, list):
            raise ValueError("LLM did not return a list")
            
        questions = questions[:5]
        while len(questions) < 5:
            questions.append("Can you elaborate on a complex technical challenge you solved?")
            
    except Exception as e:
        logger.error(f"Failed to parse LLM questions: {e}. Using fallback questions.")
        questions = [
            "Can you describe a time you had to learn a new technology quickly?",
            "How do you handle technical debt?",
            "What is your approach to testing?",
            "Describe a complex architectural challenge you solved.",
            "How do you prioritize tasks when deadlines are tight?"
        ]
        
    # 4. Generate Session Token & Metadata
    session_id = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(hours=24)
    
    # 5. Store in DB
    interview = InterviewSession(
        session_id=session_id,
        candidate_id=candidate.id,
        job_id=jd.id if jd else None,
        questions_json=json.dumps(questions),
        expires_at=expires_at,
        status="pending"
    )
    db.add(interview)
    
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    return {
        "session_id": session_id,
        "expires_at": expires_at.isoformat(),
        "link": f"{frontend_url}/interview/{session_id}"
    }
