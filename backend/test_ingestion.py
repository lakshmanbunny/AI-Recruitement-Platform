import sys
import os

# Add backend and project root to sys.path
backend_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, "../"))

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("Path setup complete.")
from app.services.data_ingestion import data_ingestion_service
print("Imported data_ingestion_service.")
excel_file = r"c:\Users\lakshman.yvs\Desktop\exp\ParadigmIT.xlsx"

print(f"Parsing {excel_file}...")
try:
    candidates = data_ingestion_service.parse_file(excel_file)
    print(f"Parsed {len(candidates)} candidates.")
    
    for idx, c in enumerate(candidates[:2]):  # print first 2
        print(f"\nCandidate {idx+1}: {c['name']} (ID: {c['candidate_id']})")
        print(f"Email: {c.get('email', '')}")
        print(f"Links: {c.get('links', {})}")
        resume_preview = c.get('raw_resume_text', '')[:150].replace('\n', ' ')
        print(f"Resume text preview (150 chars): {resume_preview}...")
except Exception as e:
    print(f"Error: {e}")
