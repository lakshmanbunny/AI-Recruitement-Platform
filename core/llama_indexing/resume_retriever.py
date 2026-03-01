from config.logging_config import get_logger
from .resume_indexer import ResumeLlamaIndexer, DEFAULT_INDEX_DIR
from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilters

logger = get_logger(__name__)

class ResumeHybridRetriever:
    def __init__(self, index_dir=DEFAULT_INDEX_DIR):
        self.indexer = ResumeLlamaIndexer(persist_dir=index_dir)

    def retrieve_candidate_chunks(self, job_description: str, candidate_email: str, top_k=50):
        """
        Whole-Candidate Retrieval: Queries the vector DB using a strict
        exact match filter on the candidate_email to guarantee no chunk starvation.
        """
        # 1. Apply Strict Metadata Filtration
        filters = MetadataFilters(
            filters=[ExactMatchFilter(key="candidate_email", value=candidate_email)]
        )
        
        # 2. Get Retriever with high top_k to return ALL of their sections
        try:
            # We must ensure the retriever includes embeddings so that mathematical coverage works downstream
            retriever = self.indexer.get_retriever(similarity_top_k=top_k, filters=filters)
        except Exception as e:
            logger.error(f"[LLAMA RETRIEVAL ERROR] Could not initialize retriever: {e}")
            return []
            
        logger.info(f"[LLAMA RETRIEVAL ACTIVE] Performing isolated search for: {candidate_email}")
        
        # 3. Retrieve chunks 
        try:
            nodes = retriever.retrieve(job_description)
            
            results = []
            for node_with_score in nodes:
                results.append({
                    "text": node_with_score.node.get_content(),
                    "metadata": node_with_score.node.metadata, # ◄ Included for evaluator
                    "section": node_with_score.node.metadata.get("section", "Unknown"),
                    "score": node_with_score.score,
                    "embedding": node_with_score.node.embedding
                })
                
            # Results are inherently returned sorted by cosine similarity
            return results
        except Exception as e:
            logger.error(f"[LLAMA RETRIEVAL ERROR] Searching for {candidate_email} failed: {e}")
            return []
