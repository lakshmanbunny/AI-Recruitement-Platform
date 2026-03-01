from typing import Dict, List, Any, Optional
from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import BaseRetriever
from config.logging_config import get_logger
from .resume_indexer import ResumeLlamaIndexer

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_INDEX_DIR = os.path.join(PROJECT_ROOT, "backend", "storage", "llama_resume.index")

logger = get_logger(__name__)

class ResumeRAGEvidenceBuilder:
    """
    Builds grounded technical evidence for candidates using LlamaIndex retrieval.
    Replaces full resume text with specific, high-relevance chunks.
    """
    
    def __init__(self, index_dir: str = DEFAULT_INDEX_DIR, top_k: int = 5):
        self.top_k = top_k
        self.indexer = ResumeLlamaIndexer(persist_dir=index_dir)
        try:
            # We want more chunks initially to ensure cross-section diversity
            self.retriever = self.indexer.get_retriever(similarity_top_k=100)
        except Exception as e:
            logger.error(f"[RESUME RAG] Failed to initialize retriever: {str(e)}")
            self.retriever = None

    def build_evidence(self, candidate_id: str, job_description: str) -> Dict[str, Any]:
        """
        Retrieves all relevant chunks for a specific candidate and groups them by section.
        """
        if not self.retriever:
            logger.warning(f"[RESUME RAG] Retriever inactive for {candidate_id}")
            return {"candidate_id": candidate_id, "sections": {}, "raw_chunks": [], "error": "Retriever inactive"}

        logger.info(f"[RESUME RAG EVIDENCE BUILT] Building grounded evidence for {candidate_id}")
        
        try:
            # Retrieve chunks relevant to the JD
            all_nodes = self.retriever.retrieve(job_description)
            
            # Filter specifically for this candidate
            candidate_nodes = [
                node for node in all_nodes 
                if node.node.metadata.get("candidate_id") == candidate_id
            ]
            
            # Sort by score (usually similarity score)
            candidate_nodes.sort(key=lambda x: x.score, reverse=True)
            
            # Use all retrieved chunks for this candidate
            top_nodes = candidate_nodes
            
            evidence = {
                "candidate_id": candidate_id,
                "evidence_summary": f"Retrieved {len(top_nodes)} relevant evidence chunks from candidate resume.",
                "sections": {
                    "skills": [],

                    "experience": [],
                    "projects": [],
                    "education": []
                },
                "raw_chunks": []
            }
            
            for node_with_score in top_nodes:
                node = node_with_score.node
                text = node.get_content()
                section = node.metadata.get("section", "unclassified").lower()
                score = node_with_score.score
                
                # Group by section
                if section in evidence["sections"]:
                    evidence["sections"][section].append(text)
                else:
                    # Fallback for unclassified or dynamic sections
                    if "other" not in evidence["sections"]:
                        evidence["sections"]["other"] = []
                    evidence["sections"]["other"].append(text)
                
                evidence["raw_chunks"].append({
                    "text": text,
                    "section": section,
                    "score": round(float(score), 4)
                })
            
            logger.info(f"[RESUME RAG] Successfully retrieved {len(top_nodes)} chunks for {candidate_id}")
            return evidence

        except Exception as e:
            logger.error(f"[RESUME RAG] Evidence building failed for {candidate_id}: {str(e)}")
            return {
                "candidate_id": candidate_id, 
                "sections": {}, 
                "raw_chunks": [], 
                "error": str(e)
            }
