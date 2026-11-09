"""BFSI (Banking, Financial Services, and Insurance) entity extraction for Hindi/Hinglish.

Extracts:
1. Amounts: Normalized integer in Indian Rupees (INR).
   Handles:
   - "2.25 lakh" -> 225000
   - "3,50,000 rupees" -> 350000
   - "₹2.25 crore" -> 22500000
   - Lakh/crore/हज़ार/हजार/लाख/करोड़ representations
   - Comma-formatted numbers (Indian system)
   - Currency symbols and words (₹, Rs., Rs, INR, रुपये, रुपए)
2. Due Day: Integer day of month (1 to 31).
   Handles:
   - "5 तारीख तक" -> 5
   - "15 तारीख" -> 15
   - "due on the 10th" -> 10
   - "दिनांक 25" -> 25
"""

from __future__ import annotations

import re
from typing import Any

# Patterns for Amount Extraction
# 1. Lakh / Crore / Hazar with decimals or integers
# Examples: 2.25 lakh, 1.5 लाख, 2 करोड़, 50 हजार
MULTIPLIERS = {
    "lakh": 100_000,
    "lakhs": 100_000,
    "lac": 100_000,
    "lacs": 100_000,
    "लाख": 100_000,
    "लाखों": 100_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
    "cr": 10_000_000,
    "करोड़": 10_000_000,
    "करोड": 10_000_000,
    "thousand": 1_000,
    "thousands": 1_000,
    "k": 1_000,
    "हज़ार": 1_000,
    "हजार": 1_000,
}

MULT_PATTERN = re.compile(
    r"(?:₹|rs\.?|inr|रुपये|रुपए)?\s*(\d+(?:\.\d+)?)\s*(lakhs?|lacs?|lac|crores?|crore|cr|thousands?|thousand|लाखों|लाख|करोड़ों|करोड़|करोड|हज़ार|हजार)\b",
    re.IGNORECASE,
)

# Hindi Number Words Mapping
HINDI_NUMS = {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5,
    "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14, "पंद्रह": 15,
    "सोलह": 16, "सत्रह": 17, "अठारह": 18, "उन्नीस": 19, "बीस": 20,
    "इक्कीस": 21, "बाईस": 22, "तेईस": 23, "चौबीस": 24, "पच्चीस": 25,
    "छब्बीस": 26, "सत्ताईस": 27, "अट्ठाईस": 28, "अट्ठाइस": 28, "उनतीस": 29, "तीस": 30,
    "इकत्तीस": 31,
    "पचास": 50, "पचहत्तर": 75,
}

# Standard digit amounts with commas and optional currency symbols
# e.g., 3,50,000 rupees, ₹ 50,000, 10000/-
DIGIT_PATTERN = re.compile(
    r"(?:(?:₹|rs\.?|inr|रुपये|रुपए)\s*([\d,]+)(?:\s*(?:rupees?|रुपये|रुपए|/-))?)|(?:([\d,]+)\s*(?:rupees?|रुपये|रुपए|/-))",
    re.IGNORECASE,
)

# Due day patterns
# Examples: "5 तारीख तक", "15 तारीख", "due on the 10th", "by 25th", "दिनांक 12"
DUE_DAY_PATTERNS = [
    re.compile(r"(\b\d{1,2})\s*(?:तारीख|तारीख़|तारिख)", re.IGNORECASE),
    re.compile(r"(?:दिनांक|दिन)\s*(\b\d{1,2})", re.IGNORECASE),
    re.compile(r"(?:due|date|by|on)\s*(?:the\s*)?(\b\d{1,2})(?:st|nd|rd|th)?\b", re.IGNORECASE),
    re.compile(r"(\b\d{1,2})(?:st|nd|rd|th)\s*(?:of\s*)?(?:the\s*)?(?:month|january|february|march|april|may|june|july|august|september|october|november|december)?\b", re.IGNORECASE),
]


