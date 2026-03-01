import json
import logging
from typing import Dict, Any, List
from google import genai
from google.genai import types
from backend.app.core.config import settings
from langsmith import traceable
from .prompts import ENTERPRISE_RAG_JUDGE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class EnterpriseLLMRAGJudge:
    """
    Single-call LLM RAG Evaluator using Gemini.
    Evaluates:
    1. Faithfulness
    2. Answer Relevance
    3. Hallucination Score
    4. Context Utilization
    """
    
    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.model_name = model_name
        # Using google.genai client for v1 API (Gemini 2.0 Flash)
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        
    @traceable(project_name="RAGAS")
    def evaluate(self, question: str, retrieved_chunks: List[str], answer: str) -> Dict[str, Any]:
        """
        Runs the full 4-metric enterprise RAG evaluation in a single Gemini API call.
        """
        if not retrieved_chunks:
            return self._empty_fail_metrics(reason="No chunks provided for evaluation.")
            
        # Combine all chunks into a single deterministic context string
        context_str = "\n\n---\n\n".join(retrieved_chunks)
        
        # Build the user message strictly according to requirements: NO EXAMPLES
        user_message = f"""QUESTION
{question}

CONTEXT
{context_str}

ANSWER
{answer}
"""
        
        try:
            # We configure the model for JSON output strictly
            logger.info(f"[LLM RAG Judge] Sending eval request for chunk length {len(context_str)}")
            
            import time
            max_retries = 3
            initial_delay = 5
            
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model="gemini-2.5-pro",
                        contents=user_message,
                        config=types.GenerateContentConfig(
                            system_instruction=ENTERPRISE_RAG_JUDGE_SYSTEM_PROMPT,
                            temperature=0.0,
                            response_mime_type="application/json"
                        )
                    )
                    raw_text = response.text
                    break # Success
                except Exception as e:
                    if "429" in str(e) and attempt < max_retries - 1:
                        delay = initial_delay * (2 ** attempt)
                        logger.warning(f"[LLM RAG Judge] Quota hit (429). Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        raise e
            
            try:
                metrics = json.loads(raw_text)
            except json.JSONDecodeError as je:
                 logger.error(f"[LLM RAG Judge] Failed to parse JSON: {je}. Raw output: {raw_text}")
                 return self._empty_fail_metrics(reason="LLM returned invalid JSON.")
            
            # Post-process metrics
            faithfulness = float(metrics.get("faithfulness", 0.0))
            answer_relevance = float(metrics.get("answer_relevance", 0.0))
            hallucination_score = float(metrics.get("hallucination_score", 1.0)) # 1.0 means NO hallucination
            context_utilization = float(metrics.get("context_utilization", 0.0))
            
            # Weighted scoring
            overall_score = (faithfulness * 0.3) + (answer_relevance * 0.3) + (hallucination_score * 0.2) + (context_utilization * 0.2)

            # Determine Health Status
            # CRITICAL: Any metric < 0.5
            # GOOD: faithfulness >= 0.80, relevance >= 0.70, hallucination >= 0.90
            
            if faithfulness < 0.5 or answer_relevance < 0.5 or hallucination_score < 0.5 or context_utilization < 0.5:
                health_status = "CRITICAL"
            elif faithfulness >= 0.80 and answer_relevance >= 0.70 and hallucination_score >= 0.90:
                health_status = "GOOD"
            else:
                health_status = "WARN"
                
            metrics["overall_score"] = overall_score
            metrics["rag_health_status"] = health_status
            
            logger.info(f"[LLM RAG Judge] Eval OK: F:{faithfulness:.2f} R:{answer_relevance:.2f} H:{hallucination_score:.2f} CU:{context_utilization:.2f} -> {health_status}")
            return metrics
            
        except Exception as e:
            logger.error(f"[LLM RAG Judge] Generation failed: {e}")
            return self._empty_fail_metrics(reason=str(e))
            
    def _empty_fail_metrics(self, reason: str = "") -> Dict[str, Any]:
        return {
            "faithfulness": 0.0,
            "answer_relevance": 0.0,
            "hallucination_score": 0.0,
            "context_utilization": 0.0,
            "overall_score": 0.0,
            "rag_health_status": "CRITICAL",
            "explanation": reason
        }
