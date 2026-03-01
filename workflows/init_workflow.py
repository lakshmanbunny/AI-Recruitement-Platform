"""
3-Stage Funnel Recruitment Workflow
====================================
Stage 1: Single-Pass Flash (Extract + Score + Justify) — ALL candidates
Funnel Gate: Top 60 proceed
Stage 2: Agentic GitHub Scraper (Trees API + Smart File Select) — Top 60
Stage 3a: Unified Evaluation (Gemini 2.5 Pro) — Top 60
Stage 3b: Interview Readiness Agent — Top 60
Stage 3c: Skeptic Agent — Top 60

Zero embeddings. No LlamaIndex. No Vector DB for resumes.
"""
from typing import TypedDict, List, Any, Dict, Optional
from langgraph.graph import StateGraph, START, END
from config.logging_config import get_logger
from core.llm_service import LLMService
from core.github_verifier import GitHubVerifier
from core.stage1_flash_scorer import Stage1FlashScorer

logger = get_logger(__name__)


class GraphState(TypedDict):
    """
    Streamlined state for the 3-Stage Funnel workflow.
    """
    message: str
    resumes: List[dict]
    job_description: str

    # Stage 1: Flash scores per candidate
    stage_1_results: Dict[str, dict]

    # Ranking (sorted by base_score after Stage 1)
    ranking_results: List[dict]

    # Stage 2: GitHub data
    github_raw_data: Dict[str, dict]
    github_features: Dict[str, dict]
    github_code_files: Dict[str, dict]  # Raw file text from Trees API

    # Stage 3: Agent outputs
    llm_evaluations: Dict[str, dict]        # 3a: Unified evaluation
    interview_readiness: Dict[str, dict]    # 3b: Readiness
    skeptic_analysis: Dict[str, dict]       # 3c: Skeptic

    # Control flags
    force_evaluation: bool
    target_candidate_id: Optional[str]


# =============================================================================
# NODE: Initialize
# =============================================================================
def initialize_node(state: GraphState):
    logger.info("Workflow initialized")
    return {"message": "System is ready."}


# =============================================================================
# NODE: Load Resume Data
# =============================================================================
def load_resume_data_node(state: GraphState):
    resumes = state.get("resumes")
    if not resumes:
        logger.warning("No external resumes provided in state. Proceeding with empty candidate list.")
        resumes = []
    else:
        logger.info(f"Using {len(resumes)} EXTERNAL resumes provided in state")

    jd = state.get("job_description")
    if not jd:
        raise ValueError("CRITICAL ERROR: 'job_description' must be provided in the state.")

    logger.info("Using Job Description provided from Database")
    return {"resumes": resumes, "job_description": jd}


# =============================================================================
# STAGE 1: Single-Pass Flash Extraction & Scoring
# =============================================================================
def stage_1_extraction_node(state: GraphState):
    """
    Runs Gemini 2.0 Flash for every candidate:
    - Takes their pre-extracted resume JSON + JD
    - Returns coverage_score, similarity_score, base_score, hiring_justification
    - No embeddings, no chunking, no vector DB
    """
    resumes = state.get("resumes", [])
    job_description = state.get("job_description")
    target_id = state.get("target_candidate_id")

    scorer = Stage1FlashScorer()
    stage_1_results = {}
    ranking_results = []

    for resume in resumes:
        cand_id = resume.get("candidate_id")
        cand_name = resume.get("name", "Unknown")

        # In force-eval mode, skip non-target candidates (give placeholder)
        if target_id and cand_id.lower() != target_id.lower():
            ranking_results.append({
                "candidate_id": cand_id,
                "name": cand_name,
                "score": 0.0,
                "github_url": resume.get("links", {}).get("github"),
                "stage_1_scored": False
            })
            continue

        # Get the pre-extracted resume text
        resume_text = resume.get("raw_resume_text", "")
        if not resume_text:
            logger.warning(f"[STAGE 1] No raw_resume_text for {cand_id}. Scoring with empty resume.")
            resume_text = "{}"

        # Score with Flash
        result = scorer.score_candidate(
            candidate_id=cand_id,
            resume_json=resume_text,
            job_description=job_description
        )
        stage_1_results[cand_id] = result

        base_score = result.get("stage_1_scores", {}).get("base_score", 0.0)
        ranking_results.append({
            "candidate_id": cand_id,
            "name": cand_name,
            "score": base_score,
            "github_url": resume.get("links", {}).get("github"),
            "stage_1_scored": True
        })

    # Sort by base_score descending
    if target_id:
        ranking_results.sort(
            key=lambda x: (x["candidate_id"].lower() == target_id.lower(), x["score"]),
            reverse=True
        )
    else:
        ranking_results.sort(key=lambda x: x["score"], reverse=True)

    # Log top 10
    logger.info("--- Stage 1 Flash Ranking ---")
    for idx, result in enumerate(ranking_results[:10], 1):
        logger.info(f"  {idx}. {result['candidate_id']} ({result['name']}) — Base: {result['score']:.1f}")

    return {
        "stage_1_results": stage_1_results,
        "ranking_results": ranking_results
    }


