# app/services/dialogue_engine.py

from app.models.call_session import CallSession, CallStep, Language
from app.services.farmer_service import fetch_farmer_full_record
from app.services.prompts import get_prompt
from app.core.config import Config
from app.utils.text_match import best_match, get_last_4, extract_digits


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_LANGUAGE_RETRIES = 3
MAX_NAME_RETRIES     = 3

KNOWN_CROPS = [
    "Grapes", "Wheat", "Cotton", "Soybean", "Onion",
    "Sugarcane", "Rice", "Jowar", "Bajra", "Tur", "Paddy",
]

KNOWN_STAGES = [
    "Sowing", "Germination", "Standing", "Flowering",
    "Harvesting", "Post-harvest",
]

KNOWN_LOSS_REASONS = [
    "Hailstorm", "Flood", "Drought", "Pest Attack",
    "Disease", "Unseasonal Rain", "Fire",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_empty(text: str) -> bool:
    return text.strip() == "" or len(text.strip()) < 2


def _resolve_lang(session: CallSession) -> str:
    """Always returns a plain string language code, never an enum."""
    if session.language == Language.HINDI:
        return "hi-IN"
    elif session.language == Language.MARATHI:
        return "mr-IN"
    return "hi-IN"


def _match_from_list(user_input: str, known_list: list[str], threshold: int = 55) -> str:
    matched = best_match(user_input, known_list, threshold=threshold)
    return matched if matched else user_input


# ---------------------------------------------------------------------------
# Main processor
# ---------------------------------------------------------------------------

def process_input(session: CallSession, user_input: str) -> str:

    lang = _resolve_lang(session)

    # ── WELCOME ──────────────────────────────────────────────────────────────
    if session.step == CallStep.WELCOME:
        session.step = CallStep.LANGUAGE_SELECT
        return get_prompt("welcome", "hi-IN")

    # ── LANGUAGE SELECT ───────────────────────────────────────────────────────
    if session.step == CallStep.LANGUAGE_SELECT:
        if _is_empty(user_input):
            session.language_retries += 1
            if session.language_retries >= MAX_LANGUAGE_RETRIES:
                session.step = CallStep.END
                return get_prompt("call_disconnecting", "hi-IN")
            return get_prompt("silence_retry", "hi-IN")

        if "1" in user_input or "एक" in user_input or "hindi" in user_input.lower():
            session.language = Language.HINDI
            lang = "hi-IN"
        else:
            session.language = Language.MARATHI
            lang = "mr-IN"

        session.step = CallStep.NAME_CAPTURE
        return get_prompt("ask_name", lang)

    # ── NAME CAPTURE ──────────────────────────────────────────────────────────
    if session.step == CallStep.NAME_CAPTURE:
        if _is_empty(user_input):
            session.name_retries += 1
            if session.name_retries >= MAX_NAME_RETRIES:
                session.step = CallStep.END
                return get_prompt("call_disconnecting", lang)
            return get_prompt("name_retry", lang)
        
        if not session.mobile_number:
            print("[ERROR] No mobile number in session — cannot fetch farmer")
            session.step = CallStep.ESCALATE
            return get_prompt("auth_max_retries", lang)

        # Fetch farmer record + policy (merged) using mobile number from call
        farmer = fetch_farmer_full_record(session.mobile_number)

        if not farmer:
            # API failed — retry name input
            session.name_retries += 1
            if session.name_retries >= MAX_NAME_RETRIES:
                session.step = CallStep.ESCALATE
                return get_prompt("auth_max_retries", lang)
            return get_prompt("name_not_matched", lang)

        # Loosely verify spoken name matches DB name
        print(f"[DEBUG] Spoken name  : {user_input!r}")
        print(f"[DEBUG] DB name      : {farmer['farmer_name']!r}")

        matched = best_match(user_input, [farmer["farmer_name"]], threshold=50)
        print(f"[DEBUG] Name matched : {matched!r}")

        if matched:
            session.farmer_record = farmer
            session.step          = CallStep.AUTH
            return get_prompt("auth_prompt", lang)
        else:
            session.name_retries += 1
            if session.name_retries >= MAX_NAME_RETRIES:
                session.step = CallStep.END
                return get_prompt("call_disconnecting", lang)
            return get_prompt("name_not_matched", lang)

    # ── AUTH ──────────────────────────────────────────────────────────────────
    if session.step == CallStep.AUTH:

        if not session.farmer_record:
            session.step = CallStep.ESCALATE
            return get_prompt("auth_max_retries", lang)

        # First entry → ask policy last 4
        if session.auth_substep is None:
            session.auth_substep = "POLICY"
            return get_prompt("ask_policy_no", lang)

        # ── Policy verification ───────────────────────────────────────────────
        if session.auth_substep == "POLICY":
            policy_last4 = get_last_4(user_input)
            policy_id    = (session.farmer_record.get("policy_data") or {}).get("policy_id", "")
            expected     = policy_id[-4:] if policy_id else ""

            print(f"[DEBUG] Policy input     : {user_input!r}")
            print(f"[DEBUG] Extracted last-4 : {policy_last4!r}")
            print(f"[DEBUG] Expected last-4  : {expected!r}")

            if not expected:
                print(f"[WARN] Policy ID not available — escalating")
                session.step         = CallStep.ESCALATE
                session.auth_substep = None
                return get_prompt("auth_max_retries", lang)

            if policy_last4 and policy_last4 == expected:
                # Policy matched → move to application number
                session.auth_substep  = "APP_NO"
                session.auth_retries  = 0        # reset retries for next step
                return get_prompt("ask_app_no", lang)
            else:
                session.auth_retries += 1
                if session.auth_retries >= Config.MAX_AUTH_RETRIES:
                    session.step         = CallStep.ESCALATE
                    session.auth_substep = None
                    return get_prompt("auth_max_retries", lang)
                return get_prompt("auth_failed", lang)

        # ── Application number verification ───────────────────────────────────
        if session.auth_substep == "APP_NO":
            app_last4   = get_last_4(user_input)
            app_no      = (session.farmer_record.get("policy_data") or {}).get("application_no", "")
            expected    = app_no[-4:] if app_no else ""

            print(f"[DEBUG] App No input     : {user_input!r}")
            print(f"[DEBUG] Extracted last-4 : {app_last4!r}")
            print(f"[DEBUG] Expected last-4  : {expected!r}")

            if not expected:
                print(f"[WARN] Application number not available — escalating")
                session.step         = CallStep.ESCALATE
                session.auth_substep = None
                return get_prompt("auth_max_retries", lang)

            if app_last4 and app_last4 == expected:
                # Both verified → authenticated
                session.auth_passed  = True
                session.auth_substep = None
                session.step         = CallStep.USE_CASE_SELECT
                return get_prompt("use_case_menu", lang)
            else:
                session.auth_retries += 1
                if session.auth_retries >= Config.MAX_AUTH_RETRIES:
                    session.step         = CallStep.ESCALATE
                    session.auth_substep = None
                    return get_prompt("auth_max_retries", lang)
                return get_prompt("auth_failed", lang)
    # ── DATA CAPTURE ──────────────────────────────────────────────────────────
    if session.step == CallStep.DATA_CAPTURE:

        if not session.grievance.crop_name:
            session.grievance.crop_name = _match_from_list(user_input, KNOWN_CROPS, threshold=55)
            print(f"[DEBUG] Crop name   : {user_input!r} → {session.grievance.crop_name!r}")
            return get_prompt("ask_crop_stage", lang)

        if not session.grievance.crop_stage:
            session.grievance.crop_stage = _match_from_list(user_input, KNOWN_STAGES, threshold=55)
            print(f"[DEBUG] Crop stage  : {user_input!r} → {session.grievance.crop_stage!r}")
            return get_prompt("ask_loss_date", lang)

        if not session.grievance.loss_date:
            session.grievance.loss_date = user_input.strip()
            return get_prompt("ask_loss_reason", lang)

        if not session.grievance.loss_reason:
            session.grievance.loss_reason = _match_from_list(user_input, KNOWN_LOSS_REASONS, threshold=55)
            print(f"[DEBUG] Loss reason : {user_input!r} → {session.grievance.loss_reason!r}")
            session.step = CallStep.TICKET_CREATE
            return get_prompt("ticket_created", lang, ticket_id="TKT-12345")

    # ── TICKET CREATE ─────────────────────────────────────────────────────────
    if session.step == CallStep.TICKET_CREATE:
        session.step = CallStep.END
        return get_prompt("goodbye", lang)

    # ── FALLBACK ──────────────────────────────────────────────────────────────
    return get_prompt("goodbye", lang)