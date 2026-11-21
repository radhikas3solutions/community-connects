"""Member phone numbers from any country, stored in international (E.164) form: "+917702345678".

Members pick a country and type their number; a bare 10-digit number is taken as US/Canada.
"""

import re

MIN_DIGITS, MAX_DIGITS = 7, 15  # E.164 allows up to 15 digits including the country code


def normalize_phone(raw: object) -> str | None:
    """ "+91 77023 45678" -> "+917702345678"; "(703) 555-0123" -> "+17035550123"; junk -> None."""
    if not raw:
        return None
    text = str(raw).strip()
    digits = re.sub(r"\D", "", text)
    if text.startswith("00"):
        text, digits = "+" + text[2:], digits[2:]
    if not text.startswith("+"):
        if len(digits) == 10:
            digits = "1" + digits
        elif not (len(digits) == 11 and digits.startswith("1")):
            return None
    if not MIN_DIGITS <= len(digits) <= MAX_DIGITS or digits.startswith("0"):
        return None
    return "+" + digits


def digits_only(text: str) -> str:
    return re.sub(r"\D", "", text)
