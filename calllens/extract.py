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

    return None


def extract_entities(text: str | None) -> dict[str, int | None]:
    """Extracts both amount and due day from an utterance transcript."""
    return {
        "amount": extract_amount(text),
        "due_day": extract_due_day(text),
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
