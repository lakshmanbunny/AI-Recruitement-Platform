from typing import TypedDict, Annotated, List, Any, Dict, Optional
from langgraph.graph import StateGraph, START, END
from config.logging_config import get_logger
from data.sample_resumes import SAMPLE_RESUMES, SAMPLE_JOB_DESCRIPTION
from core.embedding_service import EmbeddingService
from core.vector_store import ResumeVectorStore
from core.similarity import cosine_similarity
from core.llm_service import LLMService
from core.github_verifier import GitHubVerifier
from core.github_vector_store import GitHubCodeVectorStore
from core.llama_indexing.resume_indexer import ResumeLlamaIndexer
from core.llama_indexing.resume_retriever import ResumeHybridRetriever
from core.rag_evaluation.rag_quality_service import rag_quality_service
from core.rag_evaluation.rag_metrics_models import RAGGateDecision

logger = get_logger(__name__)

class GraphState(TypedDict):
    """
    State definition for the LangGraph workflow.
    """
    message: str
    resumes: List[dict]
    job_description: str
    vector_store: Any # ResumeVectorStore instance
    ranking_results: List[dict]
    llm_evaluations: Dict[str, dict]
    evaluation_weights: Optional[Dict[str, float]]
    resume_rag_evidence: Dict[str, dict] # Grounded resume evidence
    github_raw_data: Dict[str, dict]
    github_features: Dict[str, dict]
    github_verifications: Dict[str, dict]
    github_code_data: Dict[str, dict]
    github_vector_store: Any
    github_retrieved_evidence: Dict[str, List[dict]]
    interview_readiness: Dict[str, dict]
    skeptic_analysis: Dict[str, dict]
    final_synthesized_decision: Dict[str, dict]
    hr_decision: Dict[str, Any]
    rag_metrics: Dict[str, dict]         # Embedding-based quick metrics
    rag_health_status: Dict[str, str]    # HEALTHY, WARNING, CRITICAL per candidate
    rag_gate_decisions: Dict[str, str]   # ALLOW, WARN, BLOCK per candidate
    ragas_metrics_full: Dict[str, Any]   # Full RAGMetricsResult objects per candidate
    force_evaluation: bool               # HR manual override flag
    target_candidate_id: Optional[str]   # Specific candidate to evaluate (None for all)
    skip_llm_eval: bool                  # Skip all LLM evaluations to only check retrieval

def initialize_node(state: GraphState):
    """
    Initialization node that logs a message.
    """
    logger.info("Workflow initialized")
    return {
        "message": "System is ready.",
        "hr_decision": {
            "status": "PENDING",
            "decision": None,
            "notes": None,
            "timestamp": None
        }
    }

def load_resume_data_node(state: GraphState):
    """
    Loads resume data and job description into the state.
    Supports external candidate injection.
    """
    resumes = state.get("resumes")
    if not resumes:
        resumes = SAMPLE_RESUMES
        logger.info(f"Using {len(resumes)} SAMPLE resumes (Fallback)")
    else:
        logger.info(f"Using {len(resumes)} EXTERNAL resumes provided in state")
    
    jd = state.get("job_description")
    if not jd:
        jd = SAMPLE_JOB_DESCRIPTION
        logger.info("Using SAMPLE Job Description (Fallback)")
    else:
        logger.info("Using Job Description provided in state")
    
    return {
        "resumes": resumes,
        "job_description": jd
    }

def index_resume_sections_node(state: GraphState):
    """
    Generates embeddings for all candidate resumes using LlamaIndex.
    """
    resumes = state.get("resumes", [])
    
    logger.info(f"Preparing to index {len(resumes)} resumes into LlamaIndex Enterprise Engine")
    
    try:
        llama_indexer = ResumeLlamaIndexer()
        # Force rebuild to ensure the latest dynamically injected JSON is fully chunked
        llama_indexer.build_index(resumes, force_rebuild=True) 
        logger.info(f"{len(resumes)} resumes successfully indexed in LlamaIndex.")
    except Exception as e:
        logger.error(f"[LLAMA INDEX CRITICAL ERROR] Indexing failed: {str(e)}")
        raise e
        
    return {"vector_store": "llama_index"}

