from config.logging_config import get_logger
from .resume_indexer import ResumeLlamaIndexer

logger = get_logger(__name__)

class ResumeHybridRetriever:
    """
    Retriever that uses both keyword and semantic chunk-based retrieval
    via LlamaIndex to identify the best candidates.
    """
    def __init__(self, index_dir="storage/llama_resume.index"):
        self.indexer = ResumeLlamaIndexer(persist_dir=index_dir)
        try:
            self.retriever = self.indexer.get_retriever(similarity_top_k=20)
        except Exception:
            self.retriever = None

    def retrieve_top_candidates(self, job_description: str, top_k=10):
        """
        Retrieves top candidates based on LlamaIndex chunk matching.
        """
        if not self.retriever:
            logger.warning("[LLAMA RETRIEVAL INACTIVE] Retriever not initialized.")
            return []

        logger.info("[LLAMA RETRIEVAL ACTIVE] Performing semantic chunk-based search...")
        
        # Retrieve chunks
        nodes = self.retriever.retrieve(job_description)
        
        # Aggregate by candidate_id
        candidate_matches = {}
        
        for node_with_score in nodes:
            node = node_with_score.node
            score = node_with_score.score
            
            cand_id = node.metadata.get("candidate_id")
            if not cand_id:
                continue
                
            if cand_id not in candidate_matches:
                candidate_matches[cand_id] = {
                    "candidate_id": cand_id,
                    "candidate_name": node.metadata.get("candidate_name"),
                    "max_score": score,
                    "sum_score": score,
                    "count": 1,
                    "matched_chunks": [node.get_content()]
                }
            else:
                candidate_matches[cand_id]["max_score"] = max(candidate_matches[cand_id]["max_score"], score)
                candidate_matches[cand_id]["sum_score"] += score
                candidate_matches[cand_id]["count"] += 1
                if node.get_content() not in candidate_matches[cand_id]["matched_chunks"]:
                    candidate_matches[cand_id]["matched_chunks"].append(node.get_content())

        # Logic for final ranking: Use a combination of max_score and frequency/sum
        # For LlamaIndex FAISS (IndexFlatL2), smaller distance is better, 
        # but LlamaIndex usually normalizes or returns similarity.
        # Assuming higher is better from LlamaIndex retriever.
        
        results = []
        for cand_id, data in candidate_matches.items():
            # Normalized composite score
            final_score = (data["max_score"] * 0.7) + ((data["sum_score"] / data["count"]) * 0.3)
            results.append({
                "candidate_id": cand_id,
                "candidate_name": data["candidate_name"],
                "score": final_score,
                "matched_chunks": data["matched_chunks"][:3] # Return top 3 snippets
            })

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        
        logger.info(f"Matched {len(results)} candidates using LlamaIndex.")
        return results[:top_k]
