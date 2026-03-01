import sqlite3
import os

db_path = "paradigm_ai.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current columns
    cursor.execute("PRAGMA table_info(rag_retrieval_metrics)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Current columns in rag_retrieval_metrics: {columns}")
    
    if "diversity" not in columns:
        print("Adding 'diversity' column...")
        cursor.execute("ALTER TABLE rag_retrieval_metrics ADD COLUMN diversity FLOAT DEFAULT 0.0")
    
    if "density" not in columns:
        print("Adding 'density' column...")
        cursor.execute("ALTER TABLE rag_retrieval_metrics ADD COLUMN density FLOAT DEFAULT 0.0")
        
    conn.commit()
    print("✅ Schema sync complete.")
    conn.close()
else:
    print("❌ Database not found at", db_path)