def extract_amount(text: str | None) -> int | None:
    """Extracts payment/loan amount from text in integer rupees.

    Returns None if no clear numeric amount is found.
    """
    if not text:
        return None

    # Check for multiplier forms first (e.g. "2.25 lakh", "₹2.25 crore")
    m_mult = MULT_PATTERN.search(text)
    if m_mult:
        val_str, unit = m_mult.groups()
        unit_lower = unit.lower()
        multiplier = MULTIPLIERS.get(unit_lower, 1)
        try:
            return int(round(float(val_str) * multiplier))
        except ValueError:
            pass

    # Check for standard formatted digits
    for m in DIGIT_PATTERN.finditer(text):
        g1, g2 = m.groups()
        val_str = g1 or g2
        if val_str:
            clean_digits = val_str.replace(",", "").strip()
            if clean_digits.isdigit():
                val = int(clean_digits)
                # Avoid capturing single-digit days as amounts unless explicit currency
                if val > 31 or (g1 and any(c in m.group(0).lower() for c in ["₹", "rs", "inr", "रुप"])):
                    return val

    # Check Hindi spoken decimal patterns: e.g. "दो दशमलव दो पाँच करोड़" / "दो दशमलव दो पाँच लाख"
    m_dec = re.search(
        r"(एक|दो|तीन|चार|पाँच|पांच)\s*दशमलव\s*(एक|दो|तीन|चार|पाँच|पांच)\s*(?:(एक|दो|तीन|चार|पाँच|पांच)\s*)?(लाख|करोड़|करोड)",
        text,
        re.IGNORECASE,
    )
    if m_dec:
        w_int, w_d1, w_d2, unit = m_dec.groups()
        val_str = f"{HINDI_NUMS[w_int]}.{HINDI_NUMS[w_d1]}" + (f"{HINDI_NUMS[w_d2]}" if w_d2 else "")
        mult = 100_000 if "लाख" in unit else 10_000_000
        return int(round(float(val_str) * mult))

    # Check Hindi compound spoken word numbers: e.g. "तीन लाख पचास हज़ार", "पचहत्तर हज़ार पाँच सौ"
    hindi_total = 0
    found_hindi = False
    m_lakh = re.search(r"(एक|दो|तीन|चार|पाँच|पांच)\s*लाख", text)
    if m_lakh:
        hindi_total += HINDI_NUMS[m_lakh.group(1)] * 100_000
        found_hindi = True

    m_haz = re.search(r"(दस|पंद्रह|बीस|पच्चीस|पचास|पचहत्तर)\s*(?:हज़ार|हजार)", text)
    if m_haz:
        hindi_total += HINDI_NUMS[m_haz.group(1)] * 1_000
        found_hindi = True

    m_sau = re.search(r"(पाँच|पांच)\s*सौ", text)
    if m_sau:
        hindi_total += HINDI_NUMS[m_sau.group(1)] * 100
        found_hindi = True

    if found_hindi:
        return hindi_total

    # Fallback: scan for any standalone 4+ digit number
    fallback_match = re.search(r"\b(\d{4,9})\b", text)
    if fallback_match:
        return int(fallback_match.group(1))

    return None


def extract_due_day(text: str | None) -> int | None:
    """Extracts day of month (1-31) representing due date.

    Returns None if no valid day is found.
    """
    if not text:
        return None

    for pat in DUE_DAY_PATTERNS:
        match = pat.search(text)
        if match:
            day_str = match.group(1)
            try:
                day = int(day_str)
                if 1 <= day <= 31:
                    return day
            except ValueError:
                continue

    # Check spoken Hindi number word for due day (e.g. "पाँच तारीख", "दिनांक अट्ठाईस")
    for word, val in HINDI_NUMS.items():
        if re.search(rf"{word}\s*(?:तारीख|तारीख़|तारिख)", text, re.IGNORECASE) or re.search(rf"दिनांक\s*{word}", text, re.IGNORECASE):
            return val

    return None


def extract_entities(text: str | None) -> dict[str, int | None]:
    """Extracts both amount and due day from an utterance transcript."""
    return {
        "amount": extract_amount(text),
        "due_day": extract_due_day(text),
    }


# Customer concern detection rules
CONCERN_RULES = [
    {
        "category": "salary_delay",
        "label": "Salary delay (वेतन में देरी)",
        "pattern": re.compile(
            r"(?:वेतन|सैलरी|salary|tankhwah|तनख्वाह|पेमेंट लेट|delay|देरी|पैसा नहीं आया|सैलरी अभी नहीं|तनखा)",
            re.IGNORECASE,
        ),
    },
    {
        "category": "technical_failure",
        "label": "Technical / Banking transaction failure (तकनीकी विफलता)",
        "pattern": re.compile(
            r"(?:सर्वर डाउन|server down|transaction fail|पेमेंट फेल|खाते से कट गया|कट गए|technical issue|upi fail|bank error|तकनीकी समस्या|डिडक्ट)",
            re.IGNORECASE,
        ),
    },
    {
        "category": "dispute_charges",
        "label": "Disputed late fee / penalty charges (अतिरिक्त शुल्क विवाद)",
        "pattern": re.compile(
            r"(?:गलत चार्ज|dispute|penalty|पेनल्टी|extra charge|गलत बिल|चार्ज हटाओ|disputed|ब्याज ज्यादा|extra interest|अतिरिक्त शुल्क)",
            re.IGNORECASE,
        ),
    },
    {
        "category": "medical_emergency",
        "label": "Medical / Family emergency (चिकित्सा आपातकाल)",
        "pattern": re.compile(
            r"(?:तबीयत खराब|hospital|अस्पताल|medical|बीमार|इलाज|emergency|इमरजेंसी|दुर्घटना|दवा)",
            re.IGNORECASE,
        ),
    },
    {
        "category": "out_of_station",
        "label": "Customer out of station / traveling (शहर से बाहर)",
        "pattern": re.compile(
            r"(?:शहर से बाहर|out of station|गांव गया|गाँव|travel|यात्रा|बाहर हूं|out of town|सफर)",
            re.IGNORECASE,
        ),
    },
    {
        "category": "extension_request",
        "label": "Request for payment extension (समय सीमा विस्तार)",
        "pattern": re.compile(
            r"(?:समय चाहिए|वक्त दीजिए|कुछ दिन|next week|अगले हफ्ते|समय दें|mohlata|मोहल्लत|तारीख बढ़ा)",
            re.IGNORECASE,
        ),
    },
]

