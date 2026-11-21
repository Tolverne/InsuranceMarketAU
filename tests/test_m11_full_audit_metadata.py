"""Preserve key metrics from the verified real 17-source M1.1 audit."""
import json
from insurance_market_au.data_foundation.m1 import ROOT


def test_full_audit_reproducibility_manifest() -> None:
    m=json.loads((ROOT/"catalog/acquisition/bitre-2026-m11-full-audit.json").read_text())
    assert m["number_of_independent_projections"] == 17
    assert m["table1_control_cells"] == 99
    assert m["table1_internal_nonzero_additivity_checks"] == 0
    assert m["source_universe_population_published_total"] == 22771150
    assert m["total_published_aggregate_rows_across_projections"] == 12181645
    assert m["count_of_nonnumeric_count_rows"] == 0
    assert m["number_of_pairwise_margin_comparisons"] == 47
    assert sum(x["comparison_count"] for x in m["comparable_margins"]) == 47
    assert all(x["maximum_abs_difference"] >= 0 for x in m["comparable_margins"])
    assert m["number_of_pairs_with_at_least_one_nonzero_residual"] == 47
    assert "requiring_M1.3_review" in m["status"]
