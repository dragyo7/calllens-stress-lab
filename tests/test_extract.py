"""Unit tests for BFSI entity extraction in calllens/extract.py."""

import pytest
from calllens.extract import (
    evaluate_entity_accuracy,
    extract_amount,
    extract_due_day,
    extract_entities,
)


def test_required_specification_examples():
    """Verify the four mandatory examples specified in BRIEF.md and Prompt:

    - 2.25 lakh -> 225000
    - 3,50,000 rupees -> 350000
    - ₹2.25 crore -> 22500000
    - 5 तारीख तक -> due_day 5
    """
    assert extract_amount("आपका बकाया 2.25 lakh है") == 225000
    assert extract_amount("कृपया 3,50,000 rupees जमा करें") == 350000
    assert extract_amount("कुल ऋण ₹2.25 crore स्वीकृत हुआ") == 22500000
    assert extract_due_day("कृपया 5 तारीख तक भुगतान करें") == 5


@pytest.mark.parametrize(
    "text,expected_amount",
    [
        ("लोन राशि 1.5 लाख है", 150000),
        ("आपका न्यूनतम भुगतान 10 हजार रुपये है", 10000),
        ("Please pay Rs. 75,500 immediately", 75500),
        ("स्वीकृत सीमा ₹ 50,000/- है", 50000),
        ("Transaction of INR 1,20,000 processed", 120000),
        ("प्रोजेक्ट लागत ₹ 10 crore है", 100000000),
        ("बकाया 50000 रुपया", 50000),
        ("amount is 2.5 lac", 250000),
        ("कुल 5 crores का निवेश", 50000000),
        ("कोई राशि नहीं है यहाँ", None),
    ],
)
def test_additional_amount_edge_cases(text, expected_amount):
    """Verify 10 additional amount extraction edge cases."""
    assert extract_amount(text) == expected_amount


@pytest.mark.parametrize(
    "text,expected_day",
    [
        ("अगली क़िस्त 15 तारीख को देय है", 15),
        ("दिनांक 25 तक जमा कराएं", 25),
        ("Your bill is due on the 10th", 10),
        ("Payment due by 31st of the month", 31),
        ("कृपया 1 तारीख को भुगतान करें", 1),
        ("Payment due by the 7th", 7),
        ("Date 18 is the last date", 18),
        ("ईएमआई 12 तारिख", 12),
        ("No date in this sentence at all", None),
        ("Only numbers 45 and 99 which are invalid days", None),
    ],
)
def test_additional_due_day_edge_cases(text, expected_day):
    """Verify 10 additional due-day extraction edge cases."""
    assert extract_due_day(text) == expected_day


def test_evaluate_entity_accuracy():
    """Verify entity accuracy evaluation metrics."""
    preds = [
        {"amount": 50000, "due_day": 5},
        {"amount": 100000, "due_day": 10},
        {"amount": 25000, "due_day": 12},  # amount wrong
    ]
    gt = [
        {"amount": 50000, "due_day": 5},
        {"amount": 100000, "due_day": 10},
        {"amount": 30000, "due_day": 12},
    ]

    metrics = evaluate_entity_accuracy(preds, gt)
    assert metrics["n"] == 3
    assert pytest.approx(2 / 3, rel=1e-3) == metrics["amount_accuracy"]
    assert metrics["due_day_accuracy"] == 1.0
    assert pytest.approx(2 / 3, rel=1e-3) == metrics["both_accuracy"]
