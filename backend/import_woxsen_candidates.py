import os
import sys
import pandas as pd

# Setup paths so we can import backend models
backend_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, "../"))
if backend_dir not in sys.path: sys.path.insert(0, backend_dir)
if project_root not in sys.path: sys.path.insert(0, project_root)

from app.db.database import SessionLocal, engine
from app.db import models

# Ensure the new table is created in the database
models.Base.metadata.create_all(bind=engine)

def import_candidates():
    excel_file = os.path.join(project_root, "ParadigmIT.xlsx")
    resumes_dir = os.path.join(backend_dir, "data", "resumes")
    
    print(f"Reading {excel_file}...")
    try:
        df = pd.read_excel(excel_file)
        
        db = SessionLocal()
        
        imported_count = 0
        skipped_count = 0
        
        for _, row in df.iterrows():
            roll_number = str(row.get('Roll Number', '')).strip()
            if not roll_number or roll_number.lower() == 'nan':
                continue
                
            # Check if this roll number already exists
            existing = db.query(models.WoxsenCandidate).filter(models.WoxsenCandidate.roll_number == roll_number).first()
            if existing:
                skipped_count += 1
                continue
                
            name = str(row.get('Full Name', '')).strip()
            email = str(row.get('Email ID (Personal)', '')).strip()
            if email.lower() == 'nan':
                email = f"{roll_number.lower()}@woxsen.edu.in"
                
            github = str(row.get('Git-Hub Account URL', '')).strip()
            linkedin = str(row.get('Linkedin-Account URL', '')).strip()
            
            if github.lower() == 'nan' or not github: github = None
            if linkedin.lower() == 'nan' or not linkedin: linkedin = None
            
            # Check if email exists
            existing_email = db.query(models.WoxsenCandidate).filter(models.WoxsenCandidate.email == email).first()
            if existing_email:
                print(f"⚠️ Skipping duplicate email: {email} for roll {roll_number}")
                skipped_count += 1
                continue

            # Check if we downloaded their resume
            resume_path = os.path.join(resumes_dir, f"{roll_number}.pdf")
            final_resume_path = resume_path if os.path.exists(resume_path) else None
            
            new_candidate = models.WoxsenCandidate(
                roll_number=roll_number,
                name=name,
                email=email,
                github_url=github,
                linkedin_url=linkedin,
                resume_file_path=final_resume_path
            )
            
            try:
                db.add(new_candidate)
                db.commit()
                imported_count += 1
            except Exception as row_e:
                db.rollback()
                print(f"⚠️ Error importing {roll_number}: {row_e}")
                skipped_count += 1
            
        print(f"\n✅ Successfully imported {imported_count} new candidates into 'woxsen_candidates' table.")
        print(f"⏭️  Skipped {skipped_count} existing candidates.")
        
    except Exception as e:
        print(f"❌ Error during import: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    import_candidates()
