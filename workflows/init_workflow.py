from typing import TypedDict, Annotated, List, Any, Dict
from langgraph.graph import StateGraph, START, END
from config.logging_config import get_logger
from data.sample_resumes import SAMPLE_RESUMES, SAMPLE_JOB_DESCRIPTION
from core.embedding_service import EmbeddingService
from core.vector_store import ResumeVectorStore
from core.similarity import cosine_similarity
from core.llm_service import LLMService
from core.github_verifier import GitHubVerifier
from core.github_vector_store import GitHubCodeVectorStore

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
    Loads sample resume data and job description into the state.
    """
    logger.info(f"{len(SAMPLE_RESUMES)} resumes successfully loaded into system")
    logger.info("Job description loaded")
    return {
        "resumes": SAMPLE_RESUMES,
        "job_description": SAMPLE_JOB_DESCRIPTION
    }

def index_resume_sections_node(state: GraphState):
    """
    Generates embeddings for resume sections and stores them in the vector store.
    """
    resumes = state.get("resumes", [])
    embedding_service = EmbeddingService()
    vector_store = ResumeVectorStore()
    
    sections = ["skills", "experience", "projects", "education"]
    
    for resume in resumes:
        candidate_id = resume["candidate_id"]
        logger.info(f"Indexing candidate: {candidate_id}")
        
        for section in sections:
            text = resume.get(section, "")
            if text:
                logger.info(f"Generating embedding for {candidate_id} - {section}")
                vector = embedding_service.generate_embedding(text)
                vector_store.add_candidate_section_embedding(candidate_id, section, vector)
    
    logger.info(f"{len(resumes)} resumes fully indexed")
    return {"vector_store": vector_store}

def retrieve_candidates_node(state: GraphState):
    """
    Retrieves and ranks candidates based on Job Description similarity.
    """
    job_description = state.get("job_description")
    vector_store = state.get("vector_store")
    resumes = state.get("resumes", [])
    
    embedding_service = EmbeddingService()
    
    logger.info("Generating embedding for Job Description")
    jd_vector = embedding_service.generate_embedding(job_description)
    
    weights = {
        "skills": 0.4,
        "experience": 0.3,
        "projects": 0.2,
        "education": 0.1
    }
    
    ranking_results = []
    all_embeddings = vector_store.get_all_embeddings()
    
    for resume in resumes:
        candidate_id = resume["candidate_id"]
        logger.info(f"Calculating similarity for {candidate_id}")
        
        weighted_score = 0.0
        candidate_embeddings = all_embeddings.get(candidate_id, {})
        
        for section, weight in weights.items():
            section_vector = candidate_embeddings.get(section)
            if section_vector:
                similarity = cosine_similarity(jd_vector, section_vector)
                logger.info(f"Similarity for {candidate_id} - {section}: {similarity:.4f}")
                weighted_score += similarity * weight
        
        logger.info(f"Final Score for {candidate_id}: {weighted_score:.4f}")
        ranking_results.append({
            "candidate_id": candidate_id,
            "name": resume["name"],
            "score": weighted_score * 100, # Scale to 0-100
            "github_url": resume.get("links", {}).get("github")
        })
    
    # Sort by score descending
    ranking_results.sort(key=lambda x: x["score"], reverse=True)
    
    logger.info("Final Candidate Ranking:")
    for idx, result in enumerate(ranking_results, 1):
        logger.info(f"{idx}. {result['candidate_id']} ({result['name']}) - Score: {result['score']:.4f}")
        
    return {"ranking_results": ranking_results}

def github_verification_node(state: GraphState):
    """
    EXTRACTS technical data from GitHub. Does NOT perform LLM evaluation.
    """
    ranking_results = state.get("ranking_results", [])
    resumes_list = state.get("resumes", [])
    job_description = state.get("job_description")
    
    # Process TOP-3 candidates
    top_candidates = ranking_results[:3]
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
        
        # Max 3 chunks for efficiency
        evidence = gh_vector_store.search(job_description, cand_id, top_k=3)
        evidence_map[cand_id] = evidence
        
    return {
        "github_raw_data": raw_data_map,
        "github_features": feature_map,
        "github_code_data": code_data_map,
        "github_vector_store": gh_vector_store,
        "github_retrieved_evidence": evidence_map
    }

def unified_candidate_evaluation_node(state: GraphState):
    """
    Single Unified Intelligence Node.
    Combines Resume + GitHub + RAG into 1 LLM call.
    """
    ranking_results = state.get("ranking_results", [])
    job_description = state.get("job_description")
    resumes_list = state.get("resumes", [])
    github_features = state.get("github_features", {})
    evidence_map = state.get("github_retrieved_evidence", {})
    
    top_candidates = ranking_results[:3]
    llm_service = LLMService()
    unified_evals = {}
    
    resume_lookup = {r["candidate_id"]: r for r in resumes_list}
    
    for rank_item in top_candidates:
        cand_id = rank_item["candidate_id"]
        resume_obj = resume_lookup.get(cand_id)
        if not resume_obj: continue

        # Summary for context preservation
        resume_summary = f"Skills: {resume_obj['skills']} | Experience: {resume_obj['experience'][:500]}..."
        gh_feat = github_features.get(cand_id, {})
        evidence = evidence_map.get(cand_id, [])
        
        try:
            evaluation = llm_service.unified_candidate_evaluation(
                candidate_id=cand_id,
                jd_text=job_description,
                resume_summary=resume_summary,
                github_username=resume_obj.get("links", {}).get("github", "N/A"),
                github_features=gh_feat,
                evidence=evidence
            )
        except Exception as e:
            logger.warning(f"Unified LLM failed for {cand_id}, using heuristic: {str(e)}")
            # Heuristic: overall_score = 0.5 * res_sim + 0.3 * gh_rel + 0.2 * act_score
            res_similarity = rank_item.get("score", 50) # Already scaled to 0-100 now
            gh_relevance = gh_feat.get("ai_relevance_score", 0)
            act_score = gh_feat.get("activity_score", 0)
            
            heuristic_overall = (0.5 * res_similarity) + (0.3 * gh_relevance) + (0.2 * act_score)
            evaluation = {
                "resume_score": int(res_similarity),
                "github_score": int(gh_relevance),
                "overall_score": int(heuristic_overall),
                "justification": ["Heuristic result based on combined similarity and repository signals."]
            }
            
        unified_evals[cand_id] = evaluation

    return {"llm_evaluations": unified_evals}

def interview_readiness_node(state: GraphState):
    """
    Final hiring intelligence layer.
    Evaluates top candidates for interview readiness.
    """
    llm_evaluations = state.get("llm_evaluations", {})
    llm_service = LLMService()
    readiness_reports = {}
    
    for cand_id, evaluation in llm_evaluations.items():
        logger.info(f"Running Readiness Evaluation for {cand_id}")
        report = llm_service.interview_readiness_evaluation(evaluation)
        readiness_reports[cand_id] = report
        
    return {"interview_readiness": readiness_reports}

def skeptic_agent_node(state: GraphState):
    """
    Adversarial risk auditor node.
    Challenges hiring decisions and identifies potential dangers for top candidates.
    """
    interview_readiness = state.get("interview_readiness", {})
    llm_service = LLMService()
    skeptic_analyses = {}
    
    for cand_id, gatekeeper_output in interview_readiness.items():
        logger.info(f"Running Adversarial Skeptic Audit for {cand_id}")
        # Build context for skeptic
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
    Acts as the Chief Recruitment Officer to reach a final hiring consensus.
    """
    interview_readiness = state.get("interview_readiness", {})
    skeptic_analysis = state.get("skeptic_analysis", {})
    llm_evaluations = state.get("llm_evaluations", {})
    llm_service = LLMService()
    final_decisions = {}
    
    for cand_id, gatekeeper_output in interview_readiness.items():
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
    workflow.add_node("github_verification", github_verification_node)
    workflow.add_node("unified_evaluation", unified_candidate_evaluation_node)
    workflow.add_node("interview_readiness", interview_readiness_node)
    workflow.add_node("skeptic_agent", skeptic_agent_node)
    workflow.add_node("final_decision", final_decision_node)
    
    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "load_resume_data")
    workflow.add_edge("load_resume_data", "index_resume_sections")
    workflow.add_edge("index_resume_sections", "retrieve_candidates")
    workflow.add_edge("retrieve_candidates", "github_verification")
    workflow.add_edge("github_verification", "unified_evaluation")
    workflow.add_edge("unified_evaluation", "interview_readiness")
    workflow.add_edge("interview_readiness", "skeptic_agent")
    workflow.add_edge("skeptic_agent", "final_decision")
    workflow.add_edge("final_decision", END)
    
    return workflow.compile()