PTP_PATTERNS = [
    # e.g. "10 तारीख को पे कर दूंगा", "20 तारीख तक भर दूंगा", "15th को transfer"
    re.compile(
        r"(\b\d{1,2})\s*(?:तारीख|तारीख़|तारिख|th|st|nd|rd)?\s*(?:को|तक)?\s*(?:पे|पेमेंट|दूँगा|दूंगा|देंगे|भर|भरेंगे|भरूंगा|डाल|ट्रांसफर|pay|clear|transfer|जमा)",
        re.IGNORECASE,
    ),
    # e.g. "pay by 10th", "transfer on 25th", "पे करूंगा 10 तारीख को"
    re.compile(
        r"(?:पे|पेमेंट|pay|clear|transfer|भरूंगा|भरेंगे|दूँगा|दूंगा|देंगे|जमा)\s*(?:तक|को|on|by)?\s*(?:the\s*)?(\b\d{1,2})(?:st|nd|rd|th|\s*(?:तारीख|तारीख़|तारिख))",
        re.IGNORECASE,
    ),
    # Named day / relative dates
    re.compile(
        r"(\b(?:कल|परसों|सोमवार|मंगलवार|बुधवार|गुरुवार|शुक्रवार|शनिवार|रविवार|tomorrow|next\s+week)\b(?:\s*(?:तक|को))?)",
        re.IGNORECASE,
    ),
]


def extract_ptp_date(text: str | None, due_day: int | None = None) -> str | None:
    """Extracts Promise-To-Pay (PTP) date or commitment commitment from dialogue.

    Returns None if no promise date is found.
    """
    if not text:
        return None

    for pat in PTP_PATTERNS:
        for m in pat.finditer(text):
            val = m.group(1).strip()
            # If numeric day
            if val.isdigit():
                day = int(val)
                if 1 <= day <= 31:
                    # If this matches due_day exactly, continue searching next match
                    if due_day and day == due_day:
                        continue
                    return f"{day} तारीख"
            else:
                return val

    # Hindi number words for PTP date (e.g. "दस तारीख को दूंगा")
    for word, num in HINDI_NUMS.items():
        if re.search(rf"{word}\s*तारीख\s*(?:को|तक)?\s*(?:दूंगा|दूँगा|पे|भर|ट्रांसफर)", text, re.IGNORECASE):
            if due_day and num == due_day:
                continue
            return f"{num} तारीख"

    return None


def extract_customer_concern(text: str | None) -> dict[str, str]:
    """Identifies the customer's primary reason or dispute from the conversation."""
    if not text:
        return {
            "category": "general",
            "label": "Standard payment reminder (सामान्य भुगतान अनुस्मारक)",
        }

    for rule in CONCERN_RULES:
        if rule["pattern"].search(text):
            return {
                "category": rule["category"],
                "label": rule["label"],
            }

    return {
        "category": "general",
        "label": "Standard payment reminder (सामान्य भुगतान अनुस्मारक)",
    }


