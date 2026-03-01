from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import json
import hashlib

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    github_url = Column(String)
    linkedin_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class WoxsenCandidate(Base):
    __tablename__ = "woxsen_candidates"

    id = Column(Integer, primary_key=True, index=True)
    roll_number = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    github_url = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    resume_file_path = Column(String, nullable=True)
    raw_resume_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    jd_text = Column(Text)
    jd_hash = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    @staticmethod
    def generate_hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

class ScreeningResult(Base):
    __tablename__ = "screening_results"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    jd_id = Column(Integer, ForeignKey("job_descriptions.id"))

    candidate = relationship("Candidate", backref="screening_results")
    job_description = relationship("JobDescription", backref="screening_results")

    resume_score = Column(Float)
    github_score = Column(Float)
    overall_score = Column(Float)

    risk_level = Column(String)
    readiness_level = Column(String)
    recommendation = Column(Text)

    # Deep Persistence for Candidates
    repo_count = Column(Integer, default=0)
    ai_projects = Column(Integer, default=0)
    
    # JSON fields stored as TEXT
    skill_gaps_json = Column(Text)
    interview_focus_json = Column(Text)
    github_features_json = Column(Text)
    repos_json = Column(Text) # List[RepoItem]
    interview_readiness_json = Column(Text) # InterviewReadinessReport
    skeptic_analysis_json = Column(Text) # SkepticAnalysis
    final_synthesized_decision_json = Column(Text) # FinalSynthesizedDecision
    ai_evidence_json = Column(Text) # Transparency layer
    justification_json = Column(Text) # Bullet points
    judge_audit_json = Column(Text) # Judge audit details
    rubric_scores_json = Column(Text) # Detailed rubric breakdown

    rank_position = Column(Integer, nullable=True)
    
    # RAG Gating & Cache Metadata
    retrieval_mode = Column(String, nullable=True) # e.g., "llama_index", "hybrid"
    retrieval_version = Column(String, nullable=True) # e.g., "v1.0.1"
    rag_enabled = Column(Boolean, default=True)
    rag_status = Column(String, default="healthy") # healthy, failed, disabled
    rag_override = Column(Boolean, default=False)

    hr_decision = Column(String, nullable=True) # APPROVED, REJECTED, ON_HOLD
    hr_notes = Column(Text, nullable=True)
    
    # Phase 8: Interview Trigger Flow & HITL
    interview_status = Column(String, default="PENDING")  # PENDING, APPROVED, INTERVIEW_SENT, INTERVIEW_COMPLETED
    evaluation_locked = Column(Boolean, default=False)
    interview_session_id = Column(String, nullable=True)
    interview_invite_sent = Column(Boolean, default=False)
    
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())

class RAGMetric(Base):
    __tablename__ = "rag_metrics"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    screening_result_id = Column(Integer, ForeignKey("screening_results.id"))
    
    retrieval_score = Column(Float)
    faithfulness_score = Column(Float)
    coverage_score = Column(Float)
    precision_score = Column(Float)
    recall_score = Column(Float, nullable=True)
    relevancy_score = Column(Float, nullable=True)
    rag_health_status = Column(String) # HEALTHY, WARNING, CRITICAL
    
    evaluation_timestamp = Column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate")
    screening_result = relationship("ScreeningResult")


class RAGRetrievalMetric(Base):
    """
    Deterministic Zero-LLM Retrieval Quality Evaluation metrics.
    """
    __tablename__ = "rag_retrieval_metrics"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), index=True)
    
    precision = Column(Float, default=0.0)
    recall = Column(Float, default=0.0)
    coverage = Column(Float, default=0.0)
    similarity = Column(Float, default=0.0)
    diversity = Column(Float, default=0.0)
    density = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)
    
    rag_health_status = Column(String, default="CRITICAL") # HEALTHY, WARNING, CRITICAL
    
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate")

class RAGEvaluationResult(Base):
    """
    Full RAGAS evaluation result for a candidate in a given screening run.
    """
    __tablename__ = "rag_evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    jd_hash = Column(String, nullable=True, index=True)

    # RAGAS Metrics
    precision = Column(Float, default=0.0)
    recall = Column(Float, default=0.0)
    faithfulness = Column(Float, default=0.0)
    relevancy = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)

    # Health & Gate
    health_status = Column(String, default="CRITICAL")  # HEALTHY, WARNING, CRITICAL
    gate_decision = Column(String, default="BLOCK")     # ALLOW, WARN, BLOCK
    failure_reasons_json = Column(Text, nullable=True)
    gating_reason = Column(Text, nullable=True)

    # Override tracking
    override_triggered = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate")

class RAGEvaluationJob(Base):
    """
    Queue for RAGAS evaluation background processing.
    """
    __tablename__ = "rag_evaluation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), index=True)
    status = Column(String, default="PENDING") # PENDING, RUNNING, COMPLETED, FAILED
    
    metrics_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    candidate = relationship("Candidate")

class RAGLLMMetric(Base):
    """
    Post-LLM RAG evaluation metrics generated by the Enterprise Judge.
    """
    __tablename__ = "rag_llm_metrics"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), index=True)
    
    faithfulness = Column(Float, default=0.0)
    answer_relevance = Column(Float, default=0.0)
    hallucination_score = Column(Float, default=0.0)
    context_utilization = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)
    
    rag_health_status = Column(String, default="CRITICAL") # GOOD, WARN, CRITICAL
    explanation = Column(Text, nullable=True)
    
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate")

class RAGLLMEvalJob(Base):
    """
    Queue for Post-LLM RAG evaluation background processing.
    """
    __tablename__ = "rag_llm_eval_jobs"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), index=True)
    status = Column(String, default="PENDING") # PENDING, RUNNING, COMPLETED, FAILED
    metrics_json = Column(Text, nullable=True)
    evaluation_weights_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    candidate = relationship("Candidate")

class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    job_id = Column(Integer, ForeignKey("job_descriptions.id"), nullable=True)
    
    session_id = Column(String, unique=True, index=True)
    status = Column(String, default="pending") # pending, active, completed, failed

    # JSON state management
    questions_json = Column(Text) # Pre-generated questions
    answers_json = Column(Text) # Transcript of answers
    followups_json = Column(Text) # Track follow-up questions
    transcript_summary = Column(Text) # Optimized memory summary
    final_scores_json = Column(Text) # Score details per dimension

    current_question_index = Column(Integer, default=0)
    interview_score = Column(Float, nullable=True) # Aggregated score

    final_score = Column(Float, nullable=True) # Legacy support / redundant
    recommendation = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
