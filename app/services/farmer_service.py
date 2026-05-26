# app/services/farmer_service.py

from typing import Optional

# ---------------------------------------------------------------------------
# Dummy farmer database
# In production, replace with real API/DB calls
# ---------------------------------------------------------------------------

FARMER_DB = {
    "9876543210": {
        "farmer_name":   "Ramesh Patil",
        "mobile_number": "9876543210",
        "aadhaar_last4": "1234",
        "policy_last4":  "5678",
        "app_no_last4":  "9012",
        "district":      "Pune",
        "state":         "Maharashtra",
    },
    "9123456780": {
        "farmer_name":   "Sunil Deshmukh",
        "mobile_number": "9123456780",
        "aadhaar_last4": "4321",
        "policy_last4":  "8765",
        "app_no_last4":  "2109",
        "district":      "Nashik",
        "state":         "Maharashtra",
    },
    "9999999999": {
        "farmer_name":   "Vijay Shinde",
        "mobile_number": "9999999999",
        "aadhaar_last4": "1111",
        "policy_last4":  "2222",
        "app_no_last4":  "3333",
        "district":      "Nagpur",
        "state":         "Maharashtra",
    },
}


# ---------------------------------------------------------------------------
# Fetch functions
# ---------------------------------------------------------------------------

def get_all_farmers() -> list[dict]:
    """
    Return all farmer records as a list.
    Called by dialogue_engine for fuzzy name matching.
    In production: return your DB/API result list here.
    """
    return list(FARMER_DB.values())


def get_farmer_by_name(name: str) -> Optional[dict]:
    """
    Exact name lookup (case-insensitive).
    NOTE: dialogue_engine.py uses best_match() + get_all_farmers() instead,
    so this is kept only for direct/internal lookups.
    """
    name = name.strip().lower()
    for farmer in FARMER_DB.values():
        if farmer["farmer_name"].lower() == name:
            return farmer
    return None


def get_farmer_by_mobile(mobile_number: str) -> Optional[dict]:
    """Fetch farmer record by mobile number."""
    return FARMER_DB.get(mobile_number.strip())


# ---------------------------------------------------------------------------
# Auth validation
# ---------------------------------------------------------------------------

def validate_auth(
    farmer: dict,
    policy_last4: str,
    app_no_last4: str,
    aadhaar_last4: str,
) -> bool:
    """
    Validate last-4 digits of policy number, app number, and Aadhaar.
    All inputs should already be normalised ASCII digits before calling this.
    """
    return (
        farmer.get("policy_last4")  == policy_last4.strip()  and
        farmer.get("app_no_last4")  == app_no_last4.strip()  and
        farmer.get("aadhaar_last4") == aadhaar_last4.strip()
    )