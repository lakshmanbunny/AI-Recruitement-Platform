import sqlite3

def migrate():
    try:
        conn = sqlite3.connect('paradigm_ai.db')
        cursor = conn.cursor()
        
        # Migrating screening_results
        cursor.execute('PRAGMA table_info(screening_results)')
        cols = [c[1] for c in cursor.fetchall()]
        print(f"Existing columns in screening_results: {cols}")
        
        new_cols = [
            ('repo_count', 'INTEGER'),
            ('ai_projects', 'INTEGER'),
            ('hr_decision', 'TEXT'),
            ('hr_notes', 'TEXT'),
            ('repos_json', 'TEXT'),
            ('interview_readiness_json', 'TEXT'),
            ('skeptic_analysis_json', 'TEXT'),
            ('final_synthesized_decision_json', 'TEXT'),
            ('ai_evidence_json', 'TEXT'),
            ('justification_json', 'TEXT')
        ]
        
        for col_name, col_type in new_cols:
            if col_name not in cols:
                cursor.execute(f'ALTER TABLE screening_results ADD COLUMN {col_name} {col_type}')
                print(f"Added {col_name} to screening_results")
            
        # Migrating interview_sessions
        cursor.execute('PRAGMA table_info(interview_sessions)')
        cols = [c[1] for c in cursor.fetchall()]
        print(f"Existing columns in interview_sessions: {cols}")
        
        missing_interview_cols = [
            ('job_id', 'INTEGER'),
            ('questions_json', 'TEXT'),
            ('answers_json', 'TEXT'),
            ('followups_json', 'TEXT'),
            ('transcript_summary', 'TEXT'),
            ('final_scores_json', 'TEXT')
        ]
        
        for col_name, col_type in missing_interview_cols:
            if col_name not in cols:
                cursor.execute(f'ALTER TABLE interview_sessions ADD COLUMN {col_name} {col_type}')
                print(f"Added {col_name} to interview_sessions")
                
        conn.commit()
        conn.close()
        print("Migration completed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
