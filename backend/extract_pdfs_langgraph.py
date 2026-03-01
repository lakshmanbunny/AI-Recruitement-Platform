import sys
import os
import glob
import json
import asyncio
from typing import TypedDict, List, Dict, Any

# Setup paths so we can import backend models
backend_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, "../"))
if backend_dir not in sys.path: sys.path.insert(0, backend_dir)
if project_root not in sys.path: sys.path.insert(0, project_root)

from app.db.database import SessionLocal
from app.db import models

# LangChain / LangGraph imports
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# ==============================================================================
# 0. CONFIGURATION
# ==============================================================================
# Set your GCP Project ID and Location explicitly, or ensure they are set in your environment
# os.environ["GOOGLE_CLOUD_PROJECT"] = "your-gcp-project-id"
# os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

# Directory containing the PDFs
PDF_DIRECTORY = os.path.join(os.path.dirname(__file__), "data", "resumes")
# Output file for the parsed JSON
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "output.json")

# Limits concurrency to 5 simultaneous processing tasks
CONCURRENCY_LIMIT = 5

# ==============================================================================
# 1. STATE CONFIGURATION & PYDANTIC SCHEMA
# ==============================================================================

class FailedFile(TypedDict):
    """Structure for logging failed unparsed files."""
    filename: str
    error: str

class ExtractionState(TypedDict):
    """The graph state tracking the files and results."""
    pending_files: List[str]
    completed_results: List[Dict[str, Any]]
    failed_files: List[FailedFile]

class ResumeSection(BaseModel):
    """A section within a resume."""
    heading: str = Field(description="The heading of the section, e.g., 'Education', 'Experience', 'Skills'")
    content: str = Field(description="The text content within this section. Preserve all details.")

class ResumeData(BaseModel):
    """The structured output format for a single resume."""
    document_title: str = Field(description="The name of the candidate or document title.")
    sections: List[ResumeSection] = Field(description="The distinct sections of the resume.")

# ==============================================================================
# 2. MODEL CONFIGURATION
# ==============================================================================

# Initialize the ChatGoogleGenerativeAI model
# We use gemini-2.0-flash, enable async backoff, and enforce JSON output
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    max_retries=5, # Exponential backoff enabled by default in langchain for retries
    temperature=0.0 # Low temperature for accurate extraction
)

# Bind the Pydantic schema to strictly format the output
structured_llm = llm.with_structured_output(ResumeData)

# ==============================================================================
# 3. GRAPH NODES (APPLICATION LOGIC)
# ==============================================================================

# Create an asyncio Semaphore to strictly limit concurrency across our batch
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

async def process_single_pdf(file_path: str) -> dict:
    """
    Asynchronously processes a single PDF document.
    Wraps the LLM call with a semaphore for concurrency limiting and a try/except for error handling.
    """
    filename = os.path.basename(file_path)
    
    # Wait for a slot in the semaphore before proceeding
    async with semaphore:
        try:
            print(f"🔄 Processing: {filename}")
            
            # Read the PDF file bytes
            with open(file_path, "rb") as f:
                pdf_data = f.read()
                
            # Create a multimodal message for GenAI to process the PDF natively
            import base64
            b64_pdf = base64.b64encode(pdf_data).decode()
            
            message = HumanMessage(
                content=[
                    {"type": "text", "text": "Extract the contents of this resume into the structured JSON format provided."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:application/pdf;base64,{b64_pdf}"
                        }
                    }
                ]
            )
            
            # Call the LLM (which is bound to our Pydantic schema)
            response = await structured_llm.ainvoke([message])
            
            print(f"✅ Success: {filename}")
            return {
                "status": "success",
                "filename": filename,
                "data": response.model_dump() # Convert Pydantic object back to dict
            }
            
        except Exception as e:
            print(f"❌ Failed: {filename} - Error: {str(e)}")
            return {
                "status": "error",
                "filename": filename,
                "error": str(e)
            }

