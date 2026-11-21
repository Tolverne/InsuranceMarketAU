"""M1.4a: independent published-holdout diagnostics and Monte Carlo sensitivity.

This module never fits a model, changes published controls, or draws from a
holdout. It audits the current M1.3b synthetic sample against B26-14 and can
generate isolated replicate samples using different predeclared random seeds
and sample sizes. The published B26-14 projection remains strictly excluded
from conditioning and M1.3b sampling.

Outputs are aggregate diagnostics only, under ignored data/reports/m14.
A low source-cell WAPE is NOT vehicle-level or insurance-policy accuracy.
"""
from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import numpy as np

from insurance_market_au.data_foundation.m1 import ROOT, REFERENCE_DATE, load_bitre_catalog, sha256_file
from insurance_market_au.data_foundation.m13 import TOTAL
from insurance_market_au.data_foundation.m13b import (
    HOLDOUT_SPECS, PATH_REPORT, PATH_ROWS, TRAIN_SPECS,
    _atomic_json, _load_base_joint, _require_pyarrow,
    _source_rows, build_weighted_sample,
)

VERSION = "m14a-independent-validation-v1"
HELDOUT_ID = "B26-14"
DIMENSIONS = HOLDOUT_SPECS[HELDOUT_ID]
CURRENT_REPORT = "data/reports/m14/current-diagnostics.json"
SENSITIVITY_REPORT = "data/reports/m14/sampling-sensitivity.json"
MIN_PUBLISHED = 100
MIN_DISCLOSURE_SAFE_SUM = 1000
MIN_DISCLOSURE_SAFE_CELLS = 3

# These bands are disjoint. The three inclusive older-than cohorts below
# deliberately overlap and are *not* added together.
BANDS = (
    ("before_1980", None, 1979),
    ("1980s", 1980, 1989),
    ("1990s", 1990, 1999),
    ("2000s", 2000, 2009),
    ("2010s", 2010, 2019),
    ("2020_onward", 2020, None),
)


def read_heldout_reference(root: Path = ROOT, *,
                           minimum_published: int = MIN_PUBLISHED) -> tuple[dict[tuple[str, ...], int], dict]:
    """Load only originally published B26-14 cells at/above a declared threshold.

    We validate all source rows/date/lineage/national totals using M1.0's
    source-specific source contract. Unpublished/suppressed/missing cells
    must never be treated as true physical zeros.
    """
    if minimum_published < 100:
        raise ValueError("M1.4a disclosure-aware public diagnostics require a threshold >=100")
    catalogue = {x["projection_id"]: x for x in load_bitre_catalog(root)}
    if HELDOUT_ID in TRAIN_SPECS:
        raise ValueError("Heldout B26-14 cannot enter the sampler's training sources")
    source = catalogue[HELDOUT_ID]
    observed: dict[tuple[str, ...], int] = defaultdict(int)
    original_source_rows = 0
    discarded_rows = 0
    for batch in _source_rows(source, DIMENSIONS, root=root):
        for key, value in batch:
            original_source_rows += 1
            if value < minimum_published:
                discarded_rows += 1
                continue
            observed[key] += value
    meta = {
        "id": HELDOUT_ID,
        "sha256": source["sha256"],
        "reference_date": REFERENCE_DATE,
        "dimensions": list(DIMENSIONS),
        "threshold": minimum_published,
        "source_rows_excluding_publisher_totals": original_source_rows,
        "excluded_below_threshold_rows": discarded_rows,
        "included_source_rows_at_or_above_threshold": original_source_rows - discarded_rows,
        "included_unique_published_keys": len(observed),
        "non_numeric_suppression_not_imputed": True,
        "holdout_used_for_sampler": False,
    }
    if not observed:
        raise ValueError(f"No published B26-14 cells >= {minimum_published}")
    return dict(observed), meta


def _year(value: Any) -> int | None:
    if isinstance(value, str) and len(value) == 4 and value.isdecimal():
        return int(value)
    return None


def _band(key: tuple[str, ...]) -> str:
    year = _year(key[1])  # B26-14: class/year/fuel/make/model
    if year is None:
        return "unknown_year"
    for label, low, high in BANDS:
        if (low is None or year >= low) and (high is None or year <= high):
            return label
    return "unclassified_year"


