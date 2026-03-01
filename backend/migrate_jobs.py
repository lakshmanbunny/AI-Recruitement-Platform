"""
Migration to add the rag_evaluation_jobs table.
"""
import sqlite3
import os

DB_FILES = ["recruitment.db", "paradigm_ai.db"]

CREATE_RAG_JOBS = """
CREATE TABLE IF NOT EXISTS rag_evaluation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    status TEXT DEFAULT 'PENDING',
    metrics_json TEXT,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
)
"""

for db_path in DB_FILES:
    if not os.path.exists(db_path):
        print(f"[SKIP] {db_path} not found")
        continue

    print(f"\n=== Migrating {db_path} ===")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute(CREATE_RAG_JOBS)
    print("  -> rag_evaluation_jobs table ensured")

    conn.commit()
    conn.close()
    print(f"  Done: {db_path}")

print("\nJob queue migration complete.")