# =============================================================================
# FUNNEL GATE: Top 60 Shortlist
# =============================================================================
def funnel_gate_node(state: GraphState):
    """
    Hard blocks candidates outside the Top 60.
    Only passing candidates get Stage 2 (GitHub) and Stage 3 (Pro Judge).
    """
    ranking_results = state.get("ranking_results", [])
    target_id = state.get("target_candidate_id")
    threshold = 60

    if target_id:
        # In force-eval mode, always include the target
        logger.info(f"[FUNNEL GATE] Force-eval mode — target {target_id} always passes.")
        return {"ranking_results": ranking_results}

    if len(ranking_results) > threshold:
        logger.info(f"[FUNNEL GATE] Shortlisting from {len(ranking_results)} to Top {threshold}")
        shortlisted = ranking_results[:threshold]
    else:
        logger.info(f"[FUNNEL GATE] All {len(ranking_results)} candidates pass (below threshold).")
        shortlisted = ranking_results

    return {"ranking_results": shortlisted}


# =============================================================================
# STAGE 2: GitHub Verification (Existing verifier, to be refactored in Phase 2)
# =============================================================================
def github_verification_node(state: GraphState):
    """
    Extracts technical data from GitHub.
    Phase 2 will refactor to Trees API + LLM file selector.
    For now, uses the existing GitHubVerifier.
    """
    ranking_results = state.get("ranking_results", [])
    resumes_list = state.get("resumes", [])
    target_id = state.get("target_candidate_id")

    if target_id:
        top_candidates = [c for c in ranking_results if c["candidate_id"].lower() == target_id.lower()]
    else:
        top_candidates = ranking_results

    github_verifier = GitHubVerifier()

    raw_data_map = {}
    feature_map = {}
    code_files_map = {}

    resume_lookup = {r["candidate_id"]: r for r in resumes_list}

    for rank_item in top_candidates:
        cand_id = rank_item["candidate_id"]
        resume_obj = resume_lookup.get(cand_id)
        if not resume_obj:
            continue

        links = resume_obj.get("links", {})
        username = github_verifier.extract_github_username(links.get("github", ""))

        if not username:
            raw_data_map[cand_id] = {"error": "No link"}
            feature_map[cand_id] = {"activity_score": 0, "ai_relevance_score": 0, "repo_count": 0}
            code_files_map[cand_id] = {"repos": []}
            continue

        repos = github_verifier.fetch_repos(username)
        raw, feat, code_data = github_verifier.analyze_repos(repos, username)

        raw_data_map[cand_id] = raw
        feature_map[cand_id] = feat
        code_files_map[cand_id] = code_data

    return {
        "github_raw_data": raw_data_map,
        "github_features": feature_map,
        "github_code_files": code_files_map,
    }


