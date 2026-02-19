from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class RankingItem(BaseModel):
    rank: int
    candidate_id: str
    name: str
    score: float
    github_url: Optional[str] = None

class InterviewReadinessReport(BaseModel):
    hire_readiness_level: Optional[str] = "MEDIUM"
    confidence_score: Optional[int] = 0
    risk_factors: List[str] = []
    skill_gaps: List[str] = []
    interview_focus_areas: List[str] = []
    final_hiring_recommendation: Optional[str] = "N/A"
    executive_summary: List[str] = []

class SkepticAnalysis(BaseModel):
    risk_level: Optional[str] = "LOW"
    major_concerns: List[str] = []
    hidden_risks: List[str] = []
    critical_skill_gaps: List[str] = []
    skeptic_recommendation: List[str] = []

class FinalSynthesizedDecision(BaseModel):
    final_decision: Optional[str] = "PROCEED WITH CAUTION"
    candidate_classification: Optional[str] = "N/A"
    decision_reasoning: List[str] = []
    hitl_status: str = "PENDING_HR_REVIEW"

class HRDecisionRequest(BaseModel):
    candidate_id: str
    decision: str  # APPROVE / REJECT / HOLD
    notes: Optional[str] = None

class RepoItem(BaseModel):
    name: str
    url: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    stars: int = 0
    ai_relevance_tag: Optional[str] = None

class CandidateEvaluation(BaseModel):
    overall_score: int = 0
    resume_score: int = 0
    github_score: int = 0
    repo_count: int = 0
    ai_projects: int = 0
    justification: List[str] = []
    repos: List[RepoItem] = []
    interview_readiness: Optional[InterviewReadinessReport] = None
    skeptic_analysis: Optional[SkepticAnalysis] = None
    final_decision: Optional[str] = None
    final_synthesized_decision: Optional[FinalSynthesizedDecision] = None
    hr_decision: Optional[Dict[str, Any]] = None
    ai_evidence: List[Dict[str, Any]] = []

class ScreeningResponse(BaseModel):
    ranking: List[RankingItem]
    evaluations: Dict[str, CandidateEvaluation]
