"""
One-time SQLite migration:
  - Adds recall_score, relevancy_score to rag_metrics
  - Creates rag_evaluation_results table
"""
import sqlite3
import os

DB_FILES = ["recruitment.db", "paradigm_ai.db"]

CREATE_RAG_EVAL = """
CREATE TABLE IF NOT EXISTS rag_evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    jd_hash TEXT,
    precision FLOAT DEFAULT 0.0,
    recall FLOAT DEFAULT 0.0,
    faithfulness FLOAT DEFAULT 0.0,
    relevancy FLOAT DEFAULT 0.0,
    overall_score FLOAT DEFAULT 0.0,
    health_status TEXT DEFAULT 'CRITICAL',
    gate_decision TEXT DEFAULT 'BLOCK',
    failure_reasons_json TEXT,
    gating_reason TEXT,
    override_triggered BOOLEAN DEFAULT 0,
    override_reason TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

for db_path in DB_FILES:
    if not os.path.exists(db_path):
        print(f"[SKIP] {db_path} not found")
        continue

    print(f"\n=== Migrating {db_path} ===")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in c.fetchall()]
    print(f"Tables: {tables}")

    if "rag_metrics" in tables:
        c.execute("PRAGMA table_info(rag_metrics)")
        cols = [row[1] for row in c.fetchall()]
        print(f"rag_metrics columns: {cols}")

        if "recall_score" not in cols:
            c.execute("ALTER TABLE rag_metrics ADD COLUMN recall_score FLOAT DEFAULT 0.0")
            print("  -> Added recall_score")
        else:
            print("  -> recall_score already exists")

        if "relevancy_score" not in cols:
            c.execute("ALTER TABLE rag_metrics ADD COLUMN relevancy_score FLOAT DEFAULT 0.0")
            print("  -> Added relevancy_score")
        else:
            print("  -> relevancy_score already exists")
    else:
        print("  [SKIP] rag_metrics table not found in this DB")

    c.execute(CREATE_RAG_EVAL)
    print("  -> rag_evaluation_results table ensured")

    conn.commit()
    conn.close()
    print(f"  Done: {db_path}")

print("\nMigration complete.")