def read_sample_predictions(
    root: Path, sample_path: Path, sample_report: Path
) -> tuple[dict[tuple[str, ...], float], dict]:
    """Validate *every* four-way expected cell, not just the national total.

    The base table is immutable; a discrepancy, stale source or missing
    synthetic cell aborts diagnostic publication instead of hiding it.
    """
    _, pq = _require_pyarrow()
    if not sample_path.is_file() or not sample_report.is_file():
        raise FileNotFoundError("Missing synthetic sample/report; run py -3 scripts/m13b_expand.py --rows 220000")
    report = json.loads(sample_report.read_text(encoding="utf-8"))
    if (report.get("status") != "weighted_synthetic_analytic_POC_not_fleet_release"
        or report.get("reference_date") != REFERENCE_DATE
        or set(report.get("training_projections", [])) != set(TRAIN_SPECS)
        or set(report.get("heldout_projections_excluded_from_sampling", [])) != set(HOLDOUT_SPECS)
        or report.get("source_microdata_linkage_performed") is not False
        or Path(report.get("sample_file", "")).resolve() != sample_path.resolve()):
        raise ValueError("Sample report lineage, holdout isolation, or file identity differs from the M1.3b contract")
    base, weights, prior = _load_base_joint(root)
    base_columns = ("registered_state", "vehicle_type", "manufacture_year", "motive_power")
    base_expectation = {
        tuple(base[f][i] for f in base_columns): float(weights[i])
        for i in range(len(weights))
    }
    if len(base_expectation) != len(weights):
        raise ValueError("Duplicate four-way support keys in M1.3a")
    got = defaultdict(float)
    predicted = defaultdict(float)
    row_count = 0
    total = 0.0
    sum_squares = 0.0
    parquet = pq.ParquetFile(sample_path)
    required = set((*base_columns, "make", "model", "expected_vehicle_weight",
                    "is_synthetic"))
    if not required <= set(parquet.schema_arrow.names):
        raise ValueError(f"Expected source-safe synthetic attributes missing: {required - set(parquet.schema_arrow.names)}")
    for batch in parquet.iter_batches(batch_size=30000, columns=sorted(required)):
        data = batch.to_pydict()
        for i in range(batch.num_rows):
            mass = data["expected_vehicle_weight"][i]
            if (not data["is_synthetic"][i] or mass is None
                    or not isinstance(mass, (float, int))
                    or not math.isfinite(mass) or mass <= 0):
                raise ValueError("Only finite positive synthetic expected mass can enter validation")
            base_key = tuple(data[k][i] for k in base_columns)
            if base_key not in base_expectation:
                raise ValueError("Synthetic sample contains a combination outside original M1.3a base support")
            high_key = tuple(data[k][i] for k in DIMENSIONS)
            if any(v is None for v in high_key):
                raise ValueError("M1.3b sample contains an unclassified null attribute")
            mass = float(mass)
            got[base_key] += mass
            predicted[high_key] += mass
            total += mass
            sum_squares += mass * mass
            row_count += 1
    if row_count != report.get("rows") or row_count != parquet.metadata.num_rows:
        raise ValueError("Weighted sample row count differs from its report")
    if len(got) != len(base_expectation):
        raise ValueError("At least one M1.3a base support cell was dropped")
    discrepancies = [
        abs(observed - base_expectation[key])
        for key, observed in got.items()
    ]
    max_error = max(discrepancies, default=math.inf)
    if (max_error > 1e-5 or abs(total - TOTAL) > 0.1 or
            abs(float(report.get("weighted_total_expected", -1)) - TOTAL) > 0.1):
        raise ValueError(f"Four-way synthetic mass not preserved: max cell residual={max_error}")
    return dict(predicted), {
        "sample_sha256": sha256_file(sample_path),
        "sample_file": str(sample_path),
        "sample_size_bytes": sample_path.stat().st_size,
        "sample_mtime_ns": sample_path.stat().st_mtime_ns,
        "sample_report": str(sample_report),
        "sample_rows": row_count,
        "seed": report["seed"],
        "total_expected_vehicles": total,
        "four_way_support_cells": len(got),
        "max_four_way_mass_residual": max_error,
        "weighted_sample_ESS": total * total / sum_squares if sum_squares else 0.0,
        "source_microdata_linkage_performed": False,
    }


def _stats(values: list[tuple[int, float]]) -> dict:
    published = float(sum(v for v, _ in values))
    fitted = float(sum(p for _, p in values))
    covered = sum(p > 0 for _, p in values)
    absolute = float(sum(abs(p - v) for v, p in values))
    absolute_residuals = [abs(p - v) for v, p in values]
    return {
        "published_reference_mass": published,
        "synthetic_expected_mass_on_same_cells": fitted,
        "source_cell_count": len(values),
        "sample_supported_source_cells": covered,
        "sample_support_fraction": covered / len(values) if values else None,
        "published_cell_WAPE": absolute / published if published else None,
        "net_percentage_bias": (fitted - published) / published if published else None,
        "median_absolute_cell_error": float(np.median(absolute_residuals)) if values else None,
        "p90_absolute_cell_error": float(np.percentile(absolute_residuals, 90)) if values else None,
        "not_individual_vehicle_ground_truth": True,
    }