def retrieve_candidates_node(state: GraphState):
    """
    Retrieves and ranks candidates based on Job Description similarity 
    exclusively using LlamaIndex Enterprise Retrieval with Whole-Candidate isolation.
    """
    job_description = state.get("job_description")
    resumes = state.get("resumes", [])
    
    ranking_results = []
    
    try:
        from core.llama_indexing.resume_retriever import ResumeHybridRetriever
        llama_retriever = ResumeHybridRetriever()
        logger.info("Triggering Isolated LlamaIndex Retrieval per candidate against JD")
        
        # Whole-Candidate Retrieval: Loop individually to prevent "chunk starvation"
        for resume in resumes:
            cand_id = resume.get("candidate_id")
            cand_name = resume.get("name", "Unknown")
            cand_email = str(resume.get("email", cand_id)).strip().lower() 
            
            # Isolated query using the exact match email filter
            candidate_chunks = llama_retriever.retrieve_candidate_chunks(
                job_description=job_description,
                candidate_email=cand_email,
                top_k=50
            )
            
            # Calculate a primary pre-LLM relevance score for ranking (average of Top 3 chunks)
            score = 0.0
            if candidate_chunks:
                scores = [chunk.get("score", 0.0) for chunk in candidate_chunks]
                top_3_scores = scores[:3]
                score = (sum(top_3_scores) / len(top_3_scores)) * 100 if top_3_scores else 0.0
                
            ranking_results.append({
                "candidate_id": cand_id,
                "name": cand_name,
                "score": score,  # Scale to 0-100 for downstream uniformity
                "github_url": resume.get("links", {}).get("github"),
                "llama_augmented": True,
                "retrieved_chunks": candidate_chunks  # Store chunks with embeddings directly in state for math coverage
            })
                    
        # Sort by isolated candidate score descending
        ranking_results.sort(key=lambda x: x["score"], reverse=True)
            
    except Exception as e:
        logger.error(f"[LLAMA RETRIEVAL FAILED] Error: {str(e)}. No fallback allowed.")
        ranking_results = []

    logger.info("--- Final LlamaIndex Candidate Ranking ---")
    for idx, result in enumerate(ranking_results, 1):
        if idx <= 10: # Only print top 10 to avoid log bloat
            logger.info(f"{idx}. {result['candidate_id']} ({result['name']}) - Score: {result['score']:.4f}, Chunks: {len(result.get('retrieved_chunks', []))}")
        
    return {"ranking_results": ranking_results}

def shortlist_filter_node(state: GraphState):
    """
    STAGE 1.5: Shortlist filter.
    Limits expensive Stage 2 evaluations (GitHub, LLM Deep Dive) to top N candidates.
    """
    ranking_results = state.get("ranking_results", [])
    threshold = 30 # Configurable threshold for deep evaluation
    
    if len(ranking_results) > threshold:
        logger.info(f"[SHORTLIST FILTER] Truncating candidate pool from {len(ranking_results)} to top {threshold} for deep evaluation.")
        shortlisted = ranking_results[:threshold]
    else:
        logger.info(f"[SHORTLIST FILTER] Processing all {len(ranking_results)} candidates (below threshold).")
        shortlisted = ranking_results
        
    return {"ranking_results": shortlisted}

