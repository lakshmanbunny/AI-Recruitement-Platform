import asyncio
import os
import logging
import traceback
from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobRequest,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import silero, deepgram, elevenlabs, google

# Robust .env loading
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(current_dir, ".env")) 
load_dotenv(os.path.join(os.path.dirname(current_dir), ".env"))
root_dir = os.path.dirname(os.path.dirname(current_dir))
load_dotenv(os.path.join(root_dir, ".env"))

# Add backend and root to sys.path for service imports
sys.path.append(os.path.dirname(current_dir))
sys.path.append(root_dir)

# Import services
from app.services.interview_service import interview_service
from config.logging_config import get_logger
logger = get_logger(__name__)

# Setup file logging for deep diagnostics
LOG_FILE = os.path.join(current_dir, "agent_debug.log")
def log_to_file(msg):
    from datetime import datetime
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")

async def request_fnc(req: JobRequest):
    log_to_file(f"Received Job Request: {req.id} for room {req.job.room.name}")
    print(f"\n--- [AGENT] Received Job Request: {req.id} for room {req.job.room.name} ---")
    await req.accept()

async def entrypoint(ctx: JobContext):
    from datetime import datetime
    log_to_file(f"Entrypoint Started for room: {ctx.room.name}")
    print(f"\n--- [AGENT] Entrypoint Started: {ctx.room.name} ---")
    
    try:
        # Extract candidate_id/job_id from room name (format: interview-CAND-JOB)
        room_parts = ctx.room.name.split("-")
        candidate_id = 1
        job_id = 1
        if len(room_parts) >= 3:
            try:
                candidate_id = int(room_parts[1])
                job_id = int(room_parts[2])
            except: pass

        # 1. Initialize/Resume Interview Session
        print(f"--- [AGENT] Connecting to Intelligence Service for Candidate {candidate_id}... ---")
        session_state = await interview_service.start_interview(candidate_id, job_id)
        session_id = session_state["session_id"]
        
        instructions = (
            "You are a Senior Technical Interviewer at Paradigm IT. "
            "Your role is to conduct a professional screening using the questions provided to you. "
            "PRINCIPLES: "
            "1. Be professional and objective. "
            "2. Keep transitions brief. "
            "3. Do not attempt to explain technical concepts. "
            "4. Follow the structured question roadmap strictly."
        )

        # 2. Connect to LiveKit Room
        log_to_file("Connecting to LiveKit Room...")
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        log_to_file("Connected to LiveKit Room successfully.")

        # 3. Setup Components
        log_to_file("Initializing VAD, STT, LLM, TTS plugins...")
        vad = silero.VAD.load()
        stt = deepgram.STT(api_key=os.getenv("DEEPGRAM_API_KEY"))
        llm_model = google.LLM(model="gemini-2.5-flash-lite")
        tts = elevenlabs.TTS(api_key=os.getenv("ELEVENLABS_API_KEY"))
        
        log_to_file("Creating Agent and AgentSession...")
        agent = Agent(
            instructions=instructions,
            vad=vad,
            stt=stt,
            llm=llm_model,
            tts=tts,
        )

        agent_session = AgentSession(
            vad=vad,
            stt=stt,
            llm=llm_model,
            tts=tts,
        )

        last_transcribed_text = ""

        @agent_session.on("user_input_transcribed")
        def on_user_transcribed(event):
            nonlocal last_transcribed_text
            text = event.text.strip()
            if text:
                print(f"[USER]: {text}")
                last_transcribed_text = text
                # Send to UI for transparency
                asyncio.create_task(ctx.room.local_participant.publish_data(
                    payload=text.encode(),
                    topic="transcription"
                ))

        @agent_session.on("agent_speech_started")
        def on_agent_speech_started(event):
            # Clear speech layout in UI
            asyncio.create_task(ctx.room.local_participant.publish_data(
                payload=b"CLEAR_TRANSCRIPTION",
                topic="transcription"
            ))

        # Start Session
        log_to_file("Starting AgentSession...")
        await agent_session.start(agent, room=ctx.room)
        log_to_file("AgentSession started.")
        
        # 4. Main Interview Intelligence Loop
        print("--- [AGENT] Waiting for candidate to join... ---")
        await ctx.wait_for_participant()
        # Stabilization delay to ensure audio streams are ready
        await asyncio.sleep(2)

        if session_state.get("current_question"):
            print(f"--- [AGENT] Initial Question Found: {session_state['current_question']} ---")
        else:
            print("--- [AGENT] WARNING: No initial question found in session state! ---")

        print("--- [AGENT] Interview Started. Greeting candidate... ---")
        greeting = "Hello! I am your AI Technical Interviewer for today. Thank you for joining. We have a structured roadmap to go through. Let's begin."
        print(f"--- [AGENT] Triggering Speech: {greeting} ---")
        agent_session.say(greeting)
        print("--- [AGENT] Speech Triggered. Waiting for greeting buffer (5s)... ---")
        await asyncio.sleep(5) 

        print("--- [AGENT] Question Loop Started ---")
        
        while not session_state.get("is_completed"):
            current_q = session_state.get("current_question")
            if not current_q:
                print("--- [AGENT] No more questions. Finishing. ---")
                break

            # Ask the question
            print(f"--- [AGENT] Talking: {current_q} ---")
            agent_session.say(current_q)
            
            # Reset answer and wait for candidate to finish speaking
            last_transcribed_text = ""
            
            # Simple wait-for-answer logic
            # In production, we'd use a more sophisticated state machine
            while not last_transcribed_text:
                await asyncio.sleep(0.5)
            
            # Give candidate time to finish the sentence
            await asyncio.sleep(3)
            
            print(f"--- [AGENT] Submitting Answer for Analysis... ---")
            session_state = await interview_service.submit_answer(session_id, last_transcribed_text)
            
            if session_state.get("status") == "completed":
                print("--- [AGENT] Reached end of session. ---")
                agent_session.say("Thank you. I have all the information I need for now. We will be in touch shortly. Goodbye!")
                await asyncio.sleep(5)
                break

        # Cleanup / Shutdown handling
        shutdown_event = asyncio.Event()
        ctx.add_shutdown_callback(lambda reason: shutdown_event.set())
        await shutdown_event.wait()
        
    except Exception as e:
        print(f"\n--- [AGENT CRITICAL ERROR]: {e} ---")
        traceback.print_exc()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        request_fnc=request_fnc,
    ))
