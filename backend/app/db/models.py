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

    rank_position = Column(Integer, nullable=True)
    hr_decision = Column(String, nullable=True) # APPROVED, REJECTED, ON_HOLD
    hr_notes = Column(Text, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())

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