def github_verification_node(state: GraphState):
    """
    EXTRACTS technical data from GitHub. Does NOT perform LLM evaluation.
    """
    ranking_results = state.get("ranking_results", [])
    resumes_list = state.get("resumes", [])
    job_description = state.get("job_description")
    
    # Process candidates
    target_id = state.get("target_candidate_id")
    if target_id:
        top_candidates = [c for c in ranking_results if c["candidate_id"] == target_id]
    else:
        top_candidates = ranking_results
        
    github_verifier = GitHubVerifier()
    gh_vector_store = GitHubCodeVectorStore()
    
    raw_data_map = {}
    feature_map = {}
    code_data_map = {}
    evidence_map = {}
    
    resume_lookup = {r["candidate_id"]: r for r in resumes_list}
    
    for rank_item in top_candidates:
        cand_id = rank_item["candidate_id"]
        resume_obj = resume_lookup.get(cand_id)
        if not resume_obj: continue
            
        links = resume_obj.get("links", {})
        username = github_verifier.extract_github_username(links.get("github", ""))
        
        if not username:
            raw_data_map[cand_id] = {"error": "No link"}
            feature_map[cand_id] = {"activity_score": 0, "ai_relevance_score": 0, "repo_count": 0}
            evidence_map[cand_id] = []
            continue

        repos = github_verifier.fetch_repos(username)
        raw, feat, code_data = github_verifier.analyze_repos(repos, username)
        
        raw_data_map[cand_id] = raw
        feature_map[cand_id] = feat
        code_data_map[cand_id] = code_data

        for repo in code_data.get("repos", []):
            gh_vector_store.add_repo_content(cand_id, repo)
        
        # REMOVED LIMITS: Passing full repository context to Gemini Pro models
        evidence = gh_vector_store.search(job_description, cand_id, top_k=500) # Increased to 500 for deep context
        evidence_map[cand_id] = evidence
        
    return {
        "github_raw_data": raw_data_map,
        "github_features": feature_map,
        "github_code_data": code_data_map,
        "github_vector_store": gh_vector_store,
        "github_retrieved_evidence": evidence_map
    }

def rag_evaluation_node(state: GraphState):
    """
    Enterprise RAG Evaluation Node.
    Computes deterministic ZERO-LLM retrieval metrics and determines gating status.
    """
    ranking_results = state.get("ranking_results", [])
    job_description = state.get("job_description")
    github_evidence_map = state.get("github_retrieved_evidence", {})
    
    from core.llama_indexing.resume_rag import ResumeRAGEvidenceBuilder
    from core.rag_evaluation.deterministic_evaluator import DeterministicRetrievalEvaluator
    from core.embedding_service import EmbeddingService
    from app.db.database import SessionLocal
    from app.db import repository
    
    target_id = state.get("target_candidate_id")
    if target_id:
        top_candidates = [c for c in ranking_results if c["candidate_id"] == target_id]
    else:
        top_candidates = ranking_results

    evaluator = DeterministicRetrievalEvaluator()
    embedding_service = EmbeddingService()
    
    resume_rag_evidence_map = {}
    rag_metrics_map = {}
    rag_health_map = {}
    
    # Prerequisite: JD Embedding for deterministic cosine similarity
    jd_embedding = embedding_service.generate_embedding(job_description)
    
    for rank_item in top_candidates:
        cand_id = rank_item["candidate_id"]
        logger.info(f"[Retrieval Eval] Evaluating {cand_id}")
        
        # 1. Build Resume RAG Evidence mapped from state (Whole-Candidate chunks)
        llama_chunks = rank_item.get("retrieved_chunks", [])
        
        resume_rag_evidence = {
            "candidate_id": cand_id,
            "evidence_summary": f"Retrieved {len(llama_chunks)} chunks iteratively.",
            "sections": {"skills": [], "experience": [], "projects": [], "education": [], "other": []},
            "raw_chunks": llama_chunks
        }
        
        for c in llama_chunks:
            sec = c.get("section", "other").lower()
            if sec not in resume_rag_evidence["sections"]:
                resume_rag_evidence["sections"]["other"].append(c.get("text"))
            else:
                resume_rag_evidence["sections"][sec].append(c.get("text"))
                
        resume_rag_evidence_map[cand_id] = resume_rag_evidence
        
        # 2. Extract and format retrieved chunks from Resume and GitHub
        retrieved_chunks = []
        # Resume chunks
        # Resume chunks (Now preserving `embedding` for Mathematical Coverage!)
        if resume_rag_evidence and "raw_chunks" in resume_rag_evidence:
            for c in resume_rag_evidence["raw_chunks"]:
                retrieved_chunks.append(c)
                
            # 3. Compute Deterministic Metrics (Zero-LLM)
        metrics = evaluator.evaluate_retrieval(
            candidate_id=cand_id,
            jd_text=job_description,
            jd_embedding=jd_embedding,
            retrieved_chunks=retrieved_chunks,
            total_corpus_chunks=[] # Could pass total if available for comprehensive recall
        )
        
        # Removed DB save logic here because candidate doesn't exist yet in the DB.
        # It is instead saved in pipeline_service.py orchestration loop.
        
        rag_metrics_map[cand_id] = metrics
        rag_health_map[cand_id] = metrics["rag_health_status"]
        
    return {
        "resume_rag_evidence": resume_rag_evidence_map,
        "rag_metrics": rag_metrics_map,
        "rag_health_status": rag_health_map
    }


