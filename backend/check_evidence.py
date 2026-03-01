from app.db.database import SessionLocal
from app.db import models
import json

def check_screening_evidence(candidate_id: int):
    db = SessionLocal()
    try:
        res = db.query(models.ScreeningResult).filter(models.ScreeningResult.candidate_id == candidate_id).first()
        if res:
            print(f"Candidate ID: {candidate_id}")
            print(f"AI Evidence JSON: {res.ai_evidence_json}")
            print(f"Justification: {res.justification_json}")
        else:
            print(f"No screening result found for candidate {candidate_id}")
    finally:
        db.close()

if __name__ == "__main__":
    check_screening_evidence(1)
    print("-" * 20)
    check_screening_evidence(99)
