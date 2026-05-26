import asyncio
import websockets
import sounddevice as sd
import numpy as np
import winsound
import time
import os

SAMPLE_RATE = 8000
SILENCE_THRESHOLD = 30  # adjust this based on your background noise


def play_audio(audio_bytes: bytes):
    """Play audio bytes through earphones."""
    temp_path = f"bot_{int(time.time())}.wav"
    with open(temp_path, "wb") as f:
        f.write(audio_bytes)
    winsound.PlaySound(temp_path, winsound.SND_FILENAME)
    os.remove(temp_path)


def is_silent(audio_np: np.ndarray) -> bool:
    """Check if audio is just background noise."""
    rms = np.sqrt(np.mean(audio_np**2))
    print(f"Audio RMS level: {rms:.2f}")
    return rms < SILENCE_THRESHOLD


def record_audio(duration: int = 5) -> tuple[bytes, bool]:
    """
    Record from mic for given seconds.
    Returns (audio_bytes, is_silent)
    """
    print("🎤 Listening... speak now")
    recording = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16'
    )
    sd.wait()
    print("✅ Done recording")
    silent = is_silent(recording)
    return recording.tobytes(), silent


async def simulate_call():
    uri = "ws://127.0.0.1:8000/ws/call/CALL-001?mobile_number=9876543210"

    async with websockets.connect(uri) as websocket:
        print("📞 Call connected!")

        while True:
            # Receive bot audio and play
            bot_audio = await websocket.recv()
            if isinstance(bot_audio, bytes):
                print("🤖 Bot speaking...")
                play_audio(bot_audio)

            # Record farmer response
            farmer_audio, silent = record_audio(duration=5)

            if silent:
                print("🔇 Silence detected — sending empty input")
                await websocket.send(b"")
            else:
                print("📤 Sending your response...")
                await websocket.send(farmer_audio)


asyncio.run(simulate_call())

#to check silences
# if __name__ == "__main__":
#     print("=== RMS Calibration Test ===")
#     print()

#     # Test 1: Silence/background noise
#     print("Test 1: CHUP RAHO — 3 seconds background noise measure kar raha hai...")
#     recording_silence = sd.rec(
#         int(3 * SAMPLE_RATE),
#         samplerate=SAMPLE_RATE,
#         channels=1,
#         dtype='int16'
#     )
#     sd.wait()
#     rms_silence = np.sqrt(np.mean(recording_silence**2))
#     print(f"Background noise RMS: {rms_silence:.2f}")

#     print()

#     # Test 2: Normal voice
#     print("Test 2: BOLNA SHURU KARO — 5 seconds mein normally bolo...")
#     recording_voice = sd.rec(
#         int(5 * SAMPLE_RATE),
#         samplerate=SAMPLE_RATE,
#         channels=1,
#         dtype='int16'
#     )
#     sd.wait()
#     rms_voice = np.sqrt(np.mean(recording_voice**2))
#     print(f"Your voice RMS: {rms_voice:.2f}")

#     print()

#     # Recommendation
#     print("=== Result ===")
#     print(f"Background noise : {rms_silence:.2f}")
#     print(f"Your voice       : {rms_voice:.2f}")
#     print()

#     # Calculate ideal threshold
#     ideal_threshold = (rms_silence + rms_voice) / 2
#     print(f"Ideal SILENCE_THRESHOLD should be: {ideal_threshold:.0f}")
#     print()
#     print(f"Current SILENCE_THRESHOLD = {SILENCE_THRESHOLD}")

#     if rms_voice > SILENCE_THRESHOLD:
#         print("✅ Current threshold is fine — voice will be detected")
#     else:
#         print(f"❌ Threshold too high! Change SILENCE_THRESHOLD = {ideal_threshold:.0f}")