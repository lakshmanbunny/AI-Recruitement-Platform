from typing import Dict, Any, List, Optional
import json
from datetime import datetime

from app.db import repository
from app.db.database import SessionLocal
from core.llm_service import LLMService
from config.logging_config import get_logger

logger = get_logger(__name__)

class InterviewService:
    def __init__(self):
        self.llm_service = LLMService()

    async def start_interview(self, candidate_id: int, job_id: int) -> Dict[str, Any]:
        """
        Initializes a new persistent interview session.
        """
        db = SessionLocal()
        try:
            # 1. Check for existing active session
            existing_session = repository.get_active_interview_session_by_candidate(db, candidate_id)
            if existing_session:
                logger.info(f"Resuming existing session: {existing_session.session_id}")
                return self._format_session_state(existing_session)

            # 2. Get candidate screening data for question tailoring
            # For now, we assume screening is already done or we use default JD
            jd = repository.get_job_description(db, job_id)
            jd_text = jd.jd_text if jd else "General Technical Role"
            
            # 3. Generate 10 Targeted Questions
            # Note: In a real scenario, we'd pass actual screening results here
            screening_intelligence = {"status": "Screened", "readiness": "MEDIUM"}
            questions = self.llm_service.generate_interview_questions(screening_intelligence, jd_text)
            
            # 4. Create DB Session
            import uuid
            session_id = str(uuid.uuid4())
            db_session = repository.create_interview_session(db, candidate_id, session_id, job_id)
            
            # 5. Persist Questions
            repository.update_interview_progress(db, session_id, {
                "questions": questions,
                "status": "active"
            })
            
            return self._format_session_state(db_session)
        finally:
            db.close()

    async def get_interview_state(self, session_id: str) -> Dict[str, Any]:
        """
        Gets the current state of an interview.
        """
        db = SessionLocal()
        try:
            session = repository.get_interview_session(db, session_id)
            if not session:
                raise Exception("Session not found")
            return self._format_session_state(session)
        finally:
            db.close()

    async def submit_answer(self, session_id: str, answer: str) -> Dict[str, Any]:
        """
        Processes a candidate's answer and determines next steps.
        """
        db = SessionLocal()
        try:
            session = repository.get_interview_session(db, session_id)
            if not session:
                raise Exception("Session not found")
            
            questions = json.loads(session.questions_json)
            cur_idx = session.current_question_index
            
            if cur_idx >= len(questions):
                return {"status": "completed", "message": "Interview already finished"}

            current_q = questions[cur_idx]
            
            # 1. Evaluate Answer
            jd = repository.get_job_description(db, session.job_id)
            jd_text = jd.description if jd else ""
            evaluation = self.llm_service.evaluate_interview_answer(
                current_q, answer, session.transcript_summary, jd_text
            )
            
            # 2. Update Transcript Summary
            new_summary = self.llm_service.summarize_interview_transcript(
                session.transcript_summary, current_q, answer
            )
            
            # 3. Persist Progress
            answers = json.loads(session.answers_json)
            answers.append({"q": current_q, "a": answer, "eval": evaluation})
            
            next_idx = cur_idx + 1
            is_complete = next_idx >= len(questions)
            
            update_data = {
                "answers": answers,
                "summary": new_summary,
                "current_index": next_idx
            }
            
            if is_complete:
                # 4. Final Scoring if done
                final_scoring = self.llm_service.finalize_interview_scoring(new_summary, jd_text)
                repository.finalize_interview_session(db, session_id, final_scoring)
            else:
                repository.update_interview_progress(db, session_id, update_data)
                
            updated_session = repository.get_interview_session(db, session_id)
            return self._format_session_state(updated_session)
        finally:
            db.close()

    def _format_session_state(self, session) -> Dict[str, Any]:
        questions = json.loads(session.questions_json)
        cur_idx = session.current_question_index
        
        return {
            "session_id": session.session_id,
            "status": session.status,
            "current_question": questions[cur_idx] if cur_idx < len(questions) else None,
            "progress": f"{cur_idx}/{len(questions)}",
            "is_completed": session.status == "completed",
            "scores": json.loads(session.final_scores_json) if session.status == "completed" else None,
            "recommendation": session.recommendation
        }

interview_service = InterviewService()
