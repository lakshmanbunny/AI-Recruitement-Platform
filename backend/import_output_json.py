import sys, os, json
backend_dir = os.path.abspath('.')
sys.path.insert(0, backend_dir)
from app.db.database import SessionLocal
from app.db import models

def main():
    db = SessionLocal()
    with open("output.json", "r", encoding="utf-8") as f:
        completed = json.load(f)
        
    updated_count = 0
    for item in completed:
        source_file = item.get("source_file")
        if source_file:
            roll_number = source_file.split(".")[0].upper()
            candidate = db.query(models.WoxsenCandidate).filter(models.WoxsenCandidate.roll_number == roll_number).first()
            if candidate:
                candidate.raw_resume_text = json.dumps(item, ensure_ascii=False)
                updated_count += 1
                
    db.commit()
    print(f"✅ Successfully updated {updated_count} candidates in the database.")
    db.close()

if __name__ == "__main__":
    main()
