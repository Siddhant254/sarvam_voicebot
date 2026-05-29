# app/services/farmer_service.py

import requests
from typing import Optional
from datetime import datetime
import os
from dotenv import load_dotenv
from app.services.token_manager import get_headers, _decompress_response, get_token

load_dotenv()

API_TOKEN = os.getenv("KRPH_API_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type":  "application/json"
}

# ---------------------------------------------------------------------------
# API config
# ---------------------------------------------------------------------------

BASE_URL        = "https://pmfbydemo.amnex.co.in/krphapi/FGMS"
MOBILE_API_URL  = f"{BASE_URL}/CheckKRPHFarmerByMobileNumber"
POLICY_API_URL  = f"{BASE_URL}/GetFarmerPolicyDetail"

API_COMMON = {
    "insertedUserID":    "214",
    "insertedIPAddress": "14.97.62.70",
    "dateShort":         "yyyy-MM-dd",
    "dateLong":          "yyyy-MM-dd HH:mm:ss",
}

# Current season config — update these as season changes
CURRENT_SEASON_ID = "1"
CURRENT_YEAR      = str(datetime.now().year)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _extract_aadhaar_last4(masked: str) -> str:
    """
    Extract last 4 digits from masked Aadhaar like "XXXX-XXXX-2590".
    Returns "" if format is unexpected.
    """
    if not masked:
        return ""
    digits = masked.replace("-", "").replace("X", "").replace("x", "").strip()
    return digits[-4:] if len(digits) >= 4 else ""


# ---------------------------------------------------------------------------
# 1. Fetch farmer by mobile number
# ---------------------------------------------------------------------------

def get_farmer_by_mobile(mobile_number: str) -> Optional[dict]:
    try:
        payload  = {"mobilenumber": mobile_number.strip(), "objCommon": API_COMMON}
        response = requests.post(MOBILE_API_URL, json=payload, headers=get_headers(), timeout=10)
        response.raise_for_status()
        data = response.json()

        print(f"[DEBUG] API status code : {response.status_code}")

        if data.get("responseCode") != "1":
            print(f"[WARN] Farmer not found: {data.get('responseMessage')}")
            return None

        # ✅ Decompress responseDynamic — same format as token response
        farmer_data = _decompress_response(data["responseDynamic"])
        print(f"[DEBUG] Farmer data keys: {list(farmer_data.keys())}")

        if not farmer_data.get("status"):
            print(f"[WARN] Farmer not found")
            return None
        result = farmer_data.get("data", {}).get("result")
        if not result:
            return None

        return {
            "farmer_name":   result.get("farmerName", ""),
            "mobile_number": result.get("mobile", mobile_number),
            "farmer_id":     result.get("farmerID", ""),
            "district":      result.get("district", ""),
            "state":         result.get("state", ""),
            "village":       result.get("village", ""),
            "sub_district":  result.get("subDistrict", ""),
            "pincode":       result.get("resPincode", ""),
            "age":           result.get("age"),
            "gender":        result.get("gender"),
            "aadhaar_last4": None,
            "policy_data":   None,
        }

    except Exception as e:
        print(f"[ERROR] Mobile API error: {e}")
        return None


# ---------------------------------------------------------------------------
# 2. Fetch policy details + extract aadhaar_last4
# ---------------------------------------------------------------------------

def get_farmer_policy(mobile_number: str, farmer_id: str) -> Optional[dict]:
    try:
        payload = {
            "mobilenumber": mobile_number.strip(),
            "seasonID":     CURRENT_SEASON_ID,
            "year":         CURRENT_YEAR,
            "farmerID":     farmer_id.strip(),
            "objCommon":    API_COMMON,
        }
        response = requests.post(POLICY_API_URL, json=payload, headers=get_headers(), timeout=10)

        print(f"[DEBUG] Policy payload sent    : {payload}")
        print(f"[DEBUG] Policy raw response    : {response.text[:500]}")

        response.raise_for_status()
        data = response.json()

        if not data.get("status") or not data.get("data"):
            print(f"[WARN] Policy not found for farmerID: {farmer_id}")
            return None

        policy_map = data["data"]
        if not policy_map:
            return None

        policy_id  = list(policy_map.keys())[0]
        policy     = policy_map[policy_id]
        app_list   = policy.get("applicationList", [])
        first_app  = app_list[0] if app_list else {}

        aadhaar_last4 = _extract_aadhaar_last4(policy.get("aadharNumber", ""))

        print(f"[DEBUG] Policy ID      : {policy_id!r}")
        print(f"[DEBUG] Application No : {first_app.get('applicationNo')!r}")
        print(f"[DEBUG] Aadhaar last 4 : {aadhaar_last4!r}")

        return {
            "aadhaar_last4":      aadhaar_last4,
            "policy_id":          policy_id,
            "policy_type":        policy.get("policyType", ""),
            "policy_premium":     policy.get("policyPremium"),
            "policy_area":        policy.get("policyArea"),
            "scheme":             policy.get("scheme", ""),
            "insurance_company":  policy.get("insuranceCompanyName", ""),
            "farmer_name":        policy.get("farmerName", ""),
            "account_number":     policy.get("accountNumber", ""),
            "relation":           policy.get("relation", ""),
            "relative_name":      policy.get("relativeName", ""),
            "district":           policy.get("resDistrict", ""),
            "state":              policy.get("resState", ""),
            "village":            policy.get("resVillage", ""),
            "sub_district":       policy.get("resSubDistrict", ""),
            "crop_name":          first_app.get("cropName", ""),
            "application_no":     first_app.get("applicationNo", ""),
            "application_status": first_app.get("applicationStatus", ""),
            "land_survey_number": first_app.get("landSurveyNumber", ""),
            "sowing_date":        first_app.get("sowingDate", ""),
            "farmer_share":       first_app.get("farmerShare"),
            "ifsc_code":          first_app.get("ifscCode", ""),
            "all_applications":   app_list,
        }

    except requests.Timeout:
        print(f"[ERROR] Policy API timed out for farmerID: {farmer_id}")
        return None
    except requests.RequestException as e:
        print(f"[ERROR] Policy API request error: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Policy unexpected error: {e}")
        return None

# ---------------------------------------------------------------------------
# 3. Combined fetch — mobile + policy in one call
#    Used by dialogue_engine during NAME_CAPTURE
# ---------------------------------------------------------------------------

def fetch_farmer_full_record(mobile_number: str) -> Optional[dict]:
    """
    Pre-fetch token once, then call both APIs.
    Prevents double token fetch.
    """
    # ✅ Force token fetch ONCE before both API calls
    get_token()

    farmer = get_farmer_by_mobile(mobile_number)
    if not farmer:
        return None

    policy = get_farmer_policy(mobile_number, farmer["farmer_id"])
    if policy:
        farmer["aadhaar_last4"] = policy["aadhaar_last4"]
        farmer["policy_data"]   = policy
        print(f"[DEBUG] aadhaar_last4 from policy: {policy['aadhaar_last4']!r}")
    else:
        print(f"[WARN] Policy fetch failed for {mobile_number} — auth will fallback")

    return farmer

# ---------------------------------------------------------------------------
# Stubs — kept so existing imports don't break
# ---------------------------------------------------------------------------

def get_all_farmers() -> list[dict]:
    return []

def get_farmer_by_name(name: str) -> Optional[dict]:
    return None

def validate_auth(farmer: dict, aadhaar_last4: str) -> bool:
    return farmer.get("aadhaar_last4") == aadhaar_last4