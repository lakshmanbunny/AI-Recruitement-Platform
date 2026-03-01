import os
import sys

# Add root folder to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from app.db.database import engine, Base
from app.db.models import RAGLLMMetric, RAGLLMEvalJob

def migrate():
    print(f"Migrating database at: {engine.url}")
    
    # Create the new tables
    RAGLLMMetric.__table__.create(bind=engine, checkfirst=True)
    RAGLLMEvalJob.__table__.create(bind=engine, checkfirst=True)
    
    print("Migration complete. rag_llm_metrics and rag_llm_eval_jobs tables created/verified.")

if __name__ == "__main__":
    migrate()