# =============================================================================
# STAGE 3a: Unified Candidate Evaluation (Gemini 2.5 Pro)
# =============================================================================
def unified_candidate_evaluation_node(state: GraphState):
    """
    Uses the Stage 1 resume data + Stage 2 GitHub data for a deep Pro evaluation.
    Replaces the old RAG-dependent evaluation with direct context passing.
    """
    ranking_results = state.get("ranking_results", [])
    job_description = state.get("job_description")
    resumes_list = state.get("resumes", [])
    stage_1_results = state.get("stage_1_results", {})
    github_features = state.get("github_features", {})
    github_code_files = state.get("github_code_files", {})
    target_id = state.get("target_candidate_id")

    if target_id:
        top_candidates = [c for c in ranking_results if c["candidate_id"].lower() == target_id.lower()]
    else:
        top_candidates = ranking_results

    llm_service = LLMService()
    unified_evals = {}
    resume_lookup = {r["candidate_id"]: r for r in resumes_list}

    for rank_item in top_candidates:
        cand_id = rank_item["candidate_id"]

        # Skip candidates that weren't scored in Stage 1
        if not rank_item.get("stage_1_scored", False):
            continue

        resume_obj = resume_lookup.get(cand_id)
        if not resume_obj:
            continue

        # Build context from Stage 1 + Stage 2 data
        raw_text = resume_obj.get("raw_resume_text", "")
        resume_summary = f"Resume Content:\n{raw_text[:5000]}" if len(raw_text) > 5000 else f"Resume Content:\n{raw_text}"

        stage_1 = stage_1_results.get(cand_id, {})
        gh_feat = github_features.get(cand_id, {})
        gh_code = github_code_files.get(cand_id, {})

        # Format GitHub code files as evidence strings
        gh_evidence = []
        for repo in gh_code.get("repos", []):
            for idx, snippet in enumerate(repo.get("code_snippets", []), 1):
                gh_evidence.append({
                    "repo_name": repo.get("name", "Unknown"),
                    "chunk_text": snippet,
                    "score": 1.0  # No embedding score, raw text
                })

        # Build resume evidence from stage 1 data
        resume_rag_evidence = {
            "raw_chunks": [{
                "text": raw_text[:3000] if raw_text else "",
                "section": "full_resume",
                "score": 1.0
            }]
        }

        try:
            evaluation = llm_service.unified_candidate_evaluation(
                candidate_id=cand_id,
                jd_text=job_description,
                resume_summary=resume_summary,
                github_username=resume_obj.get("links", {}).get("github", "N/A"),
                github_features=gh_feat,
                evidence=gh_evidence,
                resume_rag_evidence=resume_rag_evidence,
            )
        except Exception as e:
            logger.error(f"Unified LLM failed for {cand_id}: {str(e)}")
            evaluation = {"error": str(e), "overall_score": 0}

        unified_evals[cand_id] = evaluation

    return {"llm_evaluations": unified_evals}


# =============================================================================
# STAGE 3b: Interview Readiness Agent
# =============================================================================
def interview_readiness_node(state: GraphState):
    """
    Evaluates top candidates for interview readiness.
    Uses Stage 1 resume data + Stage 3a evaluation as context.
    """
    llm_evaluations = state.get("llm_evaluations", {})
    job_description = state.get("job_description")
    resumes_list = state.get("resumes", [])
    github_code_files = state.get("github_code_files", {})
    llm_service = LLMService()
    readiness_reports = {}
    resume_lookup = {r["candidate_id"]: r for r in resumes_list}

    for cand_id, evaluation in llm_evaluations.items():
        if evaluation.get("error") or evaluation.get("evaluation_blocked"):
            continue

        logger.info(f"Running Readiness Evaluation for {cand_id}")

        # Build context strings from raw resume + GitHub
        resume_obj = resume_lookup.get(cand_id, {})
        raw_text = resume_obj.get("raw_resume_text", "")
        resume_chunks_str = f"RESUME CONTENT:\n{raw_text[:3000]}" if raw_text else "No resume data available."

        gh_code = github_code_files.get(cand_id, {})
        github_chunks_str = ""
        for repo in gh_code.get("repos", []):
            for snippet in repo.get("code_snippets", []):
                github_chunks_str += f"[REPO: {repo.get('name', 'Unknown')}]\n{snippet[:1000]}\n\n"
        if not github_chunks_str:
            github_chunks_str = "No GitHub code evidence available."

        report = llm_service.interview_readiness_evaluation(
            candidate_id=cand_id,
            jd_text=job_description,
            candidate_profile=evaluation,
            resume_chunks=resume_chunks_str,
            github_chunks=github_chunks_str
        )
        readiness_reports[cand_id] = report

    return {"interview_readiness": readiness_reports}