def rag_quality_gate_node(state: GraphState):
    """
    Enterprise RAG Quality Gate Node.
    Deterministically blocks LLM evaluations if retrieval quality fails thresholds.
    """
    ranking_results = state.get("ranking_results", [])
    force_eval = state.get("force_evaluation", False)
    rag_health_status = state.get("rag_health_status", {})

    target_id = state.get("target_candidate_id")
    if target_id:
        top_candidates = [c for c in ranking_results if c["candidate_id"] == target_id]
    else:
        top_candidates = ranking_results

    gate_decisions = {}
    ragas_metrics_full = {} # Legacy compat

    for rank_item in top_candidates:
        cand_id = rank_item["candidate_id"]
        health = rag_health_status.get(cand_id, "CRITICAL")
        
        if force_eval:
            logger.warning(f"[RAG OVERRIDE TRIGGERED] {cand_id}: Force evaluation override applied")
            gate_decisions[cand_id] = "ALLOW"
            ragas_metrics_full[cand_id] = {"status": "OVERRIDE"}
        elif health == "CRITICAL":
            logger.warning(f"[RAG GATE TRIGGERED] {cand_id}: Blocking candidate LLM eval due to CRITICAL deterministic retrieval metrics.")
            gate_decisions[cand_id] = "BLOCK"
            ragas_metrics_full[cand_id] = {"status": "BLOCKED_BY_RETRIEVAL_GATE"}
        else:
            logger.info(f"[RAG HEALTH STATUS] {cand_id}: HEALTHY → Gate: ALLOW")
            gate_decisions[cand_id] = "ALLOW"
            ragas_metrics_full[cand_id] = {"status": "ALLOWED_BY_RETRIEVAL_GATE"}

    return {
        "rag_gate_decisions": gate_decisions,
        "ragas_metrics_full": ragas_metrics_full,
    }