def extract_followup_details(
    text: str | None,
    customer_name: str | None = None,
) -> dict[str, Any]:
    """Extracts complete follow-up details from a customer service or collection call.

    Extracts:
    1. Outstanding amount (int or None)
    2. Original due day (int or None)
    3. Promise-to-pay date (str or None)
    4. Customer concern (str)
    5. Call summary (str)
    6. Suggested Timbre TTS reminder draft (str)

    Never silently assumes missing values.
    """
    if not text:
        return {
            "amount": None,
            "amount_formatted": "Not detected",
            "due_day": None,
            "due_date_formatted": "Not detected",
            "ptp_date": None,
            "ptp_date_formatted": "Not detected",
            "customer_name": customer_name or "ग्राहक",
            "concern": "No dialogue text detected",
            "concern_category": "none",
            "call_summary": "No audio transcript available for analysis.",
            "suggested_reminder": "नमस्ते, कृपया अपने खाते की बकाया राशि का भुगतान करें। धन्यवाद।",
            "is_complete": False,
        }

    amount = extract_amount(text)
    due_day = extract_due_day(text)
    ptp_date = extract_ptp_date(text, due_day=due_day)
    concern_info = extract_customer_concern(text)

    # Name extraction heuristic (e.g., "राहुल शर्मा जी", "हेलो प्रिया वर्मा")
    detected_name = customer_name
    if not detected_name:
        m_name = re.search(
            r"(?:नमस्ते|हेलो|प्रिय|श्रीमान|hello|dear)\s+([A-Za-z\u0900-\u097F]+(?:\s+[A-Za-z\u0900-\u097F]+)?)\s*(?:जी|,|\b)",
            text,
            re.IGNORECASE,
        )
        if m_name:
            cand = m_name.group(1).strip()
            if len(cand) > 2 and cand.lower() not in ["aapka", "sir", "madam", "ji", "aapki"]:
                detected_name = cand

    c_name = detected_name or "ग्राहक"
    amount_str = f"₹{amount:,.0f}" if amount is not None else "Not detected"
    due_str = f"{due_day} तारीख" if due_day is not None else "Not detected"
    ptp_str = ptp_date if ptp_date is not None else "Not detected"

    # Call summary generation
    summary_parts = []
    if amount is not None:
        summary_parts.append(f"बकाया राशि {amount_str}")
    if due_day is not None:
        summary_parts.append(f"देय तिथि {due_str}")
    if concern_info["category"] != "general":
        summary_parts.append(f"ग्राहक का विषय: {concern_info['label']}")
    if ptp_date:
        summary_parts.append(f"वचनबद्ध भुगतान तिथि (PTP): {ptp_str}")

    if not summary_parts:
        call_summary = "सामान्य कॉल विवरण: कोई विशिष्ट वित्तीय आंकड़े नहीं मिले।"
    else:
        call_summary = " • ".join(summary_parts) + "।"

    # Natural reminder synthesis template for Timbre TTS
    if ptp_date and amount is not None:
        suggested_reminder = (
            f"नमस्ते {c_name} जी, आपके खाते का {amount_str} का भुगतान {ptp_str} तक "
            f"करने का आपका वादा था। असुविधा से बचने के लिए कृपया समय पर भुगतान करें। धन्यवाद।"
        )
    elif amount is not None and due_day is not None:
        suggested_reminder = (
            f"नमस्ते {c_name} जी, आपके खाते की बकाया राशि {amount_str} की देय तिथि {due_str} है। "
            f"विलंब शुल्क से बचने के लिए कृपया आज ही भुगतान करें। धन्यवाद।"
        )
    elif amount is not None:
        suggested_reminder = (
            f"नमस्ते {c_name} जी, आपके खाते की बकाया राशि {amount_str} देय है। "
            f"कृपया अतिशीघ्र भुगतान पूरा करें। धन्यवाद।"
        )
    else:
        suggested_reminder = (
            f"नमस्ते {c_name} जी, यह आपके खाते के संबंध में बैंक से एक महत्वपूर्ण सूचना है। "
            f"कृपया तुरंत संपर्क करें। धन्यवाद।"
        )

    return {
        "amount": amount,
        "amount_formatted": amount_str,
        "due_day": due_day,
        "due_date_formatted": due_str,
        "ptp_date": ptp_date,
        "ptp_date_formatted": ptp_str,
        "customer_name": c_name,
        "concern": concern_info["label"],
        "concern_category": concern_info["category"],
        "call_summary": call_summary,
        "suggested_reminder": suggested_reminder,
        "is_complete": (amount is not None and due_day is not None),
    }


def evaluate_entity_accuracy(
    predictions: list[dict[str, int | None]],
    ground_truth: list[dict[str, int | None]],
) -> dict[str, float]:
    """Computes exact-match accuracy for amounts and due days."""
    if not predictions or not ground_truth or len(predictions) != len(ground_truth):
        return {"amount_accuracy": 0.0, "due_day_accuracy": 0.0, "both_accuracy": 0.0, "n": 0}

    total = len(predictions)
    amount_correct = 0
    due_day_correct = 0
    both_correct = 0

    for pred, gt in zip(predictions, ground_truth):
        amt_match = (pred.get("amount") == gt.get("amount"))
        day_match = (pred.get("due_day") == gt.get("due_day"))

        if amt_match:
            amount_correct += 1
        if day_match:
            due_day_correct += 1
        if amt_match and day_match:
            both_correct += 1

    return {
        "amount_accuracy": round(amount_correct / total, 4),
        "due_day_accuracy": round(due_day_correct / total, 4),
        "both_accuracy": round(both_correct / total, 4),
        "n": total,
    }
