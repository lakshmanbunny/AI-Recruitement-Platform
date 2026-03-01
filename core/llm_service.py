import json
import re
import os
from typing import Dict, List, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable
from core.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)

class LLMService:
    """
    Enterprise-grade LLM Service with LangSmith observability and LangChain integration.
    """
    def __init__(self):
        # Generator: Gemini 2.0 Pro Experimental
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.2,
            convert_system_message_to_human=True
        )
        # Judge: Gemini 1.5 Pro
        self.judge_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.1,
            convert_system_message_to_human=True
        )

    @traceable(name="AI Judge Auditor")
    def _audit_evaluation(
        self, 
        candidate_id: str,
        jd_text: str,
        evaluation_data: Dict[str, Any],
        resume_chunks: str,
        github_chunks: str,
        agent_type: str = "Candidate Evaluation"
    ) -> Dict[str, Any]:
        """
        Generic LLM-as-a-judge auditor to verify faithfulness, relevance, 
        and groundedness of ANY evaluation.
        """
        try:
            logger.info(f"Invoking Enterprise LLM Judge (Gemini 2.5 Pro) for audit of {agent_type} - {candidate_id}")
            
            audit_system_prompt = f"""You are a senior hiring auditor. 
Audit the following {agent_type} for accuracy, fairness, and groundedness.
Your goal is to ensure the evaluation is objective, grounded in the provided evidence, and free of hallucinations.

Evaluate the following metrics (0.0 to 1.0):
1. Faithfulness: Does the evaluation accurately reflect the provided chunks?
2. Answer Relevance: Is the evaluation relevant to the Job Description?
3. Hallucination: Are there any claims made that are NOT in the evidence? (1.0 = No hallucinations)
4. Context Utilization: How well did the agent use the provided chunks?

Return a structured JSON response."""

            audit_user_message = f"""
CANDIDATE: {candidate_id}
JOB DESCRIPTION:
{jd_text}

EVALUATION TO AUDIT:
{json.dumps(evaluation_data, indent=2)}

EVIDENCE (RESUME):
{resume_chunks}

EVIDENCE (GITHUB):
{github_chunks}

AUDIT INSTRUCTIONS:
1. Cross-reference the evaluation against the EVIDENCE.
2. Verify that any citations or claims align with the actual chunk text.
3. Assign scores (0.0 - 1.0) for Faithfulness, Relevance, Hallucination, and Context Utilization.
4. Decide if the evaluation is "APPROVED" or needs to be "REVISED".

STRICT RESPONSE FORMAT (JSON):
{{
    "judge_verdict": "APPROVED / REVISED",
    "audit_reasoning": "Explain your findings.",
    "faithfulness": float (0.0-1.0),
    "answer_relevance": float (0.0-1.0),
    "hallucination_score": float (0.0-1.0),
    "context_utilization": float (0.0-1.0),
    "corrected_rubric_scores": {{ ... only if REVISED ... }},
    "corrected_overall_score": float (0-100),
    "corrected_justification": [ "audited bullets" ],
    "confidence_in_audit": int (0-100)
}}
"""
            
            messages = [
                SystemMessage(content=audit_system_prompt),
                HumanMessage(content=audit_user_message)
            ]
            
            audit_response = self.judge_llm.invoke(messages)
            audit_content = audit_response.content
            
            if "```json" in audit_content:
                audit_content = audit_content.split("```json")[1].split("```")[0].strip()
            elif "```" in audit_content:
                audit_content = audit_content.split("```")[1].split("```")[0].strip()
            
            audit_res = json.loads(audit_content)
            return audit_res
        except Exception as e:
            logger.error(f"LLM Judge Audit failed for {candidate_id}: {e}")
            return {"judge_verdict": "ERROR", "reasoning": str(e), "faithfulness": 0.0, "hallucination_score": 0.0}

    @traceable(name="Unified Candidate Evaluation")
    def unified_candidate_evaluation(
        self, 
        candidate_id: str,
        jd_text: str, 
        resume_summary: str,
        github_username: str,
        github_features: Dict[str, Any],
        evidence: List[Dict],
        resume_rag_evidence: Optional[Dict[str, Any]] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Enterprise-grade grounded evaluation using Top-K evidence, citations, and dynamic weights.
        """
        # 1. Default Weights if not provided
        if not weights:
            weights = {
                "technical_skills": 0.30,
                "experience_relevance": 0.20,
                "project_impact": 0.20,
                "github_strength": 0.20,
                "evidence_reliability": 0.10
            }
        
        # 2. EVIDENCE PREPROCESSING (Part 2 & 2.3)
        # Process Resume Chunks
        resume_raw = resume_rag_evidence.get("raw_chunks", []) if resume_rag_evidence else []
        # Lowered threshold to ensure dense keyword chunks (like Skills) aren't discarded
        resume_filtered = [c for c in resume_raw if c.get("score", 0) >= 0.0]
        resume_filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
        # REMOVED LIMITS: Passing all relevant chunks to Pro models
        top_resume = resume_filtered
        
        # Process GitHub Chunks
        github_filtered = [c for c in (evidence or []) if c.get("score", 0) >= 0.0]
        github_filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
        # REMOVED LIMITS: Passing all relevant chunks to Pro models
        top_github = github_filtered
        
        # Trace logs (Part 5)
        logger.info(f"[TRACE] Resume chunks selected: {len(top_resume)}")
        logger.info(f"[TRACE] GitHub chunks selected: {len(top_github)}")
        
    def format_context_chunks(self, top_resume: List[Dict], top_github: List[Dict]) -> Dict[str, str]:
        """
        Consistently formats resume and github chunks for LLM consumption.
        """
        resume_chunks_str = ""
        for i, chunk in enumerate(top_resume, 1):
            resume_chunks_str += f"[RESUME_CHUNK_ID: R{i}]\nSection: {chunk.get('section', 'Unknown').capitalize()}\nContent: {chunk.get('text', '')}\n\n"
        
        if not resume_chunks_str:
            resume_chunks_str = "No high-relevance resume evidence retrieved."

        github_chunks_str = ""
        for i, chunk in enumerate(top_github, 1):
            github_chunks_str += f"[GITHUB_CHUNK_ID: G{i}]\nRepo: {chunk.get('repo_name', 'Unknown')}\nContent: {chunk.get('chunk_text', '')}\n\n"
        
        if not github_chunks_str:
            github_chunks_str = "No high-relevance GitHub code evidence retrieved."
            
        return {
            "resume_chunks": resume_chunks_str,
            "github_chunks": github_chunks_str
        }

    @traceable(name="Unified Candidate Evaluation")
    def unified_candidate_evaluation(
        self, 
        candidate_id: str,
        jd_text: str, 
        resume_summary: str,
        github_username: str,
        github_features: Dict[str, Any],
        evidence: List[Dict],
        resume_rag_evidence: Optional[Dict[str, Any]] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Enterprise-grade grounded evaluation using Top-K evidence, citations, and dynamic weights.
        """
        # 1. Default Weights if not provided
        if not weights:
            weights = {
                "technical_skills": 0.30,
                "experience_relevance": 0.20,
                "project_impact": 0.20,
                "github_strength": 0.20,
                "evidence_reliability": 0.10
            }
        
        # 2. EVIDENCE PREPROCESSING
        resume_raw = resume_rag_evidence.get("raw_chunks", []) if resume_rag_evidence else []
        resume_filtered = [c for c in resume_raw if c.get("score", 0) >= 0.0]
        resume_filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_resume = resume_filtered
        
        github_filtered = [c for c in (evidence or []) if c.get("score", 0) >= 0.0]
        github_filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_github = github_filtered
        
        # 3. FORMAT CHUNKS WITH CITATIONS
        formatted = self.format_context_chunks(top_resume, top_github)
        resume_chunks_str = formatted["resume_chunks"]
        github_chunks_str = formatted["github_chunks"]

        # 4. LOAD PROMPTS FROM FILES (Part 4)
        try:
            curr_dir = os.path.dirname(__file__)
            with open(os.path.join(curr_dir, "prompts", "system_prompt_for_unified_candidate_eval.txt"), "r") as f:
                system_prompt = f.read()
            with open(os.path.join(curr_dir, "prompts", "unified_eval_user_template.txt"), "r") as f:
                user_template = f.read()
        except Exception as e:
            logger.error(f"Failed to load prompt templates: {e}")
            raise e

        # 5. CONSTRUCT INPUT PAYLOAD
        payload = {
            "job_description": jd_text,
            "weight_skills": weights.get("technical_skills", 0.3),
            "weight_experience": weights.get("experience_relevance", 0.2),
            "weight_projects": weights.get("project_impact", 0.2),
            "weight_github": weights.get("github_strength", 0.2),
            "weight_reliability": weights.get("evidence_reliability", 0.1),
            "resume_chunks": resume_chunks_str,
            "gh_activity": github_features.get('activity_score', 0),
            "gh_relevance": github_features.get('ai_relevance_score', 0),
            "gh_repo_count": github_features.get('repo_count', 0),
            "github_chunks": github_chunks_str
        }

        # LangSmith Trace Enhancement (Part 5)
        from core.utils.context_hasher import compute_context_hash
        generator_hash = compute_context_hash(resume_chunks_str + github_chunks_str)
        logger.info(f"[TRACE] Weight Configuration: {json.dumps(weights)}")
        logger.info(f"[TRACE] Generator context hash: {generator_hash}")

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_template)
        ])

        chain = prompt | self.llm

        # 6. INVOCATION WITH VALIDATION AND RETRY (Part 6)
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Invoking Enterprise Unified Intelligence Agent for {candidate_id} (Attempt {attempt})")
                response = chain.invoke(payload)
                
                # Parse JSON
                content = response.content
                # Strip potential markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                eval_data = json.loads(content)
                eval_data["generator_hash"] = generator_hash # Pass this out for DB / Worker usage if needed

                # --- PHASE 2: LLM JUDGE AUDIT ---
                audit_res = self._audit_evaluation(
                    candidate_id=candidate_id,
                    jd_text=jd_text,
                    evaluation_data=eval_data,
                    resume_chunks=resume_chunks_str,
                    github_chunks=github_chunks_str,
                    agent_type="Unified Evaluation"
                )
                
                # Merge Judge's revisions if any
                if audit_res.get("judge_verdict") == "REVISED":
                    logger.warning(f"LLM Judge REVISED evaluation for {candidate_id}: {audit_res.get('audit_reasoning')}")
                    eval_data["rubric_scores"] = audit_res.get("corrected_rubric_scores", eval_data.get("rubric_scores"))
                    eval_data["overall_score"] = audit_res.get("corrected_overall_score", eval_data.get("overall_score"))
                    eval_data["justification"] = audit_res.get("corrected_justification", eval_data.get("justification"))
                
                eval_data["judge_audit"] = {
                    "verdict": audit_res.get("judge_verdict", "APPROVED"),
                    "reasoning": audit_res.get("audit_reasoning", "Passed audit."),
                    "confidence": audit_res.get("confidence_in_audit", 100),
                    "faithfulness": audit_res.get("faithfulness", 1.0),
                    "relevance": audit_res.get("answer_relevance", 1.0),
                    "hallucination": audit_res.get("hallucination_score", 1.0),
                    "utility": audit_res.get("context_utilization", 1.0)
                }

                # Validation Logic
                issues = []
                # Check citations in justification
                for bullet in eval_data.get("justification", []):
                    if not re.search(r"\[[RG][0-9]+\]", bullet):
                        issues.append("Missing citation in justification bullet")
                
                if issues:
                    logger.warning(f"Validation failed for candidate {candidate_id}: {'; '.join(issues)}")
                    if attempt < max_attempts:
                        logger.info("Retrying evaluation...")
                        continue
                
                # Add transparency layer mapping for UI
                eval_data["ai_evidence"] = []
                for i, chunk in enumerate(top_resume, 1):
                    eval_data["ai_evidence"].append({
                        "source": f"Resume [R{i}]",
                        "section": chunk.get("section", "General"),
                        "snippet": chunk.get("text", "")
                    })
                for i, chunk in enumerate(top_github, 1):
                    eval_data["ai_evidence"].append({
                        "source": f"GitHub [G{i}]",
                        "repo": chunk.get("repo_name", "Unknown"),
                        "snippet": chunk.get("chunk_text", "")
                    })
                
                eval_data["resume_rag_evidence"] = resume_rag_evidence # Keep for fallback compatibility
                
                return eval_data

            except Exception as e:
                logger.error(f"LLM Call failed for {candidate_id}: {str(e)}")
                if attempt < max_attempts:
                    continue
                return {
                    "evaluation_blocked": False,
                    "error": str(e),
                    "overall_score": 0,
                    "justification": ["System error during evaluation."]
                }
        return {}

    @traceable(name="Interview Readiness Evaluation")
    def interview_readiness_evaluation(
        self, 
        candidate_id: str,
        jd_text: str,
        candidate_profile: Dict[str, Any],
        resume_chunks: str = "",
        github_chunks: str = ""
    ) -> Dict[str, Any]:
        """
        Final hiring intelligence layer to evaluate interview readiness.
        Strict enterprise gatekeeper calibration with LLM-as-a-judge audit.
        """
        system_message = """You are a strict senior technical recruiter for a top-tier AI company.
Your role is NOT to praise candidates.
Your job is to identify hiring risks and make conservative hiring decisions.

Follow these mandatory evaluation principles:
1. Assume the candidate is NOT hire-ready unless strong evidence proves otherwise.
2. Always prioritize risk detection over strengths.
3. No candidate is perfect — you MUST identify at least 2 skill gaps and at least 1 risk factor.
4. Confidence score must be conservative.
5. Focus on potential hiring risks: Lack of real-world deployment, shallow understanding, over-reliance on tutorials.

STRICT FORMATTING RULE: 
- Use ONLY concise bullet points.
- Return only structured JSON output."""
        
        user_message_template = """
        Evaluate candidate readiness based on the following holistic profile.
        
        CANDIDATE PROFILE:
        {profile}

        RESPONSE FORMAT (STRICT JSON):
        {{
            "hire_readiness_level": "str (HIGH/MEDIUM/LOW)",
            "confidence_score": int (0-100),
            "risk_factors": ["🔴 list of risk bullet points"],
            "skill_gaps": ["⚠ list of skill gap bullet points"],
            "interview_focus_areas": ["🔍 list of interview focus bullet points"],
            "final_hiring_recommendation": "str (Strong Hire / Hire / Borderline / Reject)",
            "executive_summary": ["✔ bulleted summaries"]
        }}
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_message_template)
        ])

        chain = prompt | self.llm

        logger.info(f"Invoking Strict Interview Readiness Agent for {candidate_id}")
        try:
            response = chain.invoke({
                "profile": json.dumps(candidate_profile, indent=2)
            })
            
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
            return result
        except Exception as e:
            logger.error(f"Interview readiness evaluation failed: {str(e)}")
            return {"hire_readiness_level": "LOW", "confidence_score": 0, "error": str(e)}

    @traceable(name="AI Skeptic Analysis")
    def skeptic_evaluation(
        self, 
        candidate_id: str,
        jd_text: str,
        candidate_context: Dict[str, Any], 
        gatekeeper_output: Dict[str, Any],
        resume_chunks: str = "",
        github_chunks: str = ""
    ) -> Dict[str, Any]:
        """
        Adversarial LLM agent to challenge hiring decisions with LLM-as-a-judge audit.
        """
        system_message = """You are a senior hiring risk auditor.