def unified_candidate_evaluation_node(state: GraphState):
    """
    Single Unified Intelligence Node.
    Combines Resume RAG + GitHub RAG + Features into 1 grounded LLM call.
    Strictly follows Quality Gate status from rag_quality_gate_node.
    """
    if state.get("skip_llm_eval"):
        logger.info("[SKIP LLM EVAL] Bypassing Unified Intelligence Node as requested.")
        return {"llm_evaluations": {}}

    ranking_results = state.get("ranking_results", [])
    job_description = state.get("job_description")
    resumes_list = state.get("resumes", [])
    github_features = state.get("github_features", {})
    gh_evidence_map = state.get("github_retrieved_evidence", {})
    resume_rag_evidence_map = state.get("resume_rag_evidence", {})
    rag_gate_decisions = state.get("rag_gate_decisions", {})
    # Fallback to old rag_health_status if gate not populated
    rag_health_status = state.get("rag_health_status", {})

    target_id = state.get("target_candidate_id")
    if target_id:
        top_candidates = [c for c in ranking_results if c["candidate_id"] == target_id]
    else:
        top_candidates = ranking_results
    llm_service = LLMService()

    unified_evals = {}
    resume_lookup = {r["candidate_id"]: r for r in resumes_list}

    for rank_item in top_candidates:
        cand_id = rank_item["candidate_id"]

        # AUTHORITATIVE GATE: Use RAGAS gate decision if available
        gate = rag_gate_decisions.get(cand_id)
        if not gate:
            # Fallback to embedding-based health
            health = rag_health_status.get(cand_id, "CRITICAL")
            gate = "ALLOW" if health == "HEALTHY" else ("WARN" if health == "WARNING" or health == "DEGRADED" else "BLOCK")

        if gate == "BLOCK":
            logger.warning(f"[RAG GATE TRIGGERED] Blocking LLM eval for {cand_id} due to gate: BLOCK")
            unified_evals[cand_id] = {
                "evaluation_blocked": True,
                "reason": "Evaluation blocked: RAG quality below enterprise thresholds. Use 'Force Eval' to override.",
                "overall_score": 0,
                "resume_score": 0,
                "github_score": 0,
                "justification": ["Evaluation blocked due to insufficient retrieval quality."]
            }
            continue
        elif gate == "PENDING":
            logger.warning(f"[RAG GATE TRIGGERED] Blocking LLM eval for {cand_id} due to PENDING background RAGAS job")
            unified_evals[cand_id] = {
                "evaluation_blocked": True,
                "reason": "Evaluation blocked: Pending background RAGAS evaluation. Please wait.",
                "overall_score": 0,
                "resume_score": 0,
                "github_score": 0,
                "justification": ["Evaluation deferred until RAGAS metrics are available."]
            }
            continue
        elif gate == "WARN":
            logger.warning(f"[RAG GATE WARNING] Allowing LLM eval for {cand_id} with WARNING-level RAG quality")

        resume_obj = resume_lookup.get(cand_id)
        if not resume_obj:
            continue

        resume_rag_evidence = resume_rag_evidence_map.get(cand_id, {})
        raw_text = resume_obj.get("raw_resume_text", "")
        resume_summary = f"Resume Content:\n{raw_text[:3000]}..." if len(raw_text) > 3000 else f"Resume Content:\n{raw_text}"
        gh_feat = github_features.get(cand_id, {})
        gh_evidence = gh_evidence_map.get(cand_id, [])
        weights = state.get("evaluation_weights")

        try:
            evaluation = llm_service.unified_candidate_evaluation(
                candidate_id=cand_id,
                jd_text=job_description,
                resume_summary=resume_summary,
                github_username=resume_obj.get("links", {}).get("github", "N/A"),
                github_features=gh_feat,
                evidence=gh_evidence,
                resume_rag_evidence=resume_rag_evidence,
                weights=weights
            )
        except Exception as e:
            logger.error(f"Unified LLM failed for {cand_id}: {str(e)}")
            evaluation = {"error": str(e), "overall_score": 0}

        unified_evals[cand_id] = evaluation

    return {"llm_evaluations": unified_evals}

def interview_readiness_node(state: GraphState):
    """
    Final hiring intelligence layer.
    Evaluates top candidates for interview readiness.
    Skips if RAG quality is low.
    """
    llm_evaluations = state.get("llm_evaluations", {})
    rag_quality_status = state.get("rag_quality_status", {})
    llm_service = LLMService()
    readiness_reports = {}
    
    for cand_id, evaluation in llm_evaluations.items():
        if rag_quality_status.get(cand_id) != "READY":
            continue
            
        logger.info(f"Running Readiness Evaluation for {cand_id}")
        report = llm_service.interview_readiness_evaluation(evaluation)
        readiness_reports[cand_id] = report
        
    return {"interview_readiness": readiness_reports}

