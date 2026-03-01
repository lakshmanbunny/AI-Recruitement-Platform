import sys
import os

# Add backend and project root to sys.path
backend_dir = os.path.abspath(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

project_root = os.path.abspath(os.path.join(backend_dir, "../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("--- Start Import Bisect ---")

try:
    print("Importing fastapi...")
    import fastapi
    print("OK")
    
    print("Importing uvicorn...")
    import uvicorn
    print("OK")
    
    print("Importing faiss...")
    import faiss
    print("OK - FAISS")

    print("Importing llama_index.core...")
    import llama_index.core
    print("OK - llama_index.core")

    print("Importing llama_index.embeddings.gemini...")
    import llama_index.embeddings.gemini
    print("OK - llama_index.embeddings.gemini")
    
    print("Importing langchain...")
    import langchain
    print("OK")
    
    print("Importing langgraph...")
    import langgraph
    print("OK")
    
    print("Importing google.generativeai...")
    import google.generativeai
    print("OK")
    
    print("Importing sqlalchemy...")
    import sqlalchemy
    print("OK")
    
    print("Importing pandas...")
    import pandas
    print("OK")

    print("Importing faiss...")
    import faiss
    print("OK")

    print("Importing llama_index.core...")
    import llama_index.core
    print("OK")

    print("Importing llama_index.embeddings.gemini...")
    import llama_index.embeddings.gemini
    print("OK")
    
    print("Importing app.db.init_db...")
    from app.db.init_db import init_db
    print("OK")

    print("Running init_db()...")
    init_db()
    print("OK")

    print("Importing app.api.routes...")
    import app.api.routes
    print("OK")

    print("Importing app.interview.routes...")
    import app.interview.routes
    print("OK")

    print("--- All OK ---")
except Exception as e:
    print(f"FAILED with error: {e}")
except BaseException as e:
    print(f"CRITICAL FAILED with base error: {type(e)}")