def compare_reference(
    published: dict[tuple[str, ...], int],
    estimated: dict[tuple[str, ...], float],
) -> dict:
    """Compute published-cell error and transparent classic/rare cohort splits.

    All keys have already passed the >=100 *published row* threshold.
    Make/model aggregates are surfaced only if they cover at least three
    distinct published cells and total published mass >=1,000.
    """
    if not published:
        raise ValueError("No source cells to compare")
    if any(v < MIN_PUBLISHED for v in published.values()):
        raise ValueError("Included source cells should meet the published threshold")
    pairs = [(key, count, max(0.0, float(estimated.get(key, 0.0))))
             for key, count in published.items()]
    if any(not math.isfinite(p) for _, _, p in pairs):
        raise ValueError("Nonfinite fitted prediction")
    groups: dict[str, dict[str, list[tuple[int, float]]]] = {
        "age_band": defaultdict(list),
        "vehicle_type": defaultdict(list),
        "make": defaultdict(list),
        "historic_make": defaultdict(list),
        "published_count_band": defaultdict(list),
    }
    overlapping: dict[str, list[tuple[int, float]]] = {
        "before_1980": [], "before_1990": [], "before_2000": []
    }
    for key, v, p in pairs:
        typ, year, fuel, make, model = key
        band = _band(key)
        datum = (v, p)
        groups["age_band"][band].append(datum)
        groups["vehicle_type"][typ].append(datum)
        groups["make"][make].append(datum)
        if _year(year) is not None and _year(year) < 1990:
            groups["historic_make"][make].append(datum)
        boundary = ("100-499" if v < 500 else
                    "500-999" if v < 1000 else
                    "1000-9999" if v < 10000 else "10000+")
        groups["published_count_band"][boundary].append(datum)
        numeric = _year(year)
        if numeric is not None:
            for cutoff in (1980, 1990, 2000):
                if numeric < cutoff:
                    overlapping[f"before_{cutoff}"].append(datum)
    result = {}
    for family, keyed in groups.items():
        candidates = []
        for name, entries in keyed.items():
            metric = _stats(entries)
            if family in {"make", "historic_make"}:
                if (metric["source_cell_count"] < MIN_DISCLOSURE_SAFE_CELLS
                    or metric["published_reference_mass"] < MIN_DISCLOSURE_SAFE_SUM):
                    continue
            candidates.append({"label": name, **metric})
        if family in {"make", "historic_make"}:
            candidates.sort(key=lambda x: (-x["published_reference_mass"], x["label"]))
            result[family] = candidates[:35]
        else:
            result[family] = sorted(candidates, key=lambda x: x["label"])
    unexplained_positive_model = sum(
        v for key, v in estimated.items() if key not in published
    )
    all_source = _stats([(v, p) for _, v, p in pairs])
    return {
        "overall": all_source,
        "cohorts_overlap_do_not_add_them": {
            name: _stats(entries) for name, entries in overlapping.items()
        },
        "segments": result,
        "modelled_mass_on_non_comparable_keys": unexplained_positive_model,
        "modelled_mass_note": (
            "Mass on unlisted or below-threshold publisher keys is not an error "
            "measure: absence, suppression and disclosure adjustments do not imply zero."
        ),
        "interpretation": (
            "Published B26-14 ≥100 cell WAPE against a finite weighted synthetic "
            "sample, not predictive error versus physical vehicles; high-order "
            "cell sparsity and Monte Carlo variation both contribute."
        ),
        "tuning_with_holdout": False,
    }


def audit_current(
    root: Path = ROOT, *, minimum_published: int = MIN_PUBLISHED,
    sample_path: Path | None = None, sample_report: Path | None = None,
    report_path: Path | None = None,
) -> dict:
    """Audit existing sample WITHOUT rewriting the sample or M1.3b report."""
    source = sample_path or root / PATH_ROWS
    report = sample_report or root / PATH_REPORT
    predicted, sample = read_sample_predictions(root, source, report)
    published, reference = read_heldout_reference(root, minimum_published=minimum_published)
    metrics = compare_reference(published, predicted)
    result = {
        "pipeline": VERSION,
        "status": "independent_publisher_projection_diagnostics_not_release_certification",
        "reference_date": REFERENCE_DATE,
        "published_total_accounting_anchor": TOTAL,
        "model_version": "M1.3b",
        "heldout_source": reference,
        "sample": sample,
        "metrics": metrics,
        "population_release_created": False,
        "source_margins_recalibrated": False,
        "uncertainty_interpretation": "source residual + Monte Carlo variation; neither is a calibrated source-error interval",
        "next_step": "Separate Monte Carlo sensitivity from systematic conditional-model mismatch before calibration.",
    }
    _atomic_json(report_path or root / CURRENT_REPORT, result)
    return result


