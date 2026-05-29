# app/api/websocket.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.session_manager import create_session, update_session, delete_session
from app.services.sarvam_stt import transcribe_audio
from app.services.sarvam_tts import text_to_speech
from app.services.dialogue_engine import process_input
import wave
import os

router = APIRouter()


def save_wav(audio_bytes: bytes, path: str, sample_rate: int = 8000):
    """Save raw audio bytes as a WAV file."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)


@router.websocket("/ws/call/{call_id}")
async def call_handler(
    websocket: WebSocket,
    call_id: str,
    mobile_number: str = Query(default="7000900644")
):
    await websocket.accept()
    print(f"[INFO] Call connected: {call_id} from {mobile_number}")

    # Create session once — reuse throughout the call
    session = create_session(call_id, mobile_number)

    # Send welcome message
    reply_text = process_input(session, "")   # ✅ fixed: was user_input (undefined)
    update_session(session)

    print(f"[BOT]  {reply_text!r}")
    print(f"[STEP] {session.step}")

    # Guard before TTS
    if reply_text and reply_text.strip():
        audio_bytes = text_to_speech(reply_text)
        await websocket.send_bytes(audio_bytes)
    else:
        print(f"[ERROR] Empty reply_text at welcome step — skipping TTS")

    try:
        while True:
            # Receive audio chunk from farmer
            audio_data = await websocket.receive_bytes()

            # Too short = silence
            if len(audio_data) < 100:
                user_input = ""
            else:
                wav_path = f"temp_{call_id}.wav"
                save_wav(audio_data, wav_path)
                user_input = transcribe_audio(wav_path)
                os.remove(wav_path)

            print(f"[FARMER] {user_input!r}")

            reply_text = process_input(session, user_input)
            update_session(session)

            print(f"[BOT]  {reply_text!r}")
            print(f"[STEP] {session.step}")

            # ✅ Guard before every TTS call
            if not reply_text or not reply_text.strip():
                print(f"[ERROR] Empty reply_text at step {session.step} — skipping TTS")
                continue   # ✅ fixed: continue is now correctly inside while loop

            audio_bytes = text_to_speech(reply_text)
            await websocket.send_bytes(audio_bytes)

    except WebSocketDisconnect:
        print(f"[INFO] Call ended: {call_id}")
        delete_session(call_id)