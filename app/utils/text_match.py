# app/utils/text_match.py

import re
import unicodedata
from rapidfuzz import fuzz, process
from deep_translator import GoogleTranslator


# ---------------------------------------------------------------------------
# Digit normalization maps
# ---------------------------------------------------------------------------

# Devanagari numerals → ASCII digits
DEVANAGARI_DIGIT_MAP = str.maketrans("०१२३४५६७८९", "0123456789")

# Hindi + Marathi spoken word → digit
HINDI_WORD_TO_DIGIT: dict[str, str] = {
    # Hindi
    "शून्य": "0",
    "एक":   "1",
    "दो":   "2",
    "तीन":  "3",
    "चार":  "4",
    "पांच": "5",
    "छह":   "6",
    "सात":  "7",
    "आठ":   "8",
    "नौ":   "9",
    # Marathi variants
    "दोन":  "2",
    "पाच":  "5",
    "सहा":  "6",
    "नऊ":   "9",
    # English words (sometimes mixed in by STT)
    "zero":  "0",
    "one":   "1",
    "two":   "2",
    "three": "3",
    "four":  "4",
    "five":  "5",
    "six":   "6",
    "seven": "7",
    "eight": "8",
    "nine":  "9",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace, remove punctuation."""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def _translate_to_english(text: str) -> str:
    """
    Translate Hindi / Marathi text to English via Google Translate.
    Returns original text on any failure so the pipeline can still continue.
    """
    try:
        result = GoogleTranslator(source="auto", target="en").translate(text)
        return result.strip() if result else text
    except Exception:
        return text


# ---------------------------------------------------------------------------
# Public: digit extraction  (used for Aadhaar / Policy matching)
# ---------------------------------------------------------------------------

def extract_digits(text: str) -> str:
    """
    Convert STT output to a plain ASCII digit string.

    Handles all four formats that can come out of an IVR STT engine:
      1. Devanagari numerals  : "९८७६"           → "9876"
      2. Hindi/Marathi words  : "नौ आठ सात छह"   → "9876"
      3. English words        : "nine eight..."   → "9876"
      4. Plain ASCII digits   : "9876"            → "9876"
    """
    # Step 1 – Devanagari numeral characters → ASCII
    text = text.translate(DEVANAGARI_DIGIT_MAP)

    # Step 2 – spoken word tokens → digit characters
    tokens = text.strip().split()
    converted: list[str] = []
    for token in tokens:
        clean = token.strip().lower().rstrip(".,")
        converted.append(HINDI_WORD_TO_DIGIT.get(clean, token))
    text = " ".join(converted)

    # Step 3 – strip every non-digit character
    return re.sub(r"\D", "", text)


def get_last_4(text: str) -> str:
    """
    Return the last 4 ASCII digits from any STT input format.
    Returns "" if fewer than 4 digits are present (triggers a retry).
    """
    digits = extract_digits(text)
    return digits[-4:] if len(digits) >= 4 else ""


# ---------------------------------------------------------------------------
# Public: name / text matching  (used for farmer names, crops, stages, etc.)
# ---------------------------------------------------------------------------

def best_match(
    query: str,
    candidates: list[str],
    threshold: int = 60,
) -> str | None:
    """
    Match a possibly-Hindi/Marathi STT string against a list of English candidates.

    Two-layer strategy
    ──────────────────
    Layer 1 – Direct fuzzy match
        Works immediately when the user speaks in English or the STT already
        produced a romanised string.

    Layer 2 – Translate → fuzzy match
        Translates the query to English first (via Google Translate), then
        fuzzy-matches the result.  Handles cases where translation produces a
        slightly different spelling than the DB value (e.g. "Vitthalrao" vs
        "Vithalrao").

    Returns the best-matching candidate string, or None if nothing clears
    the threshold.
    """
    if not query or not candidates:
        return None

    normalized_candidates = [_normalize(c) for c in candidates]

    # ── Layer 1: direct fuzzy ────────────────────────────────────────────────
    direct = process.extractOne(
        _normalize(query),
        normalized_candidates,
        scorer=fuzz.token_sort_ratio,
    )
    if direct and direct[1] >= threshold:
        return candidates[direct[2]]

    # ── Layer 2: translate → fuzzy ───────────────────────────────────────────
    translated = _translate_to_english(query)
    if translated and translated != query:           # only retry if translation changed anything
        result = process.extractOne(
            _normalize(translated),
            normalized_candidates,
            scorer=fuzz.token_sort_ratio,
        )
        if result and result[1] >= threshold:
            return candidates[result[2]]

    return None