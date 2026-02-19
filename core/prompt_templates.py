def get_candidate_evaluation_prompt(jd: str, resume: str) -> str:
    """
    Generates a structured prompt for Gemini to evaluate a candidate against a job description.
    """
    return f"""
You are an expert technical recruiter and hiring manager.
Your task is to evaluate the provided resume against the job description using the following hiring rubric.

HIRING RUBRIC:
1. Technical Skill Match (0-10): How well do the candidate's skills align with the requirements?
2. Experience Relevance (0-10): Is the candidate's professional background suitable for the role?
3. Project Impact (0-10): Does the candidate demonstrate tangible results and complexity in their projects?
4. Leadership/Seniority (0-10): Does the candidate show the expected level of leadership or seniority?

SCORING:
Calculate an "overall_score" from 0 to 100 based on the rubric.

RESPONSE FORMAT:
You MUST return a STRICT JSON object with these exact keys:
{{
    "technical_score": int,
    "experience_score": int,
    "project_score": int,
    "leadership_score": int,
    "overall_score": int,
    "summary": "a concise, maximum 2-sentence explanation of the candidate's fit"
}}

JOB DESCRIPTION:
{jd}

CANDIDATE RESUME:
{resume}

JSON response:
"""
