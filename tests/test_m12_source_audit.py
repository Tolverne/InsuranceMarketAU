"""Pinned evidence from full VIC, SA and NSW usage source profiling."""
import json
from insurance_market_au.data_foundation.m1 import ROOT

def test_verified_m12_source_metrics():
    o=json.loads((ROOT/"catalog/acquisition/m12-verified-state-source-audit.json").read_text())
    p={x["id"]:x for x in o["source_profiles"]}
    assert len(p)==4
    assert sum(x["rows"] for x in p.values())==2705225
    assert p["vic_model_q3_2026"]["published_numeric_cell_sum"]==6037154
    assert p["vic_postcode_q3_2026"]["published_numeric_cell_sum"]==6037154
    assert p["sa_registered_postcode_2026__84ab4212-cf51-44c5-90ff-e6ba93c681be"]["rows"]==764731
    assert p["nsw_usage_2026"]["members"]==10
    assert p["nsw_usage_2026"]["censored_rows"]==355660
    assert p["nsw_usage_2026"]["january_2026"]["published_row_sum_upper"]==7597139
    assert o["validation"]["vic_q3_2026_same_date_reported_total_delta"]==0
    assert not o["validation"]["safe_to_equate_to_BItre_registration_fleet"]
