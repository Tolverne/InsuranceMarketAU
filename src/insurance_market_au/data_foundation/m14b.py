"""M1.4b — disclosure-aware soft calibration of the existing synthetic sample.

Fitting is restricted to the EIGHT original M1.3b training projections,
through the separately indexed *published aggregate* conditional table.
B26-14/16/17 are reserved exclusively for later holdout evaluation.

This is a weight-only adjustment. It CANNOT create missing model/postcode
combinations or turn the sample into an actual individual-vehicle register.
It NEVER mutates the M1.3b sample, never uses real unit-level Queensland
data, and exactly preserves EVERY original M1.3a state/type/year/fuel mass.

Model: damped, capped conditional raking on P(choice | publisher scope) with
publisher cell coverage gates, a regularization bound on weight drift,
and projection back onto the four-way M1.3a accounting cells after each step.
Publisher counts are disclosure-affected SOFT distributional targets and
are never treated as individual-level hard constraints.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import sqlite3

import numpy as np

from insurance_market_au.data_foundation.m1 import ROOT, REFERENCE_DATE, sha256_file
from insurance_market_au.data_foundation.m13 import TOTAL
from insurance_market_au.data_foundation.m13b import (
    HOLDOUT_SPECS, PATH_DB, PATH_REPORT, PATH_ROWS, TRAIN_SPECS,
    _atomic_json, _key, _load_base_joint, _require_pyarrow,
    prepare_conditionals,
)
from insurance_market_au.data_foundation.m14 import read_sample_predictions

VERSION = "m14b-soft-conditional-v1"
PATH_CALIBRATED = "data/processed/m14b/calibrated-weighted-fleet.parquet"
PATH_REPORT_CALIBRATED = "data/reports/m14b/calibration.json"
BASE_FIELDS = ("registered_state", "vehicle_type", "manufacture_year", "motive_power")
# Priority is set before evaluating ANY held-out projections.
ORDER = (
    "B26-15", "B26-07", "B26-05",  # make/model
    "B26-13", "B26-08", "B26-06", "B26-04",  # registration postcode
    "B26-09",  # independent garaging postcode
)


@dataclass
class Margin:
    pid: str
    row_to_pair: np.ndarray
    pair_to_scope: np.ndarray
    source_count: np.ndarray
    published_scope_total: np.ndarray
    eligible: np.ndarray
    coverage: np.ndarray
    scope_keys: int
    pairs: int
    positive_supported_cells: int
    eligible_scopes: int
    observed_source_mass_fraction_on_sample_support: float
    eligible_row_count: int


def _load_samples(root: Path, source: Path, source_report: Path):
    """Check source integrity without reading any excluded holdout."""
    pa, pq = _require_pyarrow()
    # Independent M1.4a hard check: all 64,008 (or fixture) base cell
    # expected masses, no mutated or fabricated sample rows.
    _pred, assurance = read_sample_predictions(root, source, source_report)
    table = pq.read_table(source)
    frame = table.to_pandas()
    report = json.loads(source_report.read_text(encoding="utf-8"))
    if not frame["is_synthetic"].all():
        raise ValueError("Cannot calibrate any observed/unit-level vehicle rows")
    if len(frame) != report["rows"]:
        raise ValueError("Sample row count does not match its original provenance")
    return table.schema, frame, assurance, report


def _source_targets(connection: sqlite3.Connection, pid: str,
                    scopes: list[str], choices: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Retrieve only requested published scope/choice aggregates.

    SQL source table was built and checksum validated by M1.3b; the SQL
    queries only read a single explicitly named original TRAIN projection.
    The withheld source names are forbidden, including during testing.
    """
    if pid not in TRAIN_SPECS or pid in HOLDOUT_SPECS:
        raise ValueError(f"Holdout/nontraining source used for calibration: {pid}")
    if len(scopes) != len(choices):
        raise ValueError("Invalid source group index length")
    connection.execute("DROP TABLE IF EXISTS temp.m14_req")
    connection.execute("DROP TABLE IF EXISTS temp.m14_scope")
    connection.execute("CREATE TEMP TABLE m14_req (scope TEXT NOT NULL, choice TEXT NOT NULL, PRIMARY KEY(scope,choice)) WITHOUT ROWID")
    connection.execute("CREATE TEMP TABLE m14_scope (scope TEXT PRIMARY KEY) WITHOUT ROWID")
    connection.executemany(
        "INSERT OR IGNORE INTO m14_req (scope,choice) VALUES (?,?)",
        zip(scopes, choices),
    )
    connection.executemany(
        "INSERT OR IGNORE INTO m14_scope (scope) VALUES (?)",
        ((s,) for s in dict.fromkeys(scopes)),
    )
    published = {
        (scope, choice): max(0.0, float(amount))
        for scope, choice, amount in connection.execute(
            "SELECT q.scope,q.choice,COALESCE(("
            "SELECT SUM(c.published_mass) FROM conditional c "
            "WHERE c.source_id=? AND c.scope=q.scope AND c.choice=q.choice"
            "),0) FROM m14_req q", (pid,),
        )
    }
    scope_totals = {
        scope: max(0.0, float(amount))
        for scope, amount in connection.execute(
            "SELECT q.scope,COALESCE(("
            "SELECT SUM(c.published_mass) FROM conditional c "
            "WHERE c.source_id=? AND c.scope=q.scope"
            "),0) FROM m14_scope q", (pid,),
        )
    }
    connection.execute("DROP TABLE m14_req")
    connection.execute("DROP TABLE m14_scope")
    return (
        np.array([published.get((s,c), 0.0) for s,c in zip(scopes, choices)],dtype=np.float64),
        np.array([scope_totals.get(s, 0.0) for s in scopes],dtype=np.float64),
    )


