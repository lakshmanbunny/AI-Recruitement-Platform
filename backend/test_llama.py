import sys
import os
import json

backend_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, "../"))
sys.path.insert(0, project_root)

from app.db.database import SessionLocal
from app.db.models import WoxsenCandidate
from core.llama_indexing.metadata_utils import chunk_resume_sections
from core.utils.semantic_chunker import semantic_chunk

db = SessionLocal()
cand = db.query(WoxsenCandidate).filter(WoxsenCandidate.raw_resume_text.isnot(None)).first()

print(f"Testing Candidate: {cand.name}")

raw_text = cand.raw_resume_text

chunks = chunk_resume_sections({
    "candidate_id": cand.roll_number,
    "name": cand.name,
    "raw_resume_text": raw_text
})

print(f"Chunks generated using exact data: {len(chunks)}")
if chunks:
    print(f"Sample chunk: {chunks[0]}")
else:
    print("Why no chunks?")
    
    from core.utils.markdown_cleaner import clean_markdown
    cleaned = clean_markdown(raw_text)
    print("Cleaned text:", len(cleaned))
    semantic = semantic_chunk(cleaned, chunk_id_prefix="debug")
    print("Semantic chunks:", len(semantic))
    
    from core.utils.chunk_validator import validate_chunk
    for ch in semantic:
        print("Valid:", validate_chunk(ch["content"], "debug"), "len:", len(ch["content"]))

