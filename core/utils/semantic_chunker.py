import re
from typing import List, Dict

def semantic_chunk(text: str, chunk_id_prefix: str = "CHUNK", max_len: int = 800) -> List[Dict]:
    """
    Splits text by markdown headings or paragraphs.
    Caps chunks at `max_len` and truncates cleanly at the last full sentence.
    """
    if not text:
        return []

    # Split by headings
    sections = re.split(r'(?=\n##)', "\n" + text)
    chunks = []
    
    for idx, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
            
        # Extract title if present
        title_match = re.match(r'^#+\s+(.*)', section)
        title = title_match.group(1).strip() if title_match else "General"
        
        # Clean section header from body for length measuring
        body = re.sub(r'^#+.*?\n', '', section, count=1).strip()
        
        if len(body) > max_len:
            # Truncate at last full sentence
            truncated = body[:max_len]
            if "." in truncated:
                body = truncated.rsplit(".", 1)[0] + "."
            else:
                body = truncated # Fallback if no sentence boundary
                
        chunks.append({
            "chunk_id": f"{chunk_id_prefix}_{idx+1}",
            "section_title": title,
            "content": body,
            "char_length": len(body)
        })
        
    return chunks
