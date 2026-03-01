import json
import re
from core.utils.markdown_cleaner import clean_markdown
from core.utils.semantic_chunker import semantic_chunk
from core.utils.chunk_validator import validate_chunk

def chunk_resume_sections(resume_dict):
    """
    Splits a resume into semantic chunks.
    Dynamically parses the JSON sections and creates exactly ONE chunk per section.
    """
    candidate_id = resume_dict.get("candidate_id", "Unknown")
    candidate_name = resume_dict.get("name", "Unknown")
    candidate_email = str(resume_dict.get("email", "Unknown")).strip().lower() # ◄ ROBUST UNIQUE IDENTIFIER

    
    chunks = []
    raw_text = resume_dict.get("raw_resume_text", "")
    
    # NEW APPROACH: Parse the dynamic JSON array and chunk by exactly one section = one chunk.
    try:
        data = json.loads(raw_text)
        sections = data.get("sections", [])
        if sections:
            for idx, section in enumerate(sections):
                heading = section.get("heading", f"Section_{idx}")
                content = section.get("content", "")
                if not content.strip(): 
                    continue
                
                # Format to give the embedding model maximum semantic context
                chunk_text = f"Candidate: {candidate_name}\nSection: {heading}\n\n{content}"
                
                chunk_id = f"{candidate_id}-{heading.replace(' ', '')[:10]}-{idx}"
                metadata = {
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_name,
                    "candidate_email": candidate_email, # ◄ INJECTED UNIQUE IDENTIFIER
                    "section": heading,
                    "chunk_id": chunk_id
                }
                chunks.append({
                    "text": chunk_text,
                    "metadata": metadata
                })
            return chunks
    except Exception:
        pass # Fallback to legacy string processing below if not JSON

    # LEGACY FALLBACK
    def process_section(text, section_name):
        if not text: return
        cleaned = clean_markdown(text)
        semantic_chunks = semantic_chunk(cleaned, chunk_id_prefix=f"{candidate_id[:4]}_{section_name[:3]}")
        
        for idx, s_chunk in enumerate(semantic_chunks):
            chunk_content = s_chunk["content"]
            chunk_id = f"{candidate_id}-{section_name}-{idx}"
            if validate_chunk(chunk_content, chunk_id):
                metadata = {
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_name,
                    "section": section_name,
                    "chunk_id": chunk_id
                }
                chunks.append({
                    "text": chunk_content,
                    "metadata": metadata
                })

    process_section(resume_dict.get("skills", ""), "Skills")
    process_section(resume_dict.get("projects", ""), "Projects")
    process_section(resume_dict.get("experience", ""), "Experience")
    process_section(resume_dict.get("education", ""), "Education")
    process_section(raw_text, "RawResume")

    return chunks
