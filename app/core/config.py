import os

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

class Config:
    SARVAM_API_KEY    = os.getenv("SARVAM_API_KEY", "")
    STT_MODEL         = "saaras:v3"
    DEFAULT_LANGUAGE  = "hi-IN"
    MAX_AUTH_RETRIES  = 3
    APP_NAME          = "KRPH Voicebot"