Your role is to challenge hiring decisions and identify reasons NOT to hire a candidate.
Focus on: Lack of real-world production experience, weak system design exposure, missing collaboration evidence.

STRICT FORMATTING RULE: 
- Use ONLY concise bullet points.
- Return only structured JSON output."""

        user_message_template = """
        Challenge the following hiring evaluation for this candidate.
        
        CANDIDATE CONTEXT:
        {context}
        
        GATEKEEPER EVALUATION:
        {gatekeeper}
        
        RESPONSE FORMAT (STRICT JSON):
        {{
            "risk_level": "HIGH / MEDIUM / LOW",
            "major_concerns": ["• Bulleted concerns"],
            "hidden_risks": ["• Bulleted hidden dangers"],
            "critical_skill_gaps": ["• Bulleted critical gaps"],
            "skeptic_recommendation": ["• Final warnings"]
        }}
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_message_template)
        ])

        chain = prompt | self.llm

        logger.info(f"Invoking AI Skeptic Agent for {candidate_id} audit")
        try:
            response = chain.invoke({
                "context": json.dumps(candidate_context, indent=2),
                "gatekeeper": json.dumps(gatekeeper_output, indent=2)
            })
            
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
            return result
        except Exception as e:
            logger.error(f"AI Skeptic analysis failed: {str(e)}")
            return {"risk_level": "MEDIUM", "error": str(e)}

    @traceable(name="Final Decision Synthesis")
    def synthesize_final_decision(
        self, 
        gatekeeper_output: Dict[str, Any], 
        skeptic_output: Dict[str, Any], 
        unified_scores: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Final authority agent to synthesize all AI opinions into one final decision.
        """
        system_message = """You are a senior hiring decision synthesizer.
Your job is to combine multiple AI agent opinions into a final hiring decision.

Inputs:
- Gatekeeper evaluation (Optimistic/Readiness focused)
- Skeptic analysis (Risk/Adversarial focused)
- Candidate intelligence scores (Raw technical metrics)

Follow these mandatory synthesis rules:
1. Contradiction Resolution: If Gatekeeper is HIGH but Skeptic is HIGH RISK, you must downgrade to HOLD or HIRE WITH CAUTION.
2. Classification: You MUST classify the candidate into one of these: STRONG HIRE, HIRE WITH CAUTION, PROCEED TO INTERVIEW, HOLD, REJECT.
3. Reasoning: Provide a logical explanation of how you resolved the differences between the agents.
5. Confidence: Provide a final confidence score for this synthesized decision.

STRICT FORMATTING RULE: 
- Decision reasoning must be an ARRAY of bullet points.
- No paragraphs.

Return only structured JSON output."""

        user_message_template = """
        Provide a final synthesized hiring decision based on these inputs.
        
        GATEKEEPER EVALUATION:
        {gatekeeper}
        
        SKEPTIC ANALYSIS:
        {skeptic}
        
        TECHNICAL SCORES:
        {scores}
        
        RESPONSE FORMAT (STRICT JSON):
        {{
            "final_decision": "Decision String (e.g., STRONG HIRE)",
            "decision_reasoning": ["✔ Bullet 1", "⚠ Bullet 2", "🔴 Bullet 3"],
            "risk_level": "Final risk assessment (LOW/MEDIUM/HIGH)",
            "confidence": int (0-100),
            "candidate_classification": "Brief classification tag",
            "hitl_status": "PENDING_HR_REVIEW"
        }}
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_message_template)
        ])

        chain = prompt | self.llm

        config = {
            "tags": ["stage:final_synthesis", "component:decision_agent"],
            "metadata": {
                "gatekeeper_readiness": gatekeeper_output.get("hire_readiness_level", "unknown"),
                "skeptic_risk": skeptic_output.get("risk_level", "unknown")
            }
        }

        logger.info("Synthesizing final recruitment decision")
        try:
            response = chain.invoke({
                "gatekeeper": json.dumps(gatekeeper_output, indent=2),
                "skeptic": json.dumps(skeptic_output, indent=2),
                "scores": json.dumps(unified_scores, indent=2)
            }, config=config)
            
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
            
            # Defensive check for list fields
            if "decision_reasoning" in result and isinstance(result["decision_reasoning"], str):
                result["decision_reasoning"] = [result["decision_reasoning"]]
            
            logger.info("Final hiring decision synthesized.")
            return result
        except Exception as e:
            logger.error(f"Decision synthesis failed: {str(e)}")
            return {
                "final_decision": "HOLD",
                "decision_reasoning": ["Decision synthesis error - manual review required."],
                "risk_level": "MEDIUM",
                "confidence": 50,
                "candidate_classification": "System Error"
            }

    @traceable(name="Generate Interview Questions")
    def generate_interview_questions(self, screening_intelligence: Dict[str, Any], jd_text: str) -> List[str]:
        """
        One-shot generation of 10 targeted interview questions.
        """
        system_message = "You are a Senior Technical Mock Interviewer designing a rigorous 10-question roadmap."
        
        user_message_template = """
        Generate 10 technical interview questions for a candidate based on their screening intelligence and the job description.

        CANDIDATE INTELLIGENCE:
        {intelligence}

        JOB DESCRIPTION:
        {jd}

        RULES:
        1. Question 1 MUST be: "Please introduce yourself, your background, and your most relevant technical experience."
        2. Questions 2-10 must be targeted and derived from:
           - Identified skill gaps
           - GitHub verification results (if available)
           - Resume strengths
           - Job description core requirements
        3. Ensure a mix of:
           - Foundational concepts
           - Deep technical probing
           - Practical scenario-based questions
           - System design / Architectural thinking
        4. Questions must be professional and challenging.
        
        RESPONSE FORMAT (STRICT JSON):
        {{
            "questions": ["List of 10 strings"]
        }}
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_message_template)
        ])

        chain = prompt | self.llm

        try:
            response = chain.invoke({
                "intelligence": json.dumps(screening_intelligence, indent=2),
                "jd": jd_text
            })
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            result = json.loads(content)
            return result.get("questions", [])[:10]
        except Exception as e:
            logger.error(f"Question generation failed: {str(e)}")
            return [
                "Please introduce yourself, your background, and your most relevant technical experience.",
                "Can you explain the core architecture of your most significant recent project?",
                "What are the most challenging technical obstacles you've encountered and how did you overcome them?",
                "How do you approach learning new technologies and staying current in the field?",
                "Can you discuss a time you had to optimize performance in a complex application?",
                "What is your philosophy on writing clean, maintainable code?",
                "How do you handle technical debt in a fast-paced development environment?",
                "Can you explain your experience with system design and architectural patterns?",
                "What do you consider to be the most important aspects of scaling a modern web application?",
                "Do you have any questions for us about the role or the team?"
            ]

    @traceable(name="Evaluate Interview Answer")
    def evaluate_interview_answer(
        self, 
        question: str, 
        answer: str, 
        transcript_summary: str,
        jd_text: str
    ) -> Dict[str, Any]:
        """
        Evaluates a single answer and decides adaptive behavior.
        """
        system_message = """You are an adaptive technical interviewer auditor.
