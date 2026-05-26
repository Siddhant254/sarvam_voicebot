from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.session_manager import create_session, get_session, update_session, delete_session
from app.services.sarvam_stt import transcribe_audio
from app.services.sarvam_tts import text_to_speech
from app.services.dialogue_engine import process_input
import wave
import os

router = APIRouter()


def save_wav(audio_bytes: bytes, path: str, sample_rate: int = 8000):
    """Save raw audio bytes as a wav file."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)


@router.websocket("/ws/call/{call_id}")
async def call_handler(websocket: WebSocket, call_id: str, mobile_number: str):
    await websocket.accept()
    print(f"Call connected: {call_id} from {mobile_number}")

    # Create session
    session = create_session(call_id, mobile_number)

    # Send welcome message
    reply_text = process_input(session, "")
    update_session(session)
    audio_bytes = text_to_speech(reply_text)
    await websocket.send_bytes(audio_bytes)

    try:
        while True:
            # Receive audio from farmer
            # Receive audio from farmer
            audio_data = await websocket.receive_bytes()

            # If empty — farmer was silent
            if len(audio_data) < 100:
                user_input = ""
            else:
                # Save as wav
                wav_path = f"temp_{call_id}.wav"
                save_wav(audio_data, wav_path)

                # Transcribe
                user_input = transcribe_audio(wav_path)
                os.remove(wav_path)
                
            print(f"Farmer said: {user_input}")

            # Get reply from dialogue engine
            session = get_session(call_id)
            if session is None:
                break
            reply_text = process_input(session, user_input)
            
            update_session(session)
            print(f"Bot says: {reply_text}")

            # Convert reply to audio and send
            audio_bytes = text_to_speech(reply_text)
            await websocket.send_bytes(audio_bytes)

    except WebSocketDisconnect:
        print(f"Call ended: {call_id}")
        delete_session(call_id)