def _margin_index(frame, pid: str, connection: sqlite3.Connection,
                  *, min_cell: float, min_scope: float, min_coverage: float) -> Margin:
    import pandas as pd

    scope_fields, choice_fields = TRAIN_SPECS[pid]
    all_fields = (*scope_fields, *choice_fields)
    if any(x not in frame.columns for x in all_fields):
        raise ValueError(f"{pid}: sample missing a necessary publisher dimension")
    # A row group is a published dimension combination, *not* a matched
    # actual vehicle. Factorize preserves first-appearance order and the
    # original rows never leave local ignored data/.
    index = pd.MultiIndex.from_frame(frame.loc[:, list(all_fields)])
    code, unique = pd.factorize(index, sort=False)
    if np.any(code < 0):
        raise ValueError(f"{pid}: unknown/null category not supported for fitting")
    count = len(unique)
    scope_len = len(scope_fields)
    scopes = [_key(tuple(v[:scope_len])) for v in unique.tolist()]
    choices = [_key(tuple(v[scope_len:])) for v in unique.tolist()]
    source_counts, repeated_total = _source_targets(connection, pid, scopes, choices)
    scope_code, scope_values = pd.factorize(pd.Index(scopes), sort=False)
    scope_code = np.asarray(scope_code,dtype=np.int32)
    totals = np.zeros(len(scope_values), dtype=np.float64)
    # Repeated scope totals are the same by construction.
    totals[scope_code] = repeated_total
    eligible_cell = source_counts >= min_cell
    supported_mass = np.bincount(scope_code,
                                 weights=np.where(eligible_cell, source_counts, 0.0),
                                 minlength=len(totals))
    support_count = np.bincount(scope_code,
                                weights=eligible_cell.astype(np.float64),
                                minlength=len(totals))
    coverage = np.divide(supported_mass, totals, out=np.zeros_like(totals),
                         where=totals > 0)
    valid_scope = (
        (totals >= min_scope) & (coverage >= min_coverage)
        & (support_count >= 2)
    )
    eligible = eligible_cell & valid_scope[scope_code]
    row_to_pair = np.asarray(code, dtype=np.int32)
    return Margin(
        pid=pid, row_to_pair=row_to_pair,
        pair_to_scope=scope_code,
        source_count=source_counts,
        published_scope_total=totals,
        eligible=eligible,
        coverage=coverage,
        scope_keys=len(totals),
        pairs=count,
        positive_supported_cells=int(eligible_cell.sum()),
        eligible_scopes=int(valid_scope.sum()),
        observed_source_mass_fraction_on_sample_support=(
            float(supported_mass.sum() / totals.sum()) if totals.sum()>0 else 0.0
        ),
        eligible_row_count=int(eligible[row_to_pair].sum()),
    )


def _soft_objective(m: Margin, weights: np.ndarray) -> dict:
    """Conditional relative absolute fit on originally-supported keys.

    This is NOT direct publisher WAPE and is NOT a holdout metric. It only
    compares the conditional distribution on supported, eligible groups.
    """
    pair_mass = np.bincount(m.row_to_pair,weights=weights,minlength=m.pairs)
    e_source = np.where(m.eligible,m.source_count,0.0)
    e_model = np.where(m.eligible,pair_mass,0.0)
    scope_source = np.bincount(m.pair_to_scope,weights=e_source,
                              minlength=m.scope_keys)
    scope_model = np.bincount(m.pair_to_scope,weights=e_model,
                             minlength=m.scope_keys)
    source_share = np.divide(e_source,scope_source[m.pair_to_scope],
                             out=np.zeros_like(e_source),
                             where=scope_source[m.pair_to_scope]>0)
    target = scope_model[m.pair_to_scope] * source_share
    absolute = float(np.abs(e_model[m.eligible] - target[m.eligible]).sum())
    comparable = float(e_model.sum())
    return {
        "source_id":m.pid,
        "supported_sample_projection_keys":m.pairs,
        "published_positive_source_keys_on_sample_support":m.positive_supported_cells,
        "publisher_scopes_on_sample_support":m.scope_keys,
        "eligible_scopes":m.eligible_scopes,
        "eligible_sample_rows":m.eligible_row_count,
        "published_scope_mass_fraction_on_sample_support":m.observed_source_mass_fraction_on_sample_support,
        "comparable_weighted_mass":comparable,
        "within_scope_comparable_conditional_MAE_fraction":(
            absolute/comparable if comparable else None
        ),
        "not_full_source_WAPE":True,
        "missing_sample_keys_never_set_to_structural_zero":True,
    }


