import os
import sys

# Add root folder to sys.path to easily import core and backend modules
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from core.rag_evaluation.deterministic_evaluator import DeterministicRetrievalEvaluator
from core.embedding_service import EmbeddingService

def main():
    service = EmbeddingService()
    evaluator = DeterministicRetrievalEvaluator()
    
    # Mock JD
    jd_text = "We are looking for a Senior Python Developer with experience in Django, React, and AWS."
    
    # Mock Chunks
    retrieved_chunks = [
        {"text": "I am a Python developer and I know Django well.", "metadata": {"section": "skills"}},
        {"text": "Worked on React frontends.", "metadata": {"section": "experience"}},
        {"text": "I like playing tennis.", "metadata": {"section": "hobbies"}}
    ]
    
    # Mock corpus chunks (for recall calculation)
    corpus = retrieved_chunks + [
        {"text": "Deployed applications using AWS EC2.", "metadata": {"section": "projects"}} 
    ]
    
    jd_emb = service.generate_embedding(jd_text)
    
    print("\n--- Evaluating MOCK Chunks ---")
    metrics = evaluator.evaluate_retrieval(
        candidate_id="mock_candidate",
        jd_text=jd_text,
        jd_embedding=jd_emb,
        retrieved_chunks=retrieved_chunks,
        total_corpus_chunks=corpus
    )
    
    import pprint
    pprint.pprint(metrics)
    
    if metrics["rag_health_status"] == "CRITICAL":
        print("\nSUCCESS: Gate triggered correctly (Missing AWS from retrieved but present in corpus -> low recall)")
    else:
        print("\nFAILURE: Gate not triggered when it should have been.")
        
if __name__ == "__main__":
    main()