async def extract_all_node(state: ExtractionState) -> ExtractionState:
    """
    The main LangGraph node that takes the pending files, 
    processes them concurrently (with limits), and updates the state.
    """
    pending = state.get("pending_files", [])
    
    if not pending:
         return state # Nothing to do
    
    print(f"\n🚀 Starting batch extraction of {len(pending)} files with concurrency {CONCURRENCY_LIMIT}...\n")
    
    # Create asyncio tasks for all files
    # The semaphore inside `process_single_pdf` ensures only 5 run simultaneously
    tasks = [process_single_pdf(file_path) for file_path in pending]
    
    # Wait for all files to finish (success or fail)
    results = await asyncio.gather(*tasks)
    
    # Segregate results into successes and failures
    completed = state.get("completed_results", [])
    failed = state.get("failed_files", [])
    
    for r in results:
        if r["status"] == "success":
            # Add the filename to the data for tracking
            data_dict = r["data"]
            data_dict["source_file"] = r["filename"]
            completed.append(data_dict)
        else:
            failed.append({
                "filename": r["filename"],
                "error": r["error"]
            })
            
    # Update the state, clearing pending files indicating they are all processed
    return {
        "pending_files": [],
        "completed_results": completed,
        "failed_files": failed
    }

# ==============================================================================
# 4. GRAPH COMPILATION & EXECUTION
# ==============================================================================

def build_graph():
    """Builds and compiles the StateGraph."""
    # Define the graph with our typed State
    workflow = StateGraph(ExtractionState)
    
    # Add our single node representing the batch extraction process
    workflow.add_node("extract_pdfs", extract_all_node)
    
    # Define the edges (START -> extract -> END)
    workflow.add_edge(START, "extract_pdfs")
    workflow.add_edge("extract_pdfs", END)
    
    # Compile and return the executable graph
    return workflow.compile()

async def main():
    """Main execution block."""
    print("--- 📄 PDF Resume Extractor Initialization ---")
    
    # 1. Discover all PDF files
    if not os.path.exists(PDF_DIRECTORY):
        print(f"Directory not found: {PDF_DIRECTORY}")
        return
        
    pdf_files = glob.glob(os.path.join(PDF_DIRECTORY, "*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {PDF_DIRECTORY}")
        return
        
    print(f"Found {len(pdf_files)} PDF files to process.")
    
    # Process all files
    test_pdf_files = pdf_files
    
    # 2. Build the Graph
    app = build_graph()
    
    # 3. Initialize the State
    initial_state = {
        "pending_files": test_pdf_files,
        "completed_results": [],
        "failed_files": []
    }
    
    # 4. Invoke the Graph Asynchronously
    print("Invoking LangGraph application...\n")
    final_state = await app.ainvoke(initial_state)
    
    # 5. Save the Results
    completed = final_state.get("completed_results", [])
    failed = final_state.get("failed_files", [])
    
    print(f"\n--- 🏁 Extraction Complete ---")
    print(f"Successes: {len(completed)}")
    print(f"Failures:  {len(failed)}")
    
    # Save the successful extractions to output.json and the database
    if completed:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(completed, f, indent=4, ensure_ascii=False)
        print(f"💾 Saved structured data to: {OUTPUT_FILE}")
        
        print("\n💾 Updating database with extracted structured text...")
        db = SessionLocal()
        try:
            updated_count = 0
            for item in completed:
                source_file = item.get("source_file")
                if source_file:
                    roll_number = source_file.split(".")[0].upper()
                    candidate = db.query(models.WoxsenCandidate).filter(models.WoxsenCandidate.roll_number == roll_number).first()
                    if candidate:
                        candidate.raw_resume_text = json.dumps(item, ensure_ascii=False)
                        updated_count += 1
            db.commit()
            print(f"✅ Successfully updated {updated_count} candidates in the database.")
        except Exception as e:
            print(f"❌ Error updating database: {e}")
            db.rollback()
        finally:
            db.close()
        
    # If there were failures, log them out
    if failed:
        print("\n⚠️ Failed Files:")
        for fail in failed:
            print(f"  - {fail.get('filename')}: {fail.get('error')}")

if __name__ == "__main__":
    # Ensure dependencies are installed:
    # pip install langgraph langchain-google-vertexai pydantic
    
    # Run the main async loop
    asyncio.run(main())