def _reconcile_fourway(w: np.ndarray, base_id: np.ndarray,
                       base_target: np.ndarray, min_mass: float = 1e-150) -> None:
    observed = np.bincount(base_id,weights=w,minlength=len(base_target))
    if np.any(observed < min_mass) or np.any(~np.isfinite(observed)):
        raise ValueError("A positive four-way support group was lost during fitting")
    w *= (base_target/observed)[base_id]
    if not np.all(np.isfinite(w)) or np.any(w<=0):
        raise ValueError("Nonfinite or nonpositive calibrated weight")


def _step(m: Margin, w: np.ndarray, *, relaxation: float,
          update_cap: float) -> None:
    if not m.eligible.any():
        return
    pair_mass = np.bincount(m.row_to_pair,weights=w,minlength=m.pairs)
    eligible_source = np.where(m.eligible,m.source_count,0.0)
    eligible_model = np.where(m.eligible,pair_mass,0.0)
    source_scope = np.bincount(m.pair_to_scope,weights=eligible_source,
                              minlength=m.scope_keys)
    model_scope = np.bincount(m.pair_to_scope,weights=eligible_model,
                             minlength=m.scope_keys)
    # Reconstruct target as conditional source share multiplied by the
    # *current model* mass over comparable keys in that publisher scope.
    target = np.zeros_like(pair_mass)
    ok = m.eligible & (source_scope[m.pair_to_scope]>0) & (model_scope[m.pair_to_scope]>0)
    target[ok] = (eligible_source[ok] / source_scope[m.pair_to_scope[ok]]) * model_scope[m.pair_to_scope[ok]]
    factors = np.ones(m.pairs,dtype=np.float64)
    valid = ok & (pair_mass>0)
    ratio = np.clip(target[valid]/pair_mass[valid],1/update_cap,update_cap)
    factors[valid] = np.power(ratio,relaxation)
    w *= factors[m.row_to_pair]


