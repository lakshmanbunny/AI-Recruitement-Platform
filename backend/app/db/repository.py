from sqlalchemy.orm import Session
from . import models
from .models import Candidate, JobDescription, ScreeningResult, InterviewSession, RAGMetric, RAGEvaluationResult, RAGEvaluationJob
import json
from typing import List, Optional, Dict

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

def get_candidate_by_fuzzy_id(db: Session, identifier: str):
    """
    Robustly finds a candidate by ID, full email, or roll number/email prefix.
    """
    if not identifier:
        return None
        
    identifier_str = str(identifier).strip()
    
    # 1. Try by Integer ID
    if identifier_str.isdigit():
        cand = get_candidate(db, int(identifier_str))
        if cand: return cand
        
    # 2. Try by Full Email
    cand = get_candidate_by_email(db, identifier_str.lower())
    if cand: return cand
    
    # 3. Try by Email Prefix (Roll Number)
    # Most candidates in our DB have email as roll_number@domain.com
    prefix = identifier_str.split('@')[0].lower()
    cand = db.query(Candidate).filter(Candidate.email.like(f"{prefix}%")).first()
    if cand: return cand
    
    # 4. Try by Woxsen Roll Number
    from .models import WoxsenCandidate
    wc = db.query(WoxsenCandidate).filter(WoxsenCandidate.roll_number.ilike(identifier_str)).first()
    if not wc:
        # Try partial roll number match
        wc = db.query(WoxsenCandidate).filter(WoxsenCandidate.roll_number.ilike(f"%{identifier_str}%")).first()
    
    if wc:
        cand = get_candidate_by_email(db, wc.email)
        if cand: return cand
    
    # 5. Try by Name Case-Insensitive (Fallback)
    cand = db.query(Candidate).filter(Candidate.name.ilike(f"%{identifier_str}%")).first()
    
    return cand

def list_candidates(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Candidate).offset(skip).limit(limit).all()

def list_woxsen_candidates(db: Session):
    return db.query(models.WoxsenCandidate).all()

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

def get_latest_screening_result(db: Session, candidate_id: int):
    return db.query(ScreeningResult).filter(ScreeningResult.candidate_id == candidate_id).order_by(ScreeningResult.evaluated_at.desc()).first()

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
        judge_audit_json=json.dumps(result_data.get("judge_audit", {})),
        rubric_scores_json=json.dumps(result_data.get("rubric_scores", {})),
        rank_position=result_data.get("rank_position"),
        
        # New RAG Metadata
        retrieval_mode=result_data.get("retrieval_mode", "llama_index"),
        retrieval_version=result_data.get("retrieval_version"),
        rag_enabled=result_data.get("rag_enabled", True),
        rag_status=result_data.get("rag_status", "healthy"),

        hr_decision=hr_decision,
        hr_notes=hr_notes
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result

def clear_stale_results(db: Session, current_version: str):
    """Deletes all screening results that don't match the current retrieval version."""
    stale = db.query(ScreeningResult).filter(ScreeningResult.retrieval_version != current_version).all()
    if stale:
        for result in stale:
            db.delete(result)
        db.commit()
        return len(stale)
    return 0

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

def save_rag_metrics(db: Session, candidate_id: int, screening_result_id: int, metrics: dict):
    """Saves RAG evaluation metrics for a screening run."""
    db_metrics = RAGMetric(
        candidate_id=candidate_id,
        screening_result_id=screening_result_id,
        retrieval_score=metrics.get("retrieval_score", 0.0),
        faithfulness_score=metrics.get("faithfulness_score", 0.0),
        coverage_score=metrics.get("coverage_score", 0.0),
        precision_score=metrics.get("precision_score", 0.0),
        recall_score=metrics.get("recall_score", metrics.get("recall", 0.0)),
        relevancy_score=metrics.get("relevancy_score", metrics.get("answer_relevancy", 0.0)),
        rag_health_status=metrics.get("rag_health_status", "CRITICAL")
    )
    db.add(db_metrics)
    db.commit()
    db.refresh(db_metrics)
    return db_metrics

