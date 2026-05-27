from sarvamai import SarvamAI
from app.core.config import Config
from dotenv import load_dotenv

import os

load_dotenv()

sarvam_key = os.getenv("SARVAM_API_KEY")

client = SarvamAI(api_subscription_key=sarvam_key)


def transcribe_audio(file_path: str, language: str = Config.DEFAULT_LANGUAGE) -> str:
    """
    Convert audio file to text using Sarvam STT.
    Returns transcribed text.
    """
    with open(file_path, "rb") as f:
        response = client.speech_to_text.transcribe(
            file=f,
            model="saarika:v2.5",
            mode="transcribe",
        )
    return response.transcript

# if __name__ == "__main__":
#     text = transcribe_audio("test_tts.wav")
#     print("Transcribed text:", text)