def calibrate(root: Path = ROOT, *, rounds: int = 4,
              relaxation: float = 0.35,
              update_cap: float = 1.6,
              relative_weight_cap: float = 8.0,
              min_cell: int = 10, min_scope: int = 100,
              min_coverage: float = 0.15,
              input_sample: Path | None = None,
              input_report: Path | None = None,
              output_path: Path | None = None,
              report_path: Path | None = None) -> dict:
    """Predeclared soft conditional raking; no held-out source is ever loaded.

    The existing uncalibrated synthetic sample and its M1.3b report stay
    immutable. The resulting *candidate* is never automatically promoted.
    """
    if (rounds<1 or rounds>30 or not 0<relaxation<=1
        or update_cap<=1 or relative_weight_cap<1
        or min_cell<1 or min_scope<1 or not 0<=min_coverage<=1):
        raise ValueError("Invalid soft calibration hyperparameters")
    if set(ORDER)!=set(TRAIN_SPECS) or set(ORDER)&set(HOLDOUT_SPECS):
        raise ValueError("Calibration training/heldout firewall was breached")

    pa,pq=_require_pyarrow()
    sample_path=input_sample or root / PATH_ROWS
    sample_report=input_report or root / PATH_REPORT
    final=output_path or root / PATH_CALIBRATED
    manifest_path=report_path or root / PATH_REPORT_CALIBRATED
    if sample_path.resolve()==final.resolve():
        raise ValueError("Never overwrite the baseline M1.3b sample")
    if sample_report.resolve()==manifest_path.resolve():
        raise ValueError("Never overwrite the baseline M1.3b report")
    provenance=prepare_conditionals(root)
    schema,frame,assurance,baseline_report=_load_samples(root,sample_path,sample_report)
    if provenance["version"]!=baseline_report["pipeline"]:
        raise ValueError("Stale original M1.3b conditioned source index")
    if provenance["sources"]!=baseline_report["source_fingerprints"]:
        raise ValueError("Original sample training source SHA differs from indexed source SHA")
    original=frame["expected_vehicle_weight"].to_numpy(dtype=np.float64,copy=True)
    if not np.all(np.isfinite(original)) or np.any(original<=0):
        raise ValueError("Baseline sample contains bad weights")
    from pandas import MultiIndex, factorize
    base_code, base_labels=factorize(MultiIndex.from_frame(frame[list(BASE_FIELDS)]),sort=False)
    base_code=np.asarray(base_code,dtype=np.int32)
    if np.any(base_code<0):
        raise ValueError("Unknown original four-way base key")
    original_base=np.bincount(base_code,weights=original,minlength=len(base_labels))
    if len(base_labels)!=assurance["four_way_support_cells"]:
        raise ValueError("Original base support would change")
    con=sqlite3.connect(f"file:{(root/PATH_DB).as_posix()}?mode=ro",uri=True)
    try:
        con.execute("PRAGMA temp_store=MEMORY")
        margins=[]
        for pid in ORDER:
            print(f"[M1.4b] Preparing training-only conditional margin {pid}",flush=True)
            margin=_margin_index(frame,pid,con,
                                 min_cell=min_cell,min_scope=min_scope,
                                 min_coverage=min_coverage)
            margins.append(margin)
    finally:
        con.close()
    before=[_soft_objective(m,original) for m in margins]
    w=original.copy()
    for iteration in range(rounds):
        for margin in margins:
            _step(margin,w,relaxation=relaxation,update_cap=update_cap)
            # Regularize row weights relative to their *precalibration*
            # weight. This stops runaway scaling of rare sampled choices.
            np.clip(w,original/relative_weight_cap,
                    original*relative_weight_cap,out=w)
            _reconcile_fourway(w,base_code,original_base)
        print(f"[M1.4b] Completed soft calibration round {iteration+1}/{rounds}",
              flush=True)
    after=[_soft_objective(m,w) for m in margins]
    base_after=np.bincount(base_code,weights=w,minlength=len(original_base))
    max_error=float(np.max(np.abs(base_after-original_base),initial=0))
    if (max_error>1e-5 or not np.all(np.isfinite(w))
        or np.any(w<=0) or abs(w.sum()-TOTAL)>0.1):
        raise ValueError(f"Calibrated four-way accounting invariant failed: {max_error}")
    if final.exists() and final.resolve()==sample_path.resolve():
        raise ValueError("Cannot overwrite original synthetic source")
    final.parent.mkdir(parents=True,exist_ok=True)
    partial=final.with_name(final.name+".partial")
    partial.unlink(missing_ok=True)
    try:
        frame["expected_vehicle_weight"]=w
        table=pa.Table.from_pandas(frame,schema=schema,preserve_index=False)
        pq.write_table(table,partial,compression="zstd")
        os.replace(partial,final)
    finally:
        partial.unlink(missing_ok=True)
    report={
        "pipeline":VERSION,
        "status":"conditional_weight_calibration_candidate_NOT_validated_population_release",
        "reference_date":REFERENCE_DATE,
        "original_m13b_sample":str(sample_path),
        "original_m13b_sha256":assurance["sample_sha256"],
        "original_m13b_report":str(sample_report),
        "original_m13b_rows":len(frame),
        "original_m13b_fourway_support":len(base_labels),
        "original_fourway_max_residual":assurance["max_four_way_mass_residual"],
        "calibrated_sample":str(final),
        "calibrated_sample_sha256":sha256_file(final),
        "calibrated_rows":len(frame),
        "calibrated_expected_mass":float(w.sum()),
        "max_fourway_mass_residual":max_error,
        "training_source_ids":list(ORDER),
        "heldout_ids_strictly_excluded":list(HOLDOUT_SPECS),
        "training_source_shas":provenance["sources"],
        "calibration":{
            "method":"capped_damped_conditional_soft_raking_with_exact_fourway_projection",
            "rounds":rounds,"relaxation":relaxation,
            "max_single_step_multiplier":update_cap,
            "relative_weight_cap":relative_weight_cap,
            "minimum_published_cell_for_fit":min_cell,
            "minimum_scope_published_mass_for_fit":min_scope,
            "minimum_supported_source_mass_fraction":min_coverage,
            "training_objectives_before":before,
            "training_objectives_after":after,
            "no_source_marginal_treated_as_exact_individual_vehicle_truth":True,
            "source_only_targets_on_existing_sample_support":True,
            "cannot_impute_missing_high_dimensional_support":True,
        },
        "governance":{
            "population_release_created":False,
            "holdout_used_for_parameter_selection":False,
            "automatic_promotion_to_production":False,
            "model_disclosure_uncertainty_estimated":False,
            "original_m13b_sample_mutated":False,
            "original_fourway_expected_masses_unchanged":True,
            "garaging_and_registered_postcodes_still_distinct":True,
            "note":"A conditional raking candidate is not evidence of real car-level make/model/postcode accuracy."
        }
    }
    _atomic_json(manifest_path,report)
    return report