def get_rag_metrics(db: Session, candidate_id: int):
    """Retrieves the latest RAG metrics for a candidate."""
    return db.query(RAGMetric).filter(RAGMetric.candidate_id == candidate_id)\
             .order_by(RAGMetric.evaluation_timestamp.desc()).first()

def update_rag_override(db: Session, screening_result_id: int, override_status: bool):
    """Updates the RAG override flag for a screening result."""
    result = db.query(ScreeningResult).filter(ScreeningResult.id == screening_result_id).first()
    if result:
        result.rag_override = override_status
        db.commit()
        db.refresh(result)
        return result
    return None


# --- RAGEvaluationResult Repositories ---

def get_rag_retrieval_metrics(db: Session, candidate_id: int):
    """Fetches the latest deterministic RAG retrieval metrics for a candidate."""
    from .models import RAGRetrievalMetric
    return db.query(RAGRetrievalMetric).filter(RAGRetrievalMetric.candidate_id == candidate_id).order_by(RAGRetrievalMetric.evaluated_at.desc()).first()

def list_all_rag_retrieval_metrics(db: Session):
    """Returns all RAGRetrievalMetric records joined to their Candidate, sorted by overall_score desc."""
    from .models import RAGRetrievalMetric
    return (
        db.query(RAGRetrievalMetric)
        .join(Candidate, RAGRetrievalMetric.candidate_id == Candidate.id)
        .order_by(RAGRetrievalMetric.overall_score.desc())
        .all()
    )

def save_rag_retrieval_metrics(db: Session, candidate_id: int, metrics: dict):
    """Persists deterministic zero-LLM retrieval metrics."""
    from .models import RAGRetrievalMetric
    
    # Remove older record to keep history clean/flat per candidate
    existing = db.query(RAGRetrievalMetric).filter(RAGRetrievalMetric.candidate_id == candidate_id).first()
    if existing:
        db.delete(existing)
        db.commit()
        
    db_metrics = RAGRetrievalMetric(
        candidate_id=candidate_id,
        precision=metrics.get('precision', 0.0),
        recall=metrics.get('recall', 0.0),
        coverage=metrics.get('coverage', 0.0),
        similarity=metrics.get('similarity', 0.0),
        diversity=metrics.get('diversity', 0.0),
        density=metrics.get('density', 0.0),
        overall_score=metrics.get('overall_score', 0.0),
        rag_health_status=metrics.get('rag_health_status', 'CRITICAL')
    )
    
    db.add(db_metrics)
    db.commit()
    db.refresh(db_metrics)
    return db_metrics

