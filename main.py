from config.logging_config import get_logger
from workflows.init_workflow import create_workflow
from core.settings import settings

# Initialize logger
logger = get_logger("main")

def main():
    logger.info("Starting AI Recruitment Screening System POC...")
    
    # Verify LangChain configuration is picked up
    if settings.LANGCHAIN_TRACING_V2 == "true":
        logger.info(f"LangSmith Tracing enabled for project: {settings.LANGCHAIN_PROJECT}")
    
    # Initialize and run the workflow
    workflow = create_workflow()
    
    logger.info("Running initialization workflow...")
    result = workflow.invoke({"message": "Starting..."})
    
    logger.info(f"Workflow execution completed.")
    
    # Print final ranked candidates
    ranking = result.get("ranking_results", [])
    if ranking:
        print("\n" + "="*50)
        print("FINAL CANDIATE RANKING (Stage-1 Retrieval)")
        print("="*50)
        for idx, cand in enumerate(ranking, 1):
            print(f"{idx}. {cand['candidate_id']} - {cand['name']} | Score: {cand['score']:.4f}")
        print("="*50 + "\n")
    else:
        logger.warning("No ranking results found.")

    # Print final AI evaluations
    # The workflow result is the final state
    final_state = result 
    # Print Final Results
    print("\n" + "="*50)
    print("FINAL AI EVALUATION RESULTS (Stage-2 Re-Ranking)")
    print("="*50)
    
    llm_evals = final_state.get("llm_evaluations", {})
    
    if llm_evals:
        for cand_id, eval_data in llm_evals.items():
            print(f"Candidate ID: {cand_id}")
            print(f"Overall Intelligence Score: {eval_data.get('overall_score')}/100")
            print(f"  - Resume Fit: {eval_data.get('resume_score')}/100")
            print(f"  - GitHub Strength: {eval_data.get('github_score')}/100")
            
            gh_raw = final_state.get("github_raw_data", {}).get(cand_id, {})
            gh_feat = final_state.get("github_features", {}).get(cand_id, {})
            
            if "total_repos" in gh_raw:
                print(f"[Evidence] Total Repos: {gh_raw.get('total_repos')} | AI-Relevant: {len(gh_raw.get('ai_relevant_repos', []))}")
                print(f"[Features] Activity Score: {gh_feat.get('activity_score')} | Relevance Score: {gh_feat.get('ai_relevance_score')}")
            
            print(f"Hiring Justification: {eval_data.get('justification')}")
            print("-" * 30)
        print("="*50 + "\n")
    else:
        logger.warning("No AI evaluation results found.")

if __name__ == "__main__":
    main()
