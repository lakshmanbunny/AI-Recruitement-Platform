import os
import sqlite3

def run_migration():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(backend_dir, "paradigm_ai.db")
    
    print(f"Migrating database at: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rag_retrieval_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER REFERENCES candidates(id),
                precision FLOAT DEFAULT 0.0,
                recall FLOAT DEFAULT 0.0,
                coverage FLOAT DEFAULT 0.0,
                similarity FLOAT DEFAULT 0.0,
                overall_score FLOAT DEFAULT 0.0,
                rag_health_status VARCHAR DEFAULT 'CRITICAL',
                evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_rag_retrieval_metrics_id ON rag_retrieval_metrics (id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_rag_retrieval_metrics_candidate_id ON rag_retrieval_metrics (candidate_id)
        ''')
        
        print("Migration complete. rag_retrieval_metrics table created.")
        
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.commit()
        conn.close()

if __name__ == "__main__":
    run_migration()
