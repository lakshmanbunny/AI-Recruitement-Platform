from sqlalchemy.orm import Session
from . import models
from .models import Candidate, JobDescription, ScreeningResult, InterviewSession
import json
from typing import List, Optional

# --- Candidate Repositories ---
def create_candidate(db: Session, name: str, email: str, github_url: str, linkedin_url: Optional[str] = None):
    db_candidate = Candidate(
        name=name,
        email=email,
        github_url=github_url,
        linkedin_url=linkedin_url
    )
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    return db_candidate

def get_candidate(db: Session, candidate_id: int):
    return db.query(Candidate).filter(Candidate.id == candidate_id).first()

def get_candidate_by_email(db: Session, email: str):
    return db.query(Candidate).filter(Candidate.email == email).first()

def list_candidates(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Candidate).offset(skip).limit(limit).all()

# --- JD Repositories ---
def create_job_description(db: Session, jd_text: str):
    jd_hash = JobDescription.generate_hash(jd_text)
    # Check if exists
    existing = get_jd_by_hash(db, jd_hash)
    if existing:
        return existing
        
    db_jd = JobDescription(
        jd_text=jd_text,
        jd_hash=jd_hash,
        is_active=True
    )
    # Mark others as inactive if needed, or handle active JD logic separately
    db.add(db_jd)
    db.commit()
    db.refresh(db_jd)
    return db_jd

def get_active_jd(db: Session):
    return db.query(JobDescription).filter(JobDescription.is_active == True).order_by(JobDescription.created_at.desc()).first()

def get_jd_by_hash(db: Session, jd_hash: str):
    return db.query(JobDescription).filter(JobDescription.jd_hash == jd_hash).first()

def get_job_description(db: Session, job_id: int):
    return db.query(JobDescription).filter(JobDescription.id == job_id).first()

# --- Screening Results Repositories ---
def get_screening_result(db: Session, candidate_id: int, jd_id: int):
    return db.query(ScreeningResult).filter(
        ScreeningResult.candidate_id == candidate_id,
        ScreeningResult.jd_id == jd_id
    ).first()

def list_screening_results(db: Session, jd_id: int):
    return db.query(ScreeningResult).filter(ScreeningResult.jd_id == jd_id).all()

def save_screening_result(db: Session, candidate_id: int, jd_id: int, result_data: dict):
    # Check if exists to update or create
    existing = get_screening_result(db, candidate_id, jd_id)
    
    # Preserve HR decisions if they exist
    hr_decision = None
    hr_notes = None
    if existing:
        hr_decision = existing.hr_decision
        hr_notes = existing.hr_notes
        db.delete(existing)
        db.commit()

    db_result = ScreeningResult(
        candidate_id=candidate_id,
        jd_id=jd_id,
        resume_score=result_data.get("resume_score"),
        github_score=result_data.get("github_score"),
        overall_score=result_data.get("overall_score"),
        risk_level=result_data.get("risk_level"),
        readiness_level=result_data.get("readiness_level"),
        recommendation=result_data.get("recommendation"),
        repo_count=result_data.get("repo_count", 0),
        ai_projects=result_data.get("ai_projects", 0),
        skill_gaps_json=json.dumps(result_data.get("skill_gaps", [])),
        interview_focus_json=json.dumps(result_data.get("interview_focus", [])),
        github_features_json=json.dumps(result_data.get("github_features", [])),
        repos_json=json.dumps(result_data.get("repos", [])),
        interview_readiness_json=json.dumps(result_data.get("interview_readiness", {})),
        skeptic_analysis_json=json.dumps(result_data.get("skeptic_analysis", {})),
        final_synthesized_decision_json=json.dumps(result_data.get("final_synthesized_decision", {})),
        ai_evidence_json=json.dumps(result_data.get("ai_evidence", [])),
        justification_json=json.dumps(result_data.get("justification", [])),
        rank_position=result_data.get("rank_position"),
        hr_decision=hr_decision,
        hr_notes=hr_notes
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result

def update_screening_hr_decision(db: Session, candidate_id: int, jd_id: int, decision: str, notes: Optional[str] = None):
    db_result = get_screening_result(db, candidate_id, jd_id)
    if db_result:
        db_result.hr_decision = decision
        if notes is not None:
            db_result.hr_notes = notes
        db.commit()
        db.refresh(db_result)
    return db_result

def delete_screening_result(db: Session, candidate_id: int, jd_id: int):
    result = get_screening_result(db, candidate_id, jd_id)
    if result:
        db.delete(result)
        db.commit()
        return True
    return False

# --- Interview Session Repositories ---
def create_interview_session(db: Session, candidate_id: int, session_id: str, job_id: Optional[int] = None):
    db_session = InterviewSession(
        candidate_id=candidate_id,
        session_id=session_id,
        job_id=job_id,
        status="pending",
        questions_json=json.dumps([]),
        answers_json=json.dumps([]),
        followups_json=json.dumps([]),
        transcript_summary="",
        final_scores_json=json.dumps({}),
        current_question_index=0
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_interview_session(db: Session, session_id: str):
    return db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()

def get_active_interview_session_by_candidate(db: Session, candidate_id: int):
    return db.query(InterviewSession).filter(
        InterviewSession.candidate_id == candidate_id,
        InterviewSession.status != "completed"
    ).order_by(InterviewSession.created_at.desc()).first()

def update_interview_progress(db: Session, session_id: str, progress_data: dict):
    db_session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if db_session:
        if "questions" in progress_data:
            db_session.questions_json = json.dumps(progress_data["questions"])
        if "answers" in progress_data:
            db_session.answers_json = json.dumps(progress_data["answers"])
        if "followups" in progress_data:
            db_session.followups_json = json.dumps(progress_data["followups"])
        if "summary" in progress_data:
            db_session.transcript_summary = progress_data["summary"]
        if "scores" in progress_data:
            db_session.final_scores_json = json.dumps(progress_data["scores"])
        if "current_index" in progress_data:
            db_session.current_question_index = progress_data["current_index"]
        if "status" in progress_data:
            db_session.status = progress_data["status"]
            
        db.commit()
        db.refresh(db_session)
    return db_session

def finalize_interview_session(db: Session, session_id: str, final_data: dict):
    db_session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if db_session:
        db_session.status = "completed"
        db_session.interview_score = final_data.get("overall_score")
        db_session.final_scores_json = json.dumps(final_data.get("scores", {}))
        db_session.recommendation = final_data.get("recommendation")
        db_session.completed_at = func.now()
        db.commit()
        db.refresh(db_session)
    return db_session
