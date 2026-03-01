"""
Database cleanup script for 3-Stage Funnel migration.
Clears all old evaluation/screening data while preserving:
  - woxsen_candidates (source data)
  - candidates (identity data)
  - job_descriptions (JD data)
"""
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import SessionLocal, engine
from app.db import models

def cleanup():
    db = SessionLocal()
    try:
        # Tables to CLEAR (order matters due to foreign keys)
        tables_to_clear = [
            "rag_llm_eval_jobs",
            "rag_llm_metrics",
            "rag_evaluation_jobs",
            "rag_evaluation_results",
            "rag_retrieval_metrics",
            "rag_metrics",
            "interview_sessions",
            "screening_results",
        ]

        # Show current counts
        print("=" * 60)
        print("BEFORE CLEANUP")
        print("=" * 60)
        
        woxsen_count = db.query(models.WoxsenCandidate).count()
        cand_count = db.query(models.Candidate).count()
        jd_count = db.query(models.JobDescription).count()
        screening_count = db.query(models.ScreeningResult).count()
        rag_metric_count = db.query(models.RAGMetric).count()
        rag_retrieval_count = db.query(models.RAGRetrievalMetric).count()
        rag_eval_result_count = db.query(models.RAGEvaluationResult).count()
        rag_eval_job_count = db.query(models.RAGEvaluationJob).count()
        rag_llm_metric_count = db.query(models.RAGLLMMetric).count()
        rag_llm_job_count = db.query(models.RAGLLMEvalJob).count()
        
        print(f"  woxsen_candidates:     {woxsen_count} (KEEP)")
        print(f"  candidates:            {cand_count} (KEEP)")
        print(f"  job_descriptions:      {jd_count} (KEEP)")
        print(f"  screening_results:     {screening_count} (CLEAR)")
        print(f"  rag_metrics:           {rag_metric_count} (CLEAR)")
        print(f"  rag_retrieval_metrics: {rag_retrieval_count} (CLEAR)")
        print(f"  rag_evaluation_results:{rag_eval_result_count} (CLEAR)")
        print(f"  rag_evaluation_jobs:   {rag_eval_job_count} (CLEAR)")
        print(f"  rag_llm_metrics:       {rag_llm_metric_count} (CLEAR)")
        print(f"  rag_llm_eval_jobs:     {rag_llm_job_count} (CLEAR)")
        
        # Clear tables
        print("\n" + "=" * 60)
        print("CLEARING EVALUATION TABLES...")
        print("=" * 60)
        
        for table_name in tables_to_clear:
            try:
                result = db.execute(models.Base.metadata.tables[table_name].delete())
                db.commit()
                print(f"  ✅ Cleared: {table_name} ({result.rowcount} rows)")
            except Exception as e:
                db.rollback()
                print(f"  ❌ Error clearing {table_name}: {e}")

        # Verify
        print("\n" + "=" * 60)
        print("AFTER CLEANUP")
        print("=" * 60)
        print(f"  woxsen_candidates:     {db.query(models.WoxsenCandidate).count()} (preserved)")
        print(f"  candidates:            {db.query(models.Candidate).count()} (preserved)")
        print(f"  job_descriptions:      {db.query(models.JobDescription).count()} (preserved)")
        print(f"  screening_results:     {db.query(models.ScreeningResult).count()}")
        print(f"  rag_metrics:           {db.query(models.RAGMetric).count()}")
        print(f"  rag_retrieval_metrics: {db.query(models.RAGRetrievalMetric).count()}")
        print(f"  rag_evaluation_results:{db.query(models.RAGEvaluationResult).count()}")
        print(f"  rag_evaluation_jobs:   {db.query(models.RAGEvaluationJob).count()}")
        print(f"  rag_llm_metrics:       {db.query(models.RAGLLMMetric).count()}")
        print(f"  rag_llm_eval_jobs:     {db.query(models.RAGLLMEvalJob).count()}")
        
        print("\n✅ Database cleanup complete! Ready for 3-Stage Funnel.")
        
    finally:
        db.close()

if __name__ == "__main__":
    cleanup()