def sensitivity(
    root: Path = ROOT, *, sizes: tuple[int, ...] = (85000, 220000),
    seeds: tuple[int, ...] = (17, 53, 91),
    minimum_published: int = MIN_PUBLISHED,
    retain_samples: bool = False,
) -> dict:
    """Predeclared seed/size sensitivity with isolated temporary output paths.

    Original M1.3b viewer output is never touched. The holdout is not
    consulted during generation; all replicates are built before the
    B26-14 comparison is loaded. It is a sensitivity study, not a CI.
    """
    if (not sizes or not seeds or len(sizes) * len(seeds) > 12
        or len(set(seeds)) != len(seeds)
        or any(s < 1 or s > 2_000_000 for s in sizes)
        or any(seed < 0 for seed in seeds)):
        raise ValueError("Require 1–12 replicate runs using positive sizes and unique nonnegative seeds")
    _, weights, _ = _load_base_joint(root)
    support = int(np.count_nonzero(weights > 0))
    if any(s < support for s in sizes):
        raise ValueError(f"Sample sizes must each cover all {support:,} positive four-way source support cells")
    locations: list[tuple[int,int,Path,Path]] = []
    for size in sizes:
        for seed in seeds:
            output = root / f"data/processed/m14/replicates/n{size}-seed{seed}.parquet"
            audit = root / f"data/reports/m14/replicates/n{size}-seed{seed}.json"
            print(f"[M1.4a] Generating isolated replicate n={size:,}, seed={seed}", flush=True)
            try:
                build_weighted_sample(root, rows=size, seed=seed,
                                      output_path=output, report_path=audit)
            except Exception:
                # Never leave a partially built simulation counted as a
                # valid diagnostic or modify the original explorer sample.
                if not retain_samples:
                    output.unlink(missing_ok=True)
                    audit.unlink(missing_ok=True)
                raise
            locations.append((size, seed, output, audit))
    # Reserve the independent publication until AFTER every sample exists.
    published, reference = read_heldout_reference(root, minimum_published=minimum_published)
    runs = []
    try:
        for size, seed, output, audit in locations:
            estimates, sample = read_sample_predictions(root, output, audit)
            diagnostics = compare_reference(published, estimates)
            runs.append({
                "sample_size": size, "seed": seed,
                "heldout_B26_14_WAPE": diagnostics["overall"]["published_cell_WAPE"],
                "published_key_coverage": diagnostics["overall"]["sample_support_fraction"],
                "before_1980_WAPE": diagnostics["cohorts_overlap_do_not_add_them"]["before_1980"]["published_cell_WAPE"],
                "before_1990_WAPE": diagnostics["cohorts_overlap_do_not_add_them"]["before_1990"]["published_cell_WAPE"],
                "before_2000_WAPE": diagnostics["cohorts_overlap_do_not_add_them"]["before_2000"]["published_cell_WAPE"],
                "max_four_way_mass_residual": sample["max_four_way_mass_residual"],
                "synthetic_sample_ESS": sample["weighted_sample_ESS"],
            })
    finally:
        if not retain_samples:
            for _, _, output, audit in locations:
                output.unlink(missing_ok=True)
                audit.unlink(missing_ok=True)
    summaries = []
    for size in sizes:
        same = [row for row in runs if row["sample_size"] == size]
        for metric in ("heldout_B26_14_WAPE", "published_key_coverage",
                       "before_1980_WAPE", "before_1990_WAPE", "before_2000_WAPE"):
            values = [float(row[metric]) for row in same if row[metric] is not None]
            summaries.append({
                "sample_size": size, "metric": metric, "independent_seeds": len(values),
                "mean": mean(values) if values else None,
                "sd_across_seeds": pstdev(values) if len(values) >= 2 else None,
                "minimum": min(values) if values else None,
                "maximum": max(values) if values else None,
                "sd_is_Monte_Carlo_only_not_model_confidence_interval": True,
            })
    result = {
        "pipeline": VERSION,
        "status": "reproducible_seed_and_sample_size_sensitivity_not_model_validation",
        "reference_date": REFERENCE_DATE,
        "holdout_source": reference,
        "sample_sizes": list(sizes),
        "predeclared_seeds": list(seeds),
        "retained_synthetic_replicate_files": retain_samples,
        "runs": runs,
        "summaries": summaries,
        "original_m13b_sample_and_report_untouched": True,
        "holdout_used_for_parameter_tuning": False,
        "interpretation": (
            "Seed-to-seed spread measures finite weighted Monte Carlo variation at a "
            "given sample size, not source-disclosure or model misspecification error. "
            "Sampling convergence cannot establish individual-vehicle truth."
        ),
        "release_ready": False,
    }
    _atomic_json(root / SENSITIVITY_REPORT, result)
    return result
