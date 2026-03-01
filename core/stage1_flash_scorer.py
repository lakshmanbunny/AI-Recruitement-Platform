"""
Stage 1: Single-Pass Flash Scorer
Eliminates the embedding "Double Tax" by using Gemini 2.0 Flash to simultaneously
read the pre-extracted resume JSON and the Job Description, producing:
  1. coverage_score (0-100): How well do they meet core JD requirements?
  2. similarity_score (0-100): How exact is their tech stack/experience match?
  3. base_score: Average of coverage + similarity
  4. stage_1_justification: A strict 1-sentence explanation
  5. hiring_justification: Grounded bullet-point evaluation
"""
import json
from typing import Dict, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable
from core.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class Stage1FlashScorer:
    """
    Uses Gemini 2.0 Flash to score a candidate's resume against a JD in a single pass.
    No embeddings, no chunking, no vector DB.
    """
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.1,
            convert_system_message_to_human=True
        )

    @traceable(name="Stage 1 Flash Scorer")
    def score_candidate(
        self,
        candidate_id: str,
        resume_json: str,
        job_description: str,
    ) -> Dict[str, Any]:
        """
        Single-pass extraction + scoring.
        Takes the raw_resume_text JSON and the JD, returns structured scores + justification.
        """
        system_prompt = """You are an enterprise-grade AI recruitment screening system.
Your task: Evaluate a candidate's resume against a Job Description in a single pass.

You MUST be strict, objective, and evidence-based. Do NOT inflate scores.

SCORING RUBRIC:
- coverage_score (0-100): What percentage of the JD's CORE requirements does this candidate meet?
  0-30: Minimal match, missing most requirements
  30-60: Partial match, meets some but has significant gaps
  60-80: Good match, meets most requirements with minor gaps
  80-100: Excellent match, meets virtually all requirements

- similarity_score (0-100): How closely does their tech stack and experience EXACTLY match what the JD asks for?
  0-30: Different tech stack, different domain
  30-60: Some overlap but significant differences
  60-80: Strong overlap with minor differences
  80-100: Near-exact match in stack and experience

EVALUATION RULES:
1. Base your scores ONLY on evidence found in the resume.
2. Do NOT assume skills that are not explicitly mentioned.
3. Be conservative — a student with coursework is NOT the same as production experience.
4. Provide grounded justification bullets with specific evidence from the resume.
5. Each justification bullet MUST include a citation tag in square brackets at the END indicating which resume section the evidence comes from.

CITATION TAGS (use these exact tags):
  [resume-summary] — from professional summary/objective
  [resume-skills] — from technical skills section
  [resume-projects] — from projects section
  [resume-experience] — from work experience/internships
  [resume-education] — from education section
  [resume-certifications] — from certifications section
  [resume-missing] — when a JD requirement is NOT found anywhere in the resume

RESPONSE FORMAT (STRICT JSON — no markdown, no code blocks):
{
  "stage_1_scores": {
    "coverage_score": <float 0-100>,
    "similarity_score": <float 0-100>,
    "base_score": <float 0-100, average of coverage + similarity>
  },
  "stage_1_justification": "<1 strict sentence explaining the scores>",
  "hiring_justification": [
    "✔ <strength with evidence from resume> [resume-section]",
    "⚠ <gap or concern with specifics> [resume-section]",
    "🔴 <critical missing requirement> [resume-missing]"
  ],
  "extracted_skills": ["skill1", "skill2", ...],
  "experience_level": "<Fresher/Junior/Mid/Senior>",
  "domain_match": "<Strong/Moderate/Weak/None>"
}"""

        user_message = f"""CANDIDATE ID: {candidate_id}

JOB DESCRIPTION:
{job_description}

CANDIDATE RESUME (Extracted JSON):
{resume_json}

Evaluate this candidate against the JD. Return ONLY valid JSON."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]

        try:
            logger.info(f"[STAGE 1] Scoring candidate {candidate_id} with Flash")
            response = self.llm.invoke(messages)
            content = response.content.strip()

            # Strip markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)

            # Ensure base_score is computed correctly
            scores = result.get("stage_1_scores", {})
            coverage = float(scores.get("coverage_score", 0))
            similarity = float(scores.get("similarity_score", 0))
            base_score = round((coverage + similarity) / 2, 2)
            scores["base_score"] = base_score
            result["stage_1_scores"] = scores

            logger.info(
                f"[STAGE 1] {candidate_id}: "
                f"Coverage={coverage:.1f} Similarity={similarity:.1f} "
                f"Base={base_score:.1f}"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f"[STAGE 1] JSON parse failed for {candidate_id}: {e}")
            logger.error(f"[STAGE 1] Raw response: {content[:500]}")
            return self._error_result(candidate_id, f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"[STAGE 1] Flash scoring failed for {candidate_id}: {e}")
            return self._error_result(candidate_id, str(e))

    async def score_candidate_async(
        self,
        candidate_id: str,
        resume_json: str,
        job_description: str,
    ) -> Dict[str, Any]:
        """Async wrapper for concurrent batch processing."""
        import asyncio
        return await asyncio.to_thread(
            self.score_candidate, candidate_id, resume_json, job_description
        )

    def _error_result(self, candidate_id: str, error: str) -> Dict[str, Any]:
        """Returns a safe fallback result on error."""
        return {
            "stage_1_scores": {
                "coverage_score": 0.0,
                "similarity_score": 0.0,
                "base_score": 0.0
            },
            "stage_1_justification": f"Scoring failed: {error}",
            "hiring_justification": [f"🔴 Evaluation error: {error}"],
            "extracted_skills": [],
            "experience_level": "Unknown",
            "domain_match": "None",
            "error": error
        }