Your job is to score a candidate's answer and decide if the AI interviewer should be Supportive or Strict.

ADAPTIVE RULES:
- If answer is weak/struggling: Suggest "SUPPORTIVE" mode (give hints, encourage).
- If answer is strong/confident: Suggest "STRICT" mode (ask deeper probing questions, challenge assumptions).

SCORING RULES:
- Score 0-10 based on depth, accuracy, and communication.
"""

        user_message_template = """
        Evaluate the candidate's answer to the question.

        CONTEXT SUMMARY:
        {summary}

        JOB DESCRIPTION:
        {jd}

        QUESTION:
        {question}

        ANSWER:
        {answer}

        RESPONSE FORMAT (STRICT JSON):
        {{
            "score": int (0-10),
            "performance_state": "STRUGGLING / GOOD / EXCELLENT",
            "adaptive_mode": "SUPPORTIVE / STRICT / NORMAL",
            "feedback": "Concise feedback on this specific answer",
            "suggested_follow_up": "Optional follow-up question if deeper probing is needed"
        }}
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_message_template)
        ])

        chain = prompt | self.llm

        try:
            response = chain.invoke({
                "summary": transcript_summary,
                "jd": jd_text,
                "question": question,
                "answer": answer
            })
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            return json.loads(content)
        except Exception:
            return {"score": 5, "performance_state": "GOOD", "adaptive_mode": "NORMAL", "feedback": "", "suggested_follow_up": None}

    @traceable(name="Summarize Transcript")
    def summarize_interview_transcript(self, current_summary: str, last_q: str, last_a: str) -> str:
        """
        Updates the running summary of the interview.
        """
        prompt = ChatPromptTemplate.from_template("""
        Update the interview summary with the latest exchange. 
        Keep it extremely concise, focusing on key technical strengths and weaknesses demonstrated.

        CURRENT SUMMARY:
        {summary}

        LAST QUESTION:
        {question}

        LAST ANSWER:
        {answer}

        NEW SUMMARY:
        """)
        
        chain = prompt | self.llm
        try:
            response = chain.invoke({
                "summary": current_summary,
                "question": last_q,
                "answer": last_a
            })
            return response.content.strip()
        except Exception:
            return current_summary

    @traceable(name="Final Interview Scoring")
    def finalize_interview_scoring(self, transcript_summary: str, jd_text: str) -> Dict[str, Any]:
        """
        Generates final multi-dimensional score and HR-friendly output.
        """
        system_message = "You are a Senior Technical Recruiter performing a final interview synthesis."
        
        user_message_template = """
        Based on the full interview transcript summary and the job description, provide a final evaluation.

        TRANSCRIPT SUMMARY:
        {summary}

        JOB DESCRIPTION:
        {jd}

        SCORING DIMENSIONS:
        1. Technical Depth
        2. Problem Solving
        3. Communication
        4. Practical Experience
        5. Learning Ability

        RESPONSE FORMAT (STRICT JSON):
        {{
            "overall_score": int (0-100),
            "scores": {{
                "Technical Depth": int(0-100),
                "Problem Solving": int(0-100),
                "Communication": int(0-100),
                "Practical Experience": int(0-100),
                "Learning Ability": int(0-100)
            }},
            "strengths": ["• Bulleted strength"],
            "weaknesses": ["• Bulleted weakness"],
            "risk_level": "LOW / MEDIUM / HIGH",
            "recommendation": "STRONG HIRE / HIRE / BORDERLINE / REJECT",
            "executive_summary": "1-2 sentence final verdict"
        }}
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_message_template)
        ])

        chain = prompt | self.llm

        try:
            response = chain.invoke({
                "summary": transcript_summary,
                "jd": jd_text
            })
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            return json.loads(content)
        except Exception:
            return {"overall_score": 0, "scores": {}, "recommendation": "REJECT", "risk_level": "HIGH"}
