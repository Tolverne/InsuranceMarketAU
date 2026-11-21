"""Pinned real-source M1.3a reproducibility metadata; not real vehicle truth."""
import json
from insurance_market_au.data_foundation.m1 import ROOT


def test_real_source_m13_baseline_manifest():
    d=json.loads((ROOT/"catalog/acquisition/m13-verified-national-pilot.json").read_text())
    assert d["workbook_operational_registered_vehicles"]==22771150
    assert d["synthetic_joint_cells"]==64008
    assert d["training_source_ids"]==["B26-01","B26-02","B26-03"]
    assert d["validation_source"]=="B26-10"
    assert d["calibrated_heldout_WAPE"]<d["baseline_heldout_WAPE"]
    assert d["unsupported_holdout_published_groups"]==0
    assert d["validation_policy"]["pseudo_independent_holdout_is_true_vehicle_truth"] is False
    cohorts={x["name"]:x for x in d["supported_age_cohorts"]}
    assert cohorts["before_1980"]["published_b26_10_cell_sum"]==256482
    assert cohorts["before_2000"]["holdout_WAPE"]<0.1
