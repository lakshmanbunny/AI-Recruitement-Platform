
import sqlite3
import os

# Path to the SQLite database
DB_PATH = "c:/Users/lakshman.yvs/Desktop/exp/backend/paradigm_ai.db"

def add_column():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists first
        cursor.execute("PRAGMA table_info(interview_sessions)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "interview_score" in columns:
            print("Column 'interview_score' already exists.")
        else:
            print("Adding 'interview_score' column...")
            cursor.execute("ALTER TABLE interview_sessions ADD COLUMN interview_score FLOAT")
            conn.commit()
            print("Column added successfully.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_column()
