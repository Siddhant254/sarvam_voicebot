# app/services/dialogue_engine.py

from app.models.call_session import CallSession, CallStep, Language
from app.services.farmer_service import get_all_farmers
from app.services.prompts import get_prompt
from app.core.config import Config
from app.utils.text_match import best_match, get_last_4


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_LANGUAGE_RETRIES = 3
MAX_NAME_RETRIES     = 3

# Known vocabulary lists – extend these as your DB grows.
# These are matched against STT output (Hindi/Marathi/English) using best_match().
KNOWN_CROPS = [
    "Grapes", "Wheat", "Cotton", "Soybean", "Onion",
    "Sugarcane", "Rice", "Jowar", "Bajra", "Tur",
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


def _match_from_list(user_input: str, known_list: list[str], threshold: int = 55) -> str:
    """
    Try to match STT input to a known vocabulary list.
    Falls back to raw user_input if nothing matches (so data is never lost).
    """
    matched = best_match(user_input, known_list, threshold=threshold)
    return matched if matched else user_input


# ---------------------------------------------------------------------------
# Main processor
# ---------------------------------------------------------------------------

def process_input(session: CallSession, user_input: str) -> str:

    lang = session.language or "hi-IN"

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

        # Fetch all farmers and fuzzy-match against DB names.
        # best_match() handles Hindi/Marathi STT via translate → fuzzy pipeline.
        all_farmers     = get_all_farmers()
        candidate_names = [f["farmer_name"] for f in all_farmers]
        matched_name    = best_match(user_input, candidate_names, threshold=60)
        farmer          = next(
            (f for f in all_farmers if f["farmer_name"] == matched_name), None
        ) if matched_name else None

        if farmer:
            session.farmer_record   = farmer
            session.mobile_number   = farmer["mobile_number"]
            session.step            = CallStep.AUTH
            session.auth_substep    = "MOBILE"          # start with mobile last‑4
            session.auth_retries    = 0               # reset retry counter for this field
            
            return get_prompt("ask_mobile_last4", lang) # ask mobile last‑4 immediately
        else:
            session.name_retries += 1
            if session.name_retries >= MAX_NAME_RETRIES:
                session.step = CallStep.END
                return get_prompt("call_disconnecting", lang)
            return get_prompt("name_not_matched", lang)

    # ── AUTH ──────────────────────────────────────────────────────────────────
        # ── AUTH ──────────────────────────────────────────────────────────────────
    if session.step == CallStep.AUTH:

        if not session.farmer_record:
            session.step = CallStep.ESCALATE
            return get_prompt("auth_max_retries", lang)

        # ---------- MOBILE last‑4 ----------
        if session.auth_substep == "MOBILE":
            digits = get_last_4(user_input)

            # Compare with last 4 digits of the stored mobile number
            mobile_last4 = session.farmer_record.get("mobile_number", "")[-4:]

            if digits and digits == mobile_last4:
                # Success – move to Aadhaar step
                session.auth_substep = "AADHAAR"
                session.auth_retries = 0
                return get_prompt("ask_aadhaar", lang)
            else:
                session.auth_retries += 1
                if session.auth_retries >= Config.MAX_AUTH_RETRIES:
                    session.step = CallStep.ESCALATE
                    session.auth_substep = None
                    return get_prompt("auth_max_retries", lang)
                return get_prompt("auth_failed", lang)

        # ---------- AADHAAR last‑4 ----------
        if session.auth_substep == "AADHAAR":
            digits = get_last_4(user_input)
            aadhaar_last4 = session.farmer_record.get("aadhaar_last4", "")

            if digits and digits == aadhaar_last4:
                # Success – move to Policy step
                session.auth_substep = "POLICY"
                session.auth_retries = 0
                return get_prompt("ask_policy", lang)
            else:
                session.auth_retries += 1
                if session.auth_retries >= Config.MAX_AUTH_RETRIES:
                    session.step = CallStep.ESCALATE
                    session.auth_substep = None
                    return get_prompt("auth_max_retries", lang)
                return get_prompt("auth_failed", lang)

        # ---------- POLICY last‑4 ----------
        if session.auth_substep == "POLICY":
            digits = get_last_4(user_input)
            policy_last4 = session.farmer_record.get("policy_last4", "")

            if digits and digits == policy_last4:
                # Full authentication passed
                session.auth_passed = True
                session.auth_substep = None
                session.step = CallStep.USE_CASE_SELECT
                return get_prompt("use_case_menu", lang)
            else:
                session.auth_retries += 1
                if session.auth_retries >= Config.MAX_AUTH_RETRIES:
                    session.step = CallStep.ESCALATE
                    session.auth_substep = None
                    return get_prompt("auth_max_retries", lang)
                return get_prompt("auth_failed", lang)

        # Fallback (should never happen)
        session.step = CallStep.ESCALATE
        return get_prompt("auth_max_retries", lang)

    # ── USE CASE SELECT ───────────────────────────────────────────────────────
    if session.step == CallStep.USE_CASE_SELECT:
        # Currently both options lead to DATA_CAPTURE.
        # Extend with elif branches when more use-cases are added.
        if "1" in user_input or "एक" in user_input:
            session.step = CallStep.DATA_CAPTURE
            return get_prompt("ask_crop_name", lang)
        else:
            session.step = CallStep.DATA_CAPTURE
            return get_prompt("ask_crop_name", lang)

    # ── DATA CAPTURE ──────────────────────────────────────────────────────────
    # Each field is collected in sequence.
    # best_match / _match_from_list handle Hindi/Marathi STT for all fields.
    if session.step == CallStep.DATA_CAPTURE:

        if not session.grievance.crop_name:
            # Match against known crop vocabulary; fall back to raw input
            session.grievance.crop_name = _match_from_list(
                user_input, KNOWN_CROPS, threshold=55
            )
            return get_prompt("ask_crop_stage", lang)

        if not session.grievance.crop_stage:
            session.grievance.crop_stage = _match_from_list(
                user_input, KNOWN_STAGES, threshold=55
            )
            return get_prompt("ask_loss_date", lang)

        if not session.grievance.loss_date:
            # Date is stored as-is (STT date parsing is a separate concern)
            session.grievance.loss_date = user_input.strip()
            return get_prompt("ask_loss_reason", lang)

        if not session.grievance.loss_reason:
            session.grievance.loss_reason = _match_from_list(
                user_input, KNOWN_LOSS_REASONS, threshold=55
            )
            session.step = CallStep.TICKET_CREATE
            return get_prompt("ticket_created", lang, ticket_id="TKT-12345")

    # ── TICKET CREATE ─────────────────────────────────────────────────────────
    if session.step == CallStep.TICKET_CREATE:
        session.step = CallStep.END
        return get_prompt("goodbye", lang)

    # ── FALLBACK ──────────────────────────────────────────────────────────────
    return get_prompt("goodbye", lang)


# ---------------------------------------------------------------------------
# Quick smoke-test  (python -m app.services.dialogue_engine)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from app.models.call_session import CallSession

    session = CallSession(call_id="CALL-001", mobile_number="9876543210")

    test_inputs = [
        ("Step 1 – trigger welcome",          ""),
        ("Step 2 – select Hindi",             "1"),
        ("Step 3 – name in Hindi",            "रमेश पाटील"),   # Hindi STT
        ("Step 4 – Aadhaar last-4 (words)",   "नौ आठ सात छह"), # Hindi word-numbers
        ("Step 5 – Policy last-4 (Devangari)","९०१२"),          # Devanagari numerals
        ("Step 6 – use-case",                 "1"),
        ("Step 7 – crop name in Hindi",       "अंगूर"),         # Grapes
        ("Step 8 – crop stage in Hindi",      "खड़ी फसल"),      # Standing
        ("Step 9 – loss date",                "01-01-2025"),
        ("Step 10 – loss reason in Hindi",    "ओलावृष्टि"),     # Hailstorm
    ]

    for label, inp in test_inputs:
        response = process_input(session, inp)
        print(f"{label}\n  Input   : {inp!r}\n  Response: {response}\n")