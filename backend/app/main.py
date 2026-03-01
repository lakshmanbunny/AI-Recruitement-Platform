import os
import sys

# Add the project root and backend_dir to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
project_root = os.path.abspath(os.path.join(backend_dir, "../"))

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.init_db import init_db

# Initialize database first before importing routes/services that depend on it
init_db()

from app.api.routes import router
from app.interview.routes import router as interview_router

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import time

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#     start_time = time.time()
#     response = await call_next(request)
#     duration = time.time() - start_time
#     print(f"--- [API] {request.method} {request.url.path} - {response.status_code} ({duration:.2f}s) ---")
#     return response


# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix=settings.API_V1_STR)
app.include_router(interview_router, prefix=f"{settings.API_V1_STR}/interview")

@app.get("/")
async def root():
    return {"message": "Welcome to AI Recruitment Screening API", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
