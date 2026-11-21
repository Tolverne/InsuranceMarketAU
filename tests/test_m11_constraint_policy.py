"""Ensure M1.1 written constraint policies do not silently assert exact cells."""
import json
from pathlib import Path

from insurance_market_au.data_foundation.m1 import ROOT


def test_published_constraint_policy_blocks_false_precision() -> None:
    p=json.loads((ROOT/"catalog/constraints/bitre-2026-m11-policy.json").read_text())
    assert p["publisher_summary"]["reference_total"] == 22771150
    assert p["publisher_summary"]["formal_exact_statistical_constraint"] is False
    assert p["state_class_controls"]["formal_exact_statistical_constraint"] is False
    assert p["detailed_margins"]["strict_tolerance"] == "none_approved"
    assert "not_zero" in p["detailed_margins"]["unknown_or_absent_key"]
    assert p["model_validation"]["status"] == "not_yet_estimated"