# =============================================================================
# STAGE 3c: Skeptic Agent
# =============================================================================
def skeptic_agent_node(state: GraphState):
    """
    Adversarial risk auditor.
    Uses Stage 3a + 3b outputs.
    """
    interview_readiness = state.get("interview_readiness", {})
    llm_evaluations = state.get("llm_evaluations", {})
    job_description = state.get("job_description")
    resumes_list = state.get("resumes", [])
    github_code_files = state.get("github_code_files", {})
    llm_service = LLMService()
    skeptic_analyses = {}
    resume_lookup = {r["candidate_id"]: r for r in resumes_list}

    for cand_id, gatekeeper_output in interview_readiness.items():
        logger.info(f"Running Adversarial Skeptic Audit for {cand_id}")

        # Build context strings
        resume_obj = resume_lookup.get(cand_id, {})
        raw_text = resume_obj.get("raw_resume_text", "")
        resume_chunks_str = f"RESUME CONTENT:\n{raw_text[:3000]}" if raw_text else "No resume data available."

        gh_code = github_code_files.get(cand_id, {})
        github_chunks_str = ""
        for repo in gh_code.get("repos", []):
            for snippet in repo.get("code_snippets", []):
                github_chunks_str += f"[REPO: {repo.get('name', 'Unknown')}]\n{snippet[:1000]}\n\n"
        if not github_chunks_str:
            github_chunks_str = "No GitHub code evidence available."

        context = {
            "candidate_id": cand_id,
            "eval_summary": llm_evaluations.get(cand_id, {})
        }
        analysis = llm_service.skeptic_evaluation(
            candidate_id=cand_id,
            jd_text=job_description,
            candidate_context=context,
            gatekeeper_output=gatekeeper_output,
            resume_chunks=resume_chunks_str,
            github_chunks=github_chunks_str
        )
        skeptic_analyses[cand_id] = analysis

    return {"skeptic_analysis": skeptic_analyses}


# =============================================================================
# WORKFLOW BUILDER
# =============================================================================
def create_workflow():
    """
    Creates and compiles the 3-Stage Funnel LangGraph workflow.
    """
    workflow = StateGraph(GraphState)

    # Register nodes
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("load_resume_data", load_resume_data_node)
    workflow.add_node("stage_1_extraction", stage_1_extraction_node)
    workflow.add_node("funnel_gate", funnel_gate_node)
    workflow.add_node("github_verification", github_verification_node)
    workflow.add_node("unified_evaluation", unified_candidate_evaluation_node)
    workflow.add_node("interview_readiness", interview_readiness_node)
    workflow.add_node("skeptic_agent", skeptic_agent_node)

    # Wire the graph
    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "load_resume_data")
    workflow.add_edge("load_resume_data", "stage_1_extraction")       # Stage 1: Flash scoring
    workflow.add_edge("stage_1_extraction", "funnel_gate")            # Gate: Top 60
    workflow.add_edge("funnel_gate", "github_verification")           # Stage 2: GitHub
    workflow.add_edge("github_verification", "unified_evaluation")    # Stage 3a: Unified eval
    workflow.add_edge("unified_evaluation", "interview_readiness")    # Stage 3b: Readiness
    workflow.add_edge("interview_readiness", "skeptic_agent")         # Stage 3c: Skeptic
    workflow.add_edge("skeptic_agent", END)                           # Done

    return workflow.compile()
