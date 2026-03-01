import logging

logger = logging.getLogger(__name__)

def validate_chunk(chunk_text: str, chunk_id: str) -> bool:
    """
    Validates a chunk for unclosed fences, minimum length, and valid punctuation.
    """
    if not chunk_text or len(chunk_text.strip()) < 40:
        logger.warning(f"[CHUNK_VALIDATION_FAIL] {chunk_id} - Too short or empty")
        return False
        
    # Check for unclosed backticks
    if chunk_text.count("```") % 2 != 0:
        logger.warning(f"[CHUNK_VALIDATION_FAIL] {chunk_id} - Unclosed triple backticks")
        return False
        
    if chunk_text.count("`") % 2 != 0:
        logger.warning(f"[CHUNK_VALIDATION_FAIL] {chunk_id} - Unclosed single backticks")
        return False
        
    # Check if ends with typical sentence punctuation (or list item newline)
    if not re.search(r'[.!?\n\r]$', chunk_text.strip()):
        logger.info(f"[CHUNK_VALIDATION_PASS_WITH_WARNING] {chunk_id} - Doesn't end with typical punctuation but allowing.")
        
    logger.info(f"[CHUNK_VALIDATION_PASS] {chunk_id}")
    return True

import re # Ensure re is available