def save_rag_evaluation_result(db: Session, candidate_id: int, metrics_result):
    """Persists a full RAGAS evaluation result for a candidate."""
    # Delete previous result for same candidate if exists
    existing = db.query(RAGEvaluationResult).filter(
        RAGEvaluationResult.candidate_id == candidate_id
    ).first()
    if existing:
        db.delete(existing)
        db.commit()

    if isinstance(metrics_result, dict):
        jd_hash = metrics_result.get('jd_hash')
        precision = metrics_result.get('precision', 0.0)
        recall = metrics_result.get('recall', 0.0)
        faithfulness = metrics_result.get('faithfulness', 0.0)
        relevancy = metrics_result.get('answer_relevancy', metrics_result.get('relevancy', 0.0))
        overall_score = metrics_result.get('overall_score', 0.0)
        
        health_status = metrics_result.get('rag_health_status', "CRITICAL")
        if hasattr(health_status, 'value'):
            health_status = health_status.value
            
        gate_decision = metrics_result.get('gate_decision', "BLOCK")
        if hasattr(gate_decision, 'value'):
            gate_decision = gate_decision.value
            
        failure_reasons_json = json.dumps(metrics_result.get('failure_reasons', []))
        gating_reason = metrics_result.get('gating_reason')
        override_triggered = metrics_result.get('override_triggered', False)
        override_reason = metrics_result.get('override_reason')
    else:
        jd_hash = getattr(metrics_result, 'jd_hash', None)
        precision = metrics_result.precision
        recall = metrics_result.recall
        faithfulness = metrics_result.faithfulness
        relevancy = metrics_result.answer_relevancy
        overall_score = metrics_result.overall_score
        health_status = metrics_result.rag_health_status if isinstance(metrics_result.rag_health_status, str) else metrics_result.rag_health_status.value
        gate_decision = metrics_result.gate_decision if isinstance(metrics_result.gate_decision, str) else metrics_result.gate_decision.value
        failure_reasons_json = json.dumps(metrics_result.failure_reasons)
        gating_reason = metrics_result.gating_reason
        override_triggered = metrics_result.override_triggered
        override_reason = metrics_result.override_reason

    db_result = RAGEvaluationResult(
        candidate_id=candidate_id,
        jd_hash=jd_hash,
        precision=precision,
        recall=recall,
        faithfulness=faithfulness,
        relevancy=relevancy,
        overall_score=overall_score,
        health_status=health_status,
        gate_decision=gate_decision,
        failure_reasons_json=failure_reasons_json,
        gating_reason=gating_reason,
        override_triggered=override_triggered,
        override_reason=override_reason,
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result


def get_rag_evaluation_by_candidate(db: Session, candidate_id: int) -> Optional[RAGEvaluationResult]:
    """Gets the latest RAGAS evaluation result for a candidate."""
    return db.query(RAGEvaluationResult).filter(
        RAGEvaluationResult.candidate_id == candidate_id
    ).order_by(RAGEvaluationResult.timestamp.desc()).first()


def log_rag_override(db: Session, candidate_id: int, override_reason: str) -> Optional[RAGEvaluationResult]:
    """Logs an HR override action on a candidate's RAG evaluation result."""
    result = get_rag_evaluation_by_candidate(db, candidate_id)
    if result:
        result.override_triggered = True
        result.override_reason = override_reason
        result.gate_decision = "ALLOW"
        db.commit()
        db.refresh(result)
    return result

# --- RAGEvaluationJob Repositories ---

def create_rag_evaluation_job(db: Session, candidate_id: int) -> RAGEvaluationJob:
    """Creates a new PENDING evaluation job in the queue."""
    # Delete any existing pending/failed jobs for this candidate to avoid duplicates
    existing_jobs = db.query(RAGEvaluationJob).filter(
        RAGEvaluationJob.candidate_id == candidate_id,
        RAGEvaluationJob.status.in_(["PENDING", "FAILED"])
    ).all()
    for job in existing_jobs:
        db.delete(job)
    db.commit()

    db_job = RAGEvaluationJob(
        candidate_id=candidate_id,
        status="PENDING"
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

def get_rag_evaluation_job(db: Session, job_id: int) -> Optional[RAGEvaluationJob]:
    """Retrieves a specific evaluation job by ID."""
    return db.query(RAGEvaluationJob).filter(RAGEvaluationJob.id == job_id).first()

def get_latest_rag_evaluation_job(db: Session, candidate_id: int) -> Optional[RAGEvaluationJob]:
    """Gets the most recently created evaluation job for a candidate."""
    return db.query(RAGEvaluationJob).filter(
        RAGEvaluationJob.candidate_id == candidate_id
    ).order_by(RAGEvaluationJob.created_at.desc()).first()

def get_pending_rag_evaluation_jobs(db: Session, limit: int = 1) -> List[RAGEvaluationJob]:
    """Retrieves a list of PENDING evaluation jobs for the worker to pick up."""
    return db.query(RAGEvaluationJob).filter(
        RAGEvaluationJob.status == "PENDING"
    ).limit(limit).all()

def update_rag_evaluation_job_status(
    db: Session,
    job_id: int,
    status: str,
    metrics_json: Optional[str] = None,
    error_message: Optional[str] = None
) -> Optional[RAGEvaluationJob]:
    """Updates the status and optional metrics/errors for an evaluation job."""
    from sqlalchemy.sql import func
    
    db_job = get_rag_evaluation_job(db, job_id)
    if db_job:
        db_job.status = status
        if metrics_json is not None:
            db_job.metrics_json = metrics_json
        if error_message is not None:
            db_job.error_message = error_message
            
        db.commit()
        db.refresh(db_job)
    return db_job

# --- RAGLLMMetric Repositories ---

def save_rag_llm_metrics(db: Session, candidate_id: int, metrics_data: dict) -> 'RAGLLMMetric':
    from .models import RAGLLMMetric
    
    existing = get_rag_llm_metrics(db, candidate_id)
    if existing:
        db.delete(existing)
        db.commit()

    db_metric = RAGLLMMetric(
        candidate_id=candidate_id,
        faithfulness=metrics_data.get("faithfulness", 0.0),
        answer_relevance=metrics_data.get("answer_relevance", 0.0),
        hallucination_score=metrics_data.get("hallucination_score", 0.0),
        context_utilization=metrics_data.get("context_utilization", 0.0),
        overall_score=metrics_data.get("overall_score", 0.0),
        rag_health_status=metrics_data.get("rag_health_status", "CRITICAL"),
        explanation=metrics_data.get("explanation", None)
    )
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric

def get_rag_llm_metrics(db: Session, candidate_id: int) -> Optional['RAGLLMMetric']:
    from .models import RAGLLMMetric
    return db.query(RAGLLMMetric).filter(RAGLLMMetric.candidate_id == candidate_id).first()


# --- RAGLLMEvalJob Repositories ---

def create_llm_eval_job(db: Session, candidate_id: int, evaluation_weights: Optional[Dict[str, float]] = None) -> 'RAGLLMEvalJob':
    from .models import RAGLLMEvalJob
    import json
    
    # Delete any existing pending/failed jobs for this candidate to avoid duplicates
    existing_jobs = db.query(RAGLLMEvalJob).filter(
        RAGLLMEvalJob.candidate_id == candidate_id,
        RAGLLMEvalJob.status.in_(["PENDING", "FAILED"])
    ).all()
    for job in existing_jobs:
        db.delete(job)
    db.commit()

    db_job = RAGLLMEvalJob(
        candidate_id=candidate_id,
        status="PENDING",
        evaluation_weights_json=json.dumps(evaluation_weights) if evaluation_weights else None
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

def get_pending_llm_job(db: Session) -> Optional['RAGLLMEvalJob']:
    from .models import RAGLLMEvalJob
    return db.query(RAGLLMEvalJob).filter(RAGLLMEvalJob.status == "PENDING").first()

def get_llm_eval_job_by_candidate(db: Session, candidate_id: int) -> Optional['RAGLLMEvalJob']:
    from .models import RAGLLMEvalJob
    return db.query(RAGLLMEvalJob).filter(
        RAGLLMEvalJob.candidate_id == candidate_id
    ).order_by(RAGLLMEvalJob.created_at.desc()).first()

def update_llm_job_status(db: Session, job_id: int, status: str, metrics_json: Optional[str] = None, error_message: Optional[str] = None) -> Optional['RAGLLMEvalJob']:
    from sqlalchemy.sql import func
    from .models import RAGLLMEvalJob
    
    db_job = db.query(RAGLLMEvalJob).filter(RAGLLMEvalJob.id == job_id).first()
    if db_job:
        db_job.status = status
        if metrics_json is not None:
            db_job.metrics_json = metrics_json
        if error_message is not None:
            db_job.error_message = error_message
            
        if status in ["COMPLETED", "FAILED"]:
            db_job.completed_at = func.now()
            
        db.commit()
        db.refresh(db_job)
    return db_job
