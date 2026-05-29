from sarvamai import SarvamAI
from app.core.config import Config
import base64
from dotenv import load_dotenv
import os

load_dotenv()

sarvam_key = os.getenv("SARVAM_API_KEY")
client = SarvamAI(api_subscription_key=sarvam_key)


def text_to_speech(text: str, language: str = Config.DEFAULT_LANGUAGE) -> bytes:
    """
    Convert text to audio using Sarvam TTS.
    Returns audio as bytes.
    """
    response = client.text_to_speech.convert(
        text=text,
        target_language_code=language,
        speaker="pooja",
        model="bulbul:v3",
        enable_preprocessing=True,
        pace=1.0
    )
    
    # Sarvam returns base64 encoded audio
    audio_base64 = response.audios[0]

    audio_bytes = base64.b64decode(audio_base64)
    print(f"[DEBUG] TTS audio size: {len(audio_bytes)} bytes") 
    
    return audio_bytes

# if __name__ == "__main__":
#     audio = text_to_speech(
#         "नमस्ते, K R P H हेल्पलाइन में आपका स्वागत है। हिंदी के लिए एक दबाएं। मराठीसाठी दोन दाबा।"
#     )
#     with open("test_tts.wav", "wb") as f:
#         f.write(audio)
#     print("Audio saved as test_tts.wav")