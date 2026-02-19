# Technical Implementation Details 🛠️

This document provides a deep dive into the architecture, agentic workflows, and internal logic of the AI Recruitment Intelligence Platform.

## 🧠 LangGraph Workflow Orchestration

The platform uses **LangGraph** to manage a complex, stateful multi-agent workflow. Each step in the recruitment process is a distinct node in the graph:

1.  **Retrieve Candidates Node**: 
    - Loads sample resumes and calculates semantic similarity to the Job Description using **FAISS** and Google Gemini embeddings.
    - Scales scores to a normalized 0-100 range.
2.  **GitHub Validation Node**:
    - Analyzes candidate GitHub profiles to verify presence, repo count, and technical activity levels.
3.  **Unified Candidate Evaluation Node**:
    - Combines semantic scores with technical audit data to provide a holistic "Intelligence" score.
4.  **Interview Readiness Audit Node**:
    - Performs a deep-dive analysis of the candidate's fit for the specific role requirements.
5.  **Skeptic Analysis Node**:
    - A specialized adversarial agent tasked with finding vulnerabilities, skill gaps, or potential "over-hiring" risks.
6.  **Final Synthesized Decision Node**:
    - Aggregates all agent insights into a structured hiring consensus (Approve, Hold, or Reject).

## 🤖 Specialized AI Agents

### 1. The Screening Agent
- **Purpose**: Fast, semantic screening.
- **Implementation**: Uses `llm_service.unified_candidate_evaluation` with few-shot prompting to categorize and score resumes.

### 2. The AI Skeptic
- **Purpose**: Minimize hiring mistakes by playing devil's advocate.
- **Implementation**: Analyzes data for contradictions or missing evidence, producing "Major Concerns" and "Hidden Risks" sections in the dashboard.

### 3. The Decision Synthesizer
- **Purpose**: Final consensus reached after weighing both positive evidence and skeptic warnings.
- **Implementation**: Uses a complex synthesis prompt to generate the "Executive Synthesis" seen in the Results UI.

## 📡 AI Interviewer (LiveKit Integration)

The `agent/interviewer.py` implements a real-time voice agent:
- **STT**: Deepgram
- **TTS**: ElevenLabs
- **LLM**: Gemini 2.0 Flash / 1.5 Flash
- **Logic**: Greets the candidate (candidate id 'C001' or similar), reads their background and the JD, and conducts a conversational screening interview.

## 📊 Data Persistence & Scoring

- **Database**: SQLite (`paradigm_ai.db`) using SQLAlchemy ORM.
- **Schema**:
    - `candidates`: Basic profile and metadata.
    - `screening_results`: Full JSON blob of all agent evaluations.
    - `job_descriptions`: Tracks the current active job target.
    - `interview_sessions`: Logs scores and transcripts from real-time interviews.
- **Scoring Normalization**:
    - Scores are consistently scaled to 0-100 across both backend nodes and frontend display components to ensure UX readability.

## 📦 Dependencies & Requirements

### Python Dependencies
See `backend/requirements.txt`:
- `langgraph`: For DAG workflow management.
- `google-generativeai`: Primary LLM engine.
- `faiss-cpu`: Efficient vector retrieval.
- `fastapi`: High-performance API layer.

### Frontend Dependencies
See `frontend/package.json`:
- `react-router-dom`: SPA navigation.
- `@livekit/components-react`: Real-time media handling.
- `lucide-react`: High-quality vector iconography.
- `tailwindcss`: Utility-first styling with modern aesthetics.

## 🛠️ Artifacts & Logs
- `agent_debug.log`: Detailed internal traces of agent thought processes.
- Vector indices stored locally for fast retrieval during a screening session.
