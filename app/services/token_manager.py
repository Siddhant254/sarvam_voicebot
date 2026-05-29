# app/services/token_manager.py

import base64
import gzip
import json
import time
import requests
from typing import Optional

# ---------------------------------------------------------------------------
# Login API config
# ---------------------------------------------------------------------------

LOGIN_URL = "https://pmfbydemo.amnex.co.in/krphapi/FGMS/UserLogin"

LOGIN_PAYLOAD = {
    "appAccessUID": "Qk9UQVBJ",
    "appAccessPWD": "5d26fdc618b3c21239f80ee0998fc6e8882677c6bacb9f364e622a18dbf13558",
    "mACIPAddress": "24b41dda024e7a17c9a6444d941c82",
    "objCommon": {
        "insertedIPAddress": "61.246.33.210"
    }
}

# ---------------------------------------------------------------------------
# In-memory token cache
# ---------------------------------------------------------------------------

_token_cache = {
    "token":      None,
    "expires_at": 0       # unix timestamp when token expires
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decompress_response(compressed_b64: str) -> dict:
    """Decompress GZip + Base64 encoded API response."""
    compressed   = base64.b64decode(compressed_b64)
    decompressed = gzip.decompress(compressed).decode("utf-8")
    return json.loads(decompressed)


def _fetch_fresh_token() -> tuple[Optional[str], float]:
    """
    Call login API, decompress response, extract JWT token and expiry.
    Returns (token_string, expires_at_unix_timestamp).
    """
    try:
        response = requests.post(LOGIN_URL, json=LOGIN_PAYLOAD, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("responseCode") != "1":
            print(f"[ERROR] Login API failed: {data.get('responseMessage')}")
            return None, 0

        # Decompress GZip + Base64 encoded response
        token_data = _decompress_response(data["responseDynamic"])

        # token is a nested dict inside token_data
        token_obj  = token_data.get("token", {})
        token      = token_obj.get("Token")           # actual JWT string
        expires_at = token_obj.get("expirationTime")  # unix timestamp

        print(f"[TOKEN] Fresh token fetched")
        print(f"[TOKEN] Valid from : {token_obj.get('validFrom')}")
        print(f"[TOKEN] Valid to   : {token_obj.get('validTo')}")

        if not token:
            print(f"[ERROR] Token not found in response")
            return None, 0

        return token, float(expires_at)

    except Exception as e:
        print(f"[ERROR] Token fetch failed: {e}")
        return None, 0


# ---------------------------------------------------------------------------
# Public: get valid token (cached or fresh)
# ---------------------------------------------------------------------------

def get_token() -> Optional[str]:
    now = time.time()

    if _token_cache["token"] and now < _token_cache["expires_at"]:
        print("[TOKEN] Using cached token")
        return _token_cache["token"]

    print("[TOKEN] Cache empty or expired — fetching fresh token...")
    token, expires_at = _fetch_fresh_token()

    if token and expires_at:
        _token_cache["token"]      = token
        _token_cache["expires_at"] = expires_at - 60
        print(f"[TOKEN] Token cached successfully")

    return _token_cache["token"]   # ← change this line


def get_headers() -> dict:
    """Return request headers with valid Bearer token."""
    token = get_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json"
    }