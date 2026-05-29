import asyncio
import websockets
import sounddevice as sd
import numpy as np


SAMPLE_RATE       = 8000
SILENCE_THRESHOLD = 30


def play_audio(audio_bytes: bytes):
    """Play audio directly — no temp files."""
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
    print(f"[AUDIO] Playing {len(audio_np)} samples at 24000Hz")
    sd.play(audio_np, samplerate=24000)
    sd.wait()
    print(f"[AUDIO] Playback complete")


def is_silent(audio_np: np.ndarray) -> bool:
    rms = np.sqrt(np.mean(audio_np**2))
    print(f"[MIC] RMS level: {rms:.2f}")
    return rms < SILENCE_THRESHOLD


def record_audio(duration: int = 5) -> tuple[bytes, bool]:
    print("🎤 Listening... speak now")
    recording = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16"
    )
    sd.wait()
    print("✅ Done recording")
    silent = is_silent(recording)
    return recording.tobytes(), silent


async def simulate_call():
    # Change mobile_number to match a real farmer in your API
    uri = "ws://127.0.0.1:8000/ws/call/CALL-001?mobile_number=7000900644"

    async with websockets.connect(
        uri,
        ping_interval=60,
        ping_timeout=120,
        open_timeout=30
    ) as websocket:
        print("📞 Call connected!\n")

        while True:
            # Wait for bot to speak
            try:
                bot_audio = await asyncio.wait_for(websocket.recv(), timeout=30)
                print(f"[CLIENT] Received {len(bot_audio)} bytes")
            except asyncio.TimeoutError:
                print("⏰ No response from server — ending call")
                break
            except websockets.exceptions.ConnectionClosedError as e:
                print(f"❌ Connection closed: {e}")
                break

            if isinstance(bot_audio, bytes):
                print("🤖 Attempting to play audio...")  # ← add this
                play_audio(bot_audio)
                print("✅ play_audio() finished")

            # Record farmer response
            farmer_audio, silent = record_audio(duration=5)

            if silent:
                print("🔇 Silence — sending empty input")
                await websocket.send(b"\x00" * 10)  # small non-empty bytes
            else:
                print("📤 Sending audio to server...")
                await websocket.send(farmer_audio)


asyncio.run(simulate_call())