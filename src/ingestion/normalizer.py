import re
from datetime import datetime

CITY_CANONICAL_MAP = {
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "bengaluru": "Bengaluru",
    "bangalore": "Bengaluru",
    "noida": "Noida",
    "pune": "Pune",
    "delhi": "Delhi NCR",
    "new delhi": "Delhi NCR",
    "delhi ncr": "Delhi NCR"
}

def normalize_name(name: str) -> str:
    """Normalizes candidate name to Title Case with clean spacing."""
    if not name:
        return ""
    cleaned = re.sub(r"\s+", " ", name.strip())
    parts = cleaned.split()
    title_parts = [p.capitalize() if not (len(p) <= 2 and p.endswith('.')) else p for p in parts]
    return " ".join(title_parts)

def normalize_email(email: str) -> str:
    """Lowercases and trims email string. Returns empty string if invalid."""
    if not email:
        return ""
    cleaned = email.strip().lower()
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if re.match(pattern, cleaned):
        return cleaned
    return ""

def normalize_phone(phone: str) -> str:
    """Extracts standardized 10-digit Indian phone number."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10:
        return digits
    return ""

def normalize_city(city: str) -> str:
    """Maps city variants to canonical city names."""
    if not city:
        return ""
    cleaned = city.strip().lower()
    return CITY_CANONICAL_MAP.get(cleaned, city.strip().title())

def normalize_date(date_str: str) -> str:
    """Parses various date formats to ISO-8601 (YYYY-MM-DD)."""
    if not date_str:
        return ""
    cleaned = date_str.strip()
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d %b %Y",
        "%Y/%m/%d"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return cleaned

def normalize_ctc(ctc_val) -> float:
    """
    Normalizes expected CTC to LPA float.
    If value > 100 (annual INR e.g. 332456), converts to LPA by dividing by 100,000.
    """
    if ctc_val is None or str(ctc_val).strip() == "":
        return None
    try:
        val = float(str(ctc_val).strip())
        if val > 100:
            return round(val / 100000.0, 2)
        return round(val, 2)
    except ValueError:
        return None

def normalize_rate(rate_str: str) -> dict:
    """
    Parses rate string into hourly_rate_inr or monthly_rate_inr dict.
    Examples: '1415/hr' -> {'hourly': 1415.0}, '15k/month' -> {'monthly': 15000.0}
    """
    res = {"hourly": None, "monthly": None}
    if not rate_str:
        return res
    cleaned = rate_str.strip().lower()
    if "/hr" in cleaned or "hr" in cleaned:
        num_part = re.sub(r"[^\d.]", "", cleaned)
        if num_part:
            res["hourly"] = float(num_part)
    elif "month" in cleaned:
        if "k/month" in cleaned or "k" in cleaned:
            num_part = re.sub(r"[^\d.]", "", cleaned)
            if num_part:
                res["monthly"] = float(num_part) * 1000.0
        else:
            num_part = re.sub(r"[^\d.]", "", cleaned)
            if num_part:
                res["monthly"] = float(num_part)
    return res

def normalize_verified(verified_str: str) -> bool:
    """Maps various verification status strings to boolean."""
    if not verified_str:
        return False
    cleaned = verified_str.strip().lower()
    return cleaned in ["y", "yes", "verified", "true", "1"]

def normalize_skills(skills_str: str) -> list:
    """Splits comma-separated skills into clean lowercased list."""
    if not skills_str:
        return []
    parts = skills_str.split(",")
    return [p.strip().lower() for p in parts if p.strip()]
