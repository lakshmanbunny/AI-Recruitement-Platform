import json
import re
import os
from typing import Dict, List, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langsmith import traceable
from core.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)

class LLMService:
    """
    Enterprise-grade LLM Service with LangSmith observability and LangChain integration.
    """
    def __init__(self):
        # Generator: Gemini 2.0 Pro (or latest Pro fallback)
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-pro",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.2,
            convert_system_message_to_human=True
        )
        # Judge: Gemini 3.0 Pro (or latest Pro fallback)
        self.judge_llm = ChatGoogleGenerativeAI(
            model="gemini-3-pro-preview",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.1,
            convert_system_message_to_human=True
        )

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
        
        # 3. FORMAT CHUNKS WITH CITATIONS (Part 2.1 & 2.2)
        resume_chunks_str = ""
        for i, chunk in enumerate(top_resume, 1):
            resume_chunks_str += f"[RESUME_CHUNK_ID: R{i}]\nSection: {chunk.get('section', 'Unknown').capitalize()}\nContent: {chunk.get('text', '')}\n\n"
        
        if not resume_chunks_str:
            resume_chunks_str = "No high-relevance resume evidence retrieved (Similarity < 0.45)."

        github_chunks_str = ""
        for i, chunk in enumerate(top_github, 1):
            github_chunks_str += f"[GITHUB_CHUNK_ID: G{i}]\nRepo: {chunk.get('repo_name', 'Unknown')}\nContent: {chunk.get('chunk_text', '')}\n\n"
        
        if not github_chunks_str:
            github_chunks_str = "No high-relevance GitHub code evidence retrieved (Similarity < 0.45)."

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
        ctx_chars = len(system_prompt + user_template)
        from core.utils.context_hasher import compute_context_hash
        generator_hash = compute_context_hash(resume_chunks_str + github_chunks_str)
        logger.info(f"[TRACE] Context chars: {ctx_chars}")
        logger.info(f"[TRACE] Tokens est: {ctx_chars // 4}")
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
                try:
                    logger.info(f"Invoking Enterprise LLM Judge (Gemini 3.0 Pro) for audit of {candidate_id}")
                    with open(os.path.join(curr_dir, "prompts", "judge_audit_user_template.txt"), "r") as f:
                        judge_template = f.read()
                    
                    judge_prompt = ChatPromptTemplate.from_messages([
                        ("system", "You are a senior hiring auditor. Audit the following AI recruitment evaluation for accuracy and fairness."),
                        ("human", judge_template)
                    ])
                    
                    judge_chain = judge_prompt | self.judge_llm
                    judge_payload = {
                        "candidate_id": candidate_id,
                        "job_description": jd_text,
                        "evaluation_json": json.dumps(eval_data, indent=2),
                        "resume_chunks": resume_chunks_str,
                        "github_chunks": github_chunks_str
                    }
                    
                    judge_response = judge_chain.invoke(judge_payload)
                    judge_content = judge_response.content
                    if "```json" in judge_content:
                        judge_content = judge_content.split("```json")[1].split("```")[0].strip()
                    elif "```" in judge_content:
                        judge_content = judge_content.split("```")[1].split("```")[0].strip()
                    
                    audit_res = json.loads(judge_content)
                    
                    # Merge Judge's revisions if any
                    if audit_res.get("judge_verdict") == "REVISED":
                        logger.warning(f"LLM Judge REVISED evaluation for {candidate_id}: {audit_res.get('audit_reasoning')}")
                        eval_data["rubric_scores"] = audit_res.get("corrected_rubric_scores", eval_data.get("rubric_scores"))
                        eval_data["overall_score"] = audit_res.get("corrected_overall_score", eval_data.get("overall_score"))
                        eval_data["justification"] = audit_res.get("corrected_justification", eval_data.get("justification"))
                    
                    eval_data["judge_audit"] = {
                        "verdict": audit_res.get("judge_verdict", "APPROVED"),
                        "reasoning": audit_res.get("audit_reasoning", "No discrepancies found."),
                        "confidence": audit_res.get("confidence_in_audit", 100)
                    }
                except Exception as je:
                    logger.error(f"LLM Judge Audit failed for {candidate_id}: {je}")
                    eval_data["judge_audit"] = {"verdict": "ERROR", "reasoning": str(je)}

                # Extract AI-assessed RAG metrics (Stage 2)
                eval_data["precision_score"] = eval_data.get("precision_score", 0)
                eval_data["recall_score"] = eval_data.get("recall_score", 0)
                
                # Validation Logic
                issues = []
                # Check citations in justification
                for bullet in eval_data.get("justification", []):
                    if not re.search(r"\[[RG][0-9]+\]", bullet):
                        issues.append("Missing citation in justification bullet")
                
                # Check score ranges
                rubric = eval_data.get("rubric_scores", {})
                for k, v in rubric.items():
                    if not (0 <= v <= 10):
                        v_int = int(v) if isinstance(v, (int, float)) else 0
                        if not (0 <= v_int <= 10):
                            issues.append(f"Rubric score {k}={v} out of range [0-10]")
                
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
                    "error": f"Evaluation failed after {max_attempts} attempts: {str(e)}",
                    "overall_score": 0,
                    "justification": ["System error during evaluation."]
                }
        return {}

    @traceable(name="Interview Readiness Evaluation")
    def interview_readiness_evaluation(self, candidate_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Final hiring intelligence layer to evaluate interview readiness.
        Strict enterprise gatekeeper calibration.
        """
        system_message = """You are a strict senior technical recruiter for a top-tier AI company.
Your role is NOT to praise candidates.
Your job is to identify hiring risks and make conservative hiring decisions.

Follow these mandatory evaluation principles:
1. Assume the candidate is NOT hire-ready unless strong evidence proves otherwise.
2. Always prioritize risk detection over strengths.
3. No candidate is perfect — you MUST identify at least 2 skill gaps and at least 1 risk factor.
4. Confidence score must be conservative: It must NEVER exceed the weakest dimension score. If any major gap exists, confidence must be below 85%.
5. HIGH readiness is extremely rare: Only assign HIGH if candidate has proven production experience, strong GitHub evidence, and no critical skill gaps.
8. Focus on potential hiring risks: Lack of real-world deployment, shallow understanding, over-reliance on tutorials, limited system design exposure.

STRICT FORMATTING RULE: 
- Use ONLY concise bullet points for textual explanations.
- Max 8 bullet points per section.
- No narrative sentences or paragraphs.

Return only structured JSON output."""
        
        user_message_template = """
        Evaluate candidate readiness based on the following holistic profile.
        
        CANDIDATE PROFILE:
        {profile}

        STRICT OUTPUT RULES:
        - Always include at least 2 skill gaps.
        - Always include at least 1 risk factor.
        - Confidence must be realistic.
        - Avoid generic praise.
        - Justification must mention weaknesses.
        
        RESPONSE FORMAT (STRICT JSON, Max 400 tokens):
        {{
            "hire_readiness_level": "str (HIGH/MEDIUM/LOW)",
            "confidence_score": int (0-100),
            "risk_factors": ["🔴 list of risk bullet points"],
            "skill_gaps": ["⚠ list of skill gap bullet points"],
            "interview_focus_areas": ["🔍 list of interview focus bullet points"],
            "final_hiring_recommendation": "str (Strong Hire / Hire / Borderline / Reject)",
            "executive_summary": ["✔ bulleted summaries of why this recommendation was made"]
        }}
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_message_template)
        ])

        chain = prompt | self.llm

        config = {
            "tags": ["stage:interview_readiness", "component:hiring_intelligence"],
            "metadata": {
                "candidate_id": candidate_profile.get("candidate_id", "unknown"),
                "overall_score": candidate_profile.get("overall_score", 0)
            }
        }

        logger.info(f"Invoking Strict Interview Readiness Agent for candidate")
        try:
            response = chain.invoke({
                "profile": json.dumps(candidate_profile, indent=2)
            }, config=config)
            
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
            
            # Defensive check for list fields
            for field in ["risk_factors", "skill_gaps", "interview_focus_areas", "executive_summary"]:
                if field in result and isinstance(result[field], str):
                    result[field] = [result[field]]
            
            # --- Score Calibration Logic ---
            res_score = candidate_profile.get("resume_score", 100)
            gh_score = candidate_profile.get("github_score", 100)
            
            # Confidence must be min(provided_confidence, resume_score, github_score)
            result["confidence_score"] = min(
                result.get("confidence_score", 100),
                res_score,
                gh_score
            )
            
            # Heuristic: Reduce over-scoring
            skill_gaps = result.get("skill_gaps", [])
            if len(skill_gaps) >= 3 and result.get("hire_readiness_level") == "HIGH":
                result["hire_readiness_level"] = "MEDIUM"
                result["final_hiring_recommendation"] = "Borderline"

            logger.info("Strict interview readiness evaluation completed.")
            return result
        except Exception as e:
            logger.error(f"Interview readiness evaluation failed: {str(e)}")
            # Fallback
            return {
                "hire_readiness_level": "LOW",
                "confidence_score": 30,
                "risk_factors": ["Evaluation error - manual review required"],
                "skill_gaps": ["Technical evaluation failure", "Data inconsistency"],
                "interview_focus_areas": ["Foundational system design", "Core architecture"],
                "final_hiring_recommendation": "Reject",
                "executive_summary": ["System failure during strict assessment. Automatic rejection recommended until manual audit."]
            }

    @traceable(name="AI Skeptic Analysis")
    def skeptic_evaluation(self, candidate_context: Dict[str, Any], gatekeeper_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adversarial LLM agent to challenge hiring decisions and identify hidden risks.
        """
        system_message = """You are a senior hiring risk auditor.
Your role is to challenge hiring decisions and identify reasons NOT to hire a candidate.
You must behave like a skeptical recruiter who assumes the hiring decision may be wrong.

Evaluation principles:
1. Your job is NOT to praise candidates.
2. You must identify hidden risks and long-term hiring dangers.
3. Focus on: Lack of real-world production experience, over-reliance on academic projects, weak system design exposure, missing collaboration/teamwork evidence, scalability concerns, limited domain depth.
4. Always provide at least 3 risk concerns and at least 2 critical skill gaps.
6. Be direct and realistic. Avoid polite HR language.

STRICT FORMATTING RULE: 
- Use ONLY concise bullet points.
- No paragraphs.
- Be direct and blunt.

Return only structured JSON output."""

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
            "skeptic_recommendation": ["• Final warnings in bullet form"]
        }}
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_message_template)
        ])

        chain = prompt | self.llm

        config = {
            "tags": ["stage:skeptic_analysis", "component:adversarial_agent"],
            "metadata": {
                "candidate_id": candidate_context.get("candidate_id", "unknown"),
                "gatekeeper_readiness": gatekeeper_output.get("hire_readiness_level", "unknown")
            }
        }

        logger.info("Invoking AI Skeptic Agent for candidate audit")
        try:
            response = chain.invoke({
                "context": json.dumps(candidate_context, indent=2),
                "gatekeeper": json.dumps(gatekeeper_output, indent=2)
            }, config=config)
            
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
            
            # Defensive check for list fields
            for field in ["major_concerns", "hidden_risks", "critical_skill_gaps", "skeptic_recommendation"]:
                if field in result and isinstance(result[field], str):
                    result[field] = [result[field]]
            
            logger.info("AI Skeptic analysis completed.")
            return result
        except Exception as e:
            logger.error(f"AI Skeptic analysis failed: {str(e)}")
            return {
                "risk_level": "MEDIUM",
                "major_concerns": ["Skeptic audit system error"],
                "hidden_risks": ["Possible unvetted evaluation logic"],
                "critical_skill_gaps": ["Safety audit missing"],
                "skeptic_recommendation": ["Caution: Manual safety audit required due to system failure."]
            }

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
