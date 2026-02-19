import numpy as np

def cosine_similarity(v1, v2):
    """
    Calculate the cosine similarity between two vectors.
    """
    a = np.array(v1)
    b = np.array(v2)
    
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
        
    return float(dot_product / (norm_a * norm_b))