def skeptic_agent_node(state: GraphState):
    """
    Adversarial risk auditor node.
    Skips if RAG quality is low.
    """
    interview_readiness = state.get("interview_readiness", {})
    rag_quality_status = state.get("rag_quality_status", {})
    llm_service = LLMService()
    skeptic_analyses = {}
    
    for cand_id, gatekeeper_output in interview_readiness.items():
        if rag_quality_status.get(cand_id) != "READY":
            continue
            
        logger.info(f"Running Adversarial Skeptic Audit for {cand_id}")
        context = {
            "candidate_id": cand_id,
            "eval_summary": state.get("llm_evaluations", {}).get(cand_id, {})
        }
        analysis = llm_service.skeptic_evaluation(context, gatekeeper_output)
        skeptic_analyses[cand_id] = analysis
        
    return {"skeptic_analysis": skeptic_analyses}

def final_decision_node(state: GraphState):
    """
    Final decision synthesizer node.
    Skips if RAG quality is low.
    """
    interview_readiness = state.get("interview_readiness", {})
    skeptic_analysis = state.get("skeptic_analysis", {})
    llm_evaluations = state.get("llm_evaluations", {})
    rag_health_status = state.get("rag_health_status", {})
    rag_override = state.get("force_evaluation", False)
    llm_service = LLMService()
    final_decisions = {}
    
    for cand_id, gatekeeper_output in interview_readiness.items():
        health = rag_health_status.get(cand_id, "CRITICAL")
        if health != "HEALTHY" and not rag_override:
            continue
            
        logger.info(f"Synthesizing Final Hiring Decision for {cand_id}")
        skeptic_output = skeptic_analysis.get(cand_id, {})
        unified_scores = llm_evaluations.get(cand_id, {})
        
        decision = llm_service.synthesize_final_decision(
            gatekeeper_output, 
            skeptic_output, 
            unified_scores
        )
        final_decisions[cand_id] = decision
        
    return {"final_synthesized_decision": final_decisions}

def create_workflow():
    """
    Creates and compiles the LangGraph workflow.
    """
    workflow = StateGraph(GraphState)
    
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("load_resume_data", load_resume_data_node)
    workflow.add_node("index_resume_sections", index_resume_sections_node)
    workflow.add_node("retrieve_candidates", retrieve_candidates_node)
    workflow.add_node("shortlist_filter", shortlist_filter_node) # NEW: Tiered filter
    workflow.add_node("github_verification", github_verification_node)
    workflow.add_node("rag_evaluation", rag_evaluation_node)
    workflow.add_node("rag_quality_gate", rag_quality_gate_node)  # NEW: Enterprise RAGAS gate
    workflow.add_node("unified_evaluation", unified_candidate_evaluation_node)
    workflow.add_node("interview_readiness", interview_readiness_node)
    workflow.add_node("skeptic_agent", skeptic_agent_node)
    workflow.add_node("final_decision", final_decision_node)
    
    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "load_resume_data")
    workflow.add_edge("load_resume_data", "index_resume_sections")
    workflow.add_edge("index_resume_sections", "retrieve_candidates")
    workflow.add_edge("retrieve_candidates", "rag_evaluation") # -> Stage 1 metrics for ALL first
    workflow.add_edge("rag_evaluation", "shortlist_filter") # -> Then filter for expensive Stage 2
    workflow.add_edge("shortlist_filter", "github_verification") 
    workflow.add_edge("github_verification", "rag_quality_gate")  # -> Enterprise gate
    workflow.add_edge("rag_quality_gate", "unified_evaluation")  # -> LLM eval (gated)
    workflow.add_edge("unified_evaluation", "interview_readiness")
    workflow.add_edge("interview_readiness", "skeptic_agent")
    workflow.add_edge("skeptic_agent", "final_decision")
    workflow.add_edge("final_decision", END)
    
    return workflow.compile()
