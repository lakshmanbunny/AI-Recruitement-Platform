from app.db.database import SessionLocal
from app.db import models

def cleanup_jobs():
    db = SessionLocal()
    try:
        # Delete all pending and running LLM and RAG evaluation jobs
        db.query(models.RAGLLMEvalJob).filter(models.RAGLLMEvalJob.status.in_(["PENDING", "RUNNING"])).delete()
        db.query(models.RAGEvaluationJob).filter(models.RAGEvaluationJob.status.in_(["PENDING", "RUNNING"])).delete()
        db.commit()
        print("Successfully cleaned up pending and running jobs.")
    except Exception as e:
        print(f"Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_jobs()
