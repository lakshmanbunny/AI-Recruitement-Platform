import hashlib

def compute_context_hash(text: str) -> str:
    """
    Computes a SHA256 hash of the context string to ensure parity between
    the generator and the judge LLMs.
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
