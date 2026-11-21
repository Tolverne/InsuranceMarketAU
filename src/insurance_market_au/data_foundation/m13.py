"""M1.3a — auditable national synthetic joint for state/class/year/fuel.

Train on three *distinct, confidentialised* BITRE 2026 projections:
  B26-01: state × vehicle type × manufacture year
  B26-02: vehicle type × manufacture year × motive power
  B26-03: state × vehicle type × motive power
Use workbook Table 1 state × type as operational accounting anchors.
Hold out B26-10 (state × type × year × fuel), with NO effect on support,
prior, calibration, early stopping, hyperparameters, or sample generation.

Damped alternating raking is a documented approximate fitter, not a
statistical disclosure likelihood or a claim of exact observed microdata.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from insurance_market_au.data_foundation.m1 import ROOT, REFERENCE_DATE, load_bitre_catalog
from insurance_market_au.data_foundation.m11_controls import ALL_MOTOR_VEHICLES

TRAIN_IDS = ("B26-01", "B26-02", "B26-03")
HOLDOUT_ID = "B26-10"
FIELDS = ("registered_state", "vehicle_type", "manufacture_year", "motive_power")
FAMILY_FIELDS = {
    "state_type_year": (0, 1, 2),
    "type_year_fuel": (1, 2, 3),
    "state_type_fuel": (0, 1, 3),
}
SOURCES = {
    "B26-01": ("state_type_year", (0, 1, 2)),
    "B26-02": ("type_year_fuel", (1, 2, 3)),
    "B26-03": ("state_type_fuel", (0, 1, 3)),
    "B26-10": ("holdout_joint", (0, 1, 2, 3)),
}
TOTAL = 22_771_150


def read_controls(root: Path) -> tuple[dict[tuple[str, str], float], dict]:
    path = root / "data/processed/m1/controls/bitre-2026-table1-controls.json"
    if not path.is_file():
        raise FileNotFoundError("M1.1 controls missing; run py -3 scripts/m11_reconcile.py")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["national_total"] != TOTAL or data["reference_date"] != REFERENCE_DATE:
        raise ValueError("BITRE workbook controls mismatch expected January 2026 publication")
    cells = {}
    for row in data["controls"]:
        if row["state"] == "AUS" or row["vehicle_type"] == ALL_MOTOR_VEHICLES:
            continue
        key = (row["state"], row["vehicle_type"])
        if key in cells:
            raise ValueError(f"Duplicate workbook control {key}")
        cells[key] = float(row["vehicles"])
    if len(cells) != 80 or sum(cells.values()) != TOTAL:
        raise ValueError("Expected 80 additive workbook state × class controls summing to 22,771,150")
    return cells, data


def _stage_path(root: Path, source: dict) -> Path:
    return (root / "data/processed/m1/bitre" / REFERENCE_DATE /
            f"{source['projection_id'].lower()}--{source['sha256'][:12]}.parquet")


def read_projection(path: Path, source: dict, *, batch_rows: int = 65536) -> tuple[dict[tuple[str, ...], float], dict]:
    """Sum one publisher projection along its actual published dimensions.

    Source rows are never joined to any other source rows. Input lineage,
    pinned row count, released detail total and date are all verified.
    """
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError('Install data extras: py -3 -m pip install -e ".[data,model]"') from exc
    if batch_rows <= 0:
        raise ValueError("batch_rows must be positive")
    if not path.is_file():
        raise FileNotFoundError(f"Missing M1.0 staging file {path}; run py -3 scripts/m1_ingest.py --parquet")
    projection_id = source["projection_id"]
    name, dimensions = SOURCES[projection_id]
    names = [FIELDS[i] for i in dimensions]
    parquet = pq.ParquetFile(path)
    if parquet.metadata.num_rows != source["expected_rows"]:
        raise ValueError(f"{projection_id}: physical source row count has drifted")
    required = {
        "source_release_id", "projection_id", "observation_date", "source_row",
        "count_status", "vehicle_count", "is_published_total", *names,
    }
    if not required <= set(parquet.schema_arrow.names):
        raise ValueError(f"{projection_id}: missing required staging fields {sorted(required - set(parquet.schema_arrow.names))}")
    group: dict[tuple[str, ...], float] = defaultdict(float)
    raw_rows = 0
    total_rows = 0
    detail_numeric_sum = 0.0
    unknown_cells = 0
    lineage = f"bitre-2026:{source['resource_id']}:{source['sha256'][:12]}"
    for batch in parquet.iter_batches(batch_size=batch_rows, columns=sorted(required)):
        cols = {n: batch.column(batch.schema.get_field_index(n)).to_pylist() for n in required}
        for i in range(batch.num_rows):
            raw_rows += 1
            if (cols["projection_id"][i] != projection_id or
                    cols["source_release_id"][i] != lineage or
                    cols["observation_date"][i] != REFERENCE_DATE or
                    cols["source_row"][i] != raw_rows):
                raise ValueError(f"{projection_id}: source lineage, date or row position mismatch at {raw_rows}")
            if cols["is_published_total"][i]:
                total_rows += 1
                continue
            value = cols["vehicle_count"][i]
            if value is None:
                unknown_cells += 1
                continue
            if (not isinstance(value, int) or value < 0 or
                    cols["count_status"][i] != "published_confidentialised_numeric"):
                raise ValueError(f"{projection_id}: nonnumeric or inconsistent source cell at {raw_rows}")
            key = tuple(cols[n][i] for n in names)
            if any(x is None for x in key):
                raise ValueError(f"{projection_id}: null dimension at {raw_rows}")
            group[key] += value
            detail_numeric_sum += value
    if (raw_rows != source["expected_rows"] or
            total_rows != source["expected_published_total_rows"] or
            detail_numeric_sum != source["expected_detail_numeric_total"]):
        raise ValueError(f"{projection_id}: pinned source totals failed")
    if unknown_cells:
        raise ValueError(f"{projection_id}: {unknown_cells} unknown counts; explicit censoring model required")
    return dict(group), {
        "projection_id": projection_id, "name": name, "source_sha256": source["sha256"],
        "raw_rows": raw_rows, "published_total_rows_excluded": total_rows,
        "detail_published_numeric_sum": int(detail_numeric_sum),
        "group_count": len(group), "unresolved_count_cells": unknown_cells,
    }


@dataclass
class Joint:
    states: np.ndarray
    types: np.ndarray
    years: np.ndarray
    fuels: np.ndarray
    weights: np.ndarray
    state_type_ids: np.ndarray
    state_type_labels: list[tuple[str, str]]
    hard_totals: np.ndarray

    def tuples(self) -> list[tuple[str, str, str, str]]:
        return list(zip(self.states.tolist(), self.types.tolist(),
                        self.years.tolist(), self.fuels.tolist()))


def build_support(
    controls: dict[tuple[str, str], float], projections: dict[str, dict],
    *, max_support: int = 500000,
) -> Joint:
    """Form full year × fuel support per state/class, without held-out B26-10.

    Positive pseudocounts prevent published numeric zeros and absent *joints*
    from being interpreted as proven structural impossibilities.
    """
    by_st_year = projections["B26-01"]
    by_st_fuel = projections["B26-03"]
    by_type_year_fuel = projections["B26-02"]
    type_year = defaultdict(float)
    type_fuel = defaultdict(float)
    type_year_values: dict[str, set[str]] = defaultdict(set)
    type_fuel_values: dict[str, set[str]] = defaultdict(set)
    st_year: dict[tuple[str, str], set[str]] = defaultdict(set)
    st_fuel: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (state, klass, year), v in by_st_year.items():
        if (state, klass) not in controls:
            raise ValueError(f"Unrecognised state/class in B26-01: {(state, klass)}")
        st_year[(state, klass)].add(year)
        type_year_values[klass].add(year)
    for (state, klass, fuel), v in by_st_fuel.items():
        if (state, klass) not in controls:
            raise ValueError(f"Unrecognised state/class in B26-03: {(state, klass)}")
        st_fuel[(state, klass)].add(fuel)
        type_fuel_values[klass].add(fuel)
    for (klass, year, fuel), v in by_type_year_fuel.items():
        type_year[klass, year] += v
        type_fuel[klass, fuel] += v
        type_year_values[klass].add(year)
        type_fuel_values[klass].add(fuel)
    state_type_labels = sorted(controls)
    rows = []
    priors = []
    ids = []
    for idx, (state, klass) in enumerate(state_type_labels):
        amount = controls[(state, klass)]
        if amount == 0:
            continue
        years = sorted(type_year_values[klass] | st_year[(state, klass)])
        fuels = sorted(type_fuel_values[klass] | st_fuel[(state, klass)])
        if not years or not fuels:
            raise ValueError(f"Missing year/fuel support for positive state/class {(state, klass)}")
        # State-class marginals dominate the prior; national type distributions
        # provide nonzero backoff for missing or suppressed entries.
        year_w = np.array([
            max(0.0, by_st_year.get((state, klass, y), 0.0)) +
            0.001 * max(0.0, type_year[(klass, y)]) + 0.5 for y in years
        ], dtype=np.float64)
        fuel_w = np.array([
            max(0.0, by_st_fuel.get((state, klass, f), 0.0)) +
            0.001 * max(0.0, type_fuel[(klass, f)]) + 0.5 for f in fuels
        ], dtype=np.float64)
        year_w /= year_w.sum()
        fuel_w /= fuel_w.sum()
        for yi, year in enumerate(years):
            for fi, fuel in enumerate(fuels):
                rows.append((state, klass, year, fuel))
                priors.append(float(amount * year_w[yi] * fuel_w[fi]))
                ids.append(idx)
        if len(rows) > max_support:
            raise ValueError(f"Sparse support exceeds --max-support={max_support}")
    if not rows:
        raise ValueError("No positive published state/class control cells")
    columns = list(zip(*rows))
    return Joint(
        *[np.array(c, dtype=object) for c in columns],
        np.array(priors, dtype=np.float64),
        np.array(ids, dtype=np.int32),
        state_type_labels,
        np.array([controls[k] for k in state_type_labels], dtype=np.float64),
    )


@dataclass
class Constraint:
    name: str
    labels: list[tuple[str, ...]]
    targets: np.ndarray
    cell_ids: np.ndarray
    missing_target_mass: float
    missing_target_groups: int


def constraints_for_joint(joint: Joint, projections: dict[str, dict]) -> list[Constraint]:
    rows = joint.tuples()
    output = []
    for pid in TRAIN_IDS:
        name, dims = SOURCES[pid]
        target = projections[pid]
        target_keys = sorted(target)
        target_idx = {k: i for i, k in enumerate(target_keys)}
        indices = np.array([target_idx.get(tuple(row[i] for i in dims), -1) for row in rows],
                           dtype=np.int32)
        supported = set(tuple(row[i] for i in dims) for row in rows)
        unsupported = [k for k in target_keys if k not in supported]
        output.append(Constraint(
            name=f"{pid}:{name}", labels=target_keys,
            targets=np.array([target[k] for k in target_keys], dtype=np.float64),
            cell_ids=indices,
            missing_target_mass=sum(target[k] for k in unsupported),
            missing_target_groups=len(unsupported),
        ))
    return output


def enforce_hard_totals(joint: Joint) -> None:
    current = np.bincount(joint.state_type_ids, weights=joint.weights,
                          minlength=len(joint.hard_totals))
    valid = joint.hard_totals > 0
    if np.any(valid & (current <= 0)):
        raise ValueError("Impossible positive workbook control with empty support")
    factors = np.ones(len(current), dtype=np.float64)
    factors[valid] = joint.hard_totals[valid] / current[valid]
    joint.weights *= factors[joint.state_type_ids]


def _forecast(joint: Joint, spec: Constraint) -> np.ndarray:
    valid = spec.cell_ids >= 0
    return np.bincount(spec.cell_ids[valid],
                       weights=joint.weights[valid], minlength=len(spec.targets))


def margin_metrics(joint: Joint, constraints: list[Constraint]) -> list[dict]:
    metrics = []
    for c in constraints:
        predicted = _forecast(joint, c)
        difference = predicted - c.targets
        metrics.append({
            "constraint": c.name, "groups": len(c.labels),
            "unsupported_source_groups": c.missing_target_groups,
            "unsupported_source_mass": c.missing_target_mass,
            "sum_absolute_error": float(np.abs(difference).sum()),
            "published_count_wape": float(np.abs(difference).sum() / max(c.targets.sum(), 1)),
            "maximum_absolute_residual": float(np.abs(difference).max(initial=0)),
            "published_zeros_not_structural": True,
            "hard_equality_asserted": False,
        })
    return metrics


def fit(
    joint: Joint, constraints: list[Constraint],
    *, iterations: int = 32, relaxation: float = 0.35, pseudocount: float = 2.0,
) -> dict:
    """Damped proportional fitting, with hard state/class normalisation.

    No direct confidentialised cell is imposed as a hard calibration equality.
    B26-10 is excluded entirely. Fixed iteration count avoids tuning on holdout.
    """
    if iterations < 0 or not 0 < relaxation <= 1 or pseudocount <= 0:
        raise ValueError("Invalid fit hyperparameters")
    before = margin_metrics(joint, constraints)
    for iteration in range(iterations):
        for spec in constraints:
            present = spec.cell_ids >= 0
            totals = _forecast(joint, spec)
            update = np.power(
                np.clip((spec.targets + pseudocount) / (totals + pseudocount),
                        0.25, 4.0), relaxation,
            )
            joint.weights[present] *= update[spec.cell_ids[present]]
            enforce_hard_totals(joint)
    enforce_hard_totals(joint)
    if not np.all(np.isfinite(joint.weights)) or np.any(joint.weights < 0):
        raise ValueError("Numerical failure in calibrated synthetic distribution")
    actual = np.bincount(joint.state_type_ids, weights=joint.weights,
                         minlength=len(joint.hard_totals))
    if np.max(np.abs(actual - joint.hard_totals)) > 1e-5:
        raise ValueError("Operational published state/class accounting controls not satisfied")
    return {
        "method": "damped_alternating_proportional_fitting_with_hard_state_type_normalisation",
        "iterations": iterations, "relaxation": relaxation, "pseudocount": pseudocount,
        "initial_training_margins": before,
        "fitted_training_margins": margin_metrics(joint, constraints),
        "maximum_operational_control_error": float(np.max(np.abs(actual - joint.hard_totals))),
        "formal_disclosure_likelihood_estimated": False,
        "converges_to_unique_global_optimum_claimed": False,
    }


def evaluate_holdout(joint: Joint, holdout: dict[tuple[str, str, str, str], float]) -> dict:
    """Report B26-10 validation on precisely published joint cells.

    This is a held-out *published projection*, not independent vehicle truth.
    Missing support and disclosure-affected zero values are separately flagged.
    """
    pred = {key: float(weight) for key, weight in zip(joint.tuples(), joint.weights)}
    errors = []
    substantial = []
    missing_groups = 0
    missing_mass = 0.0
    for key, published in holdout.items():
        estimated = pred.get(key, 0.0)
        if key not in pred:
            missing_groups += 1
            missing_mass += published
        delta = abs(estimated - published)
        errors.append(delta)
        if published >= 100:
            substantial.append((delta, published))
    values = np.array(errors, dtype=np.float64)
    all_published = sum(holdout.values())
    nonzero_holdout = sum(val != 0 for val in holdout.values())
    return {
        "held_out_source": "B26-10",
        "trained_on_holdout": False,
        "shared_joint_dimensions": list(FIELDS),
        "published_aggregate_cells": len(holdout),
        "positive_published_cells": nonzero_holdout,
        "unsupported_published_groups": missing_groups,
        "unsupported_published_mass": missing_mass,
        "overall_published_cell_wape": float(values.sum() / max(1.0, all_published)),
        "heldout_cells_published_ge_100": len(substantial),
        "wape_for_published_ge_100": (
            float(sum(d for d, _ in substantial) / sum(v for _, v in substantial))
            if substantial else None
        ),
        "median_absolute_count_error": float(np.median(values)) if len(values) else None,
        "p95_absolute_count_error": float(np.percentile(values, 95)) if len(values) else None,
        "maximum_absolute_count_error": float(values.max(initial=0)),
        "validation_is_independent_physical_truth": False,
        "unknown_disclosure_bias": True,
    }



def holdout_subgroup_metrics(
    joint: Joint, holdout: dict[tuple[str, str, str, str], float]
) -> dict:
    """Evaluate rare/older segments separately, without fitting on any holdout.

    Manufacture year must be a plain four-digit year to enter age cohorts.
    Unparseable publication year labels are counted and left unclassified.
    """
    pred = {row: float(mass) for row, mass in zip(joint.tuples(), joint.weights)}
    out: dict[str, dict] = {}
    cohorts = {
        "manufactured_before_1980": lambda y: y < 1980,
        "manufactured_before_1990": lambda y: y < 1990,
        "manufactured_before_2000": lambda y: y < 2000,
    }
    def summarize(rows):
        pairs = [(float(v), pred.get(k, 0.0)) for k, v in rows]
        published = sum(v for v, _ in pairs)
        return {
            "published_holdout_cells": len(pairs),
            "published_reference_sum": published,
            "model_expected_sum_on_published_cells": sum(p for _, p in pairs),
            "published_cell_WAPE": (
                sum(abs(p - v) for v, p in pairs) / published if published else None
            ),
            "published_cells_ge_100": sum(v >= 100 for v, _ in pairs),
            "not_independent_vehicle_level_truth": True,
        }
    dated = {}
    unparsed = 0
    for key, v in holdout.items():
        year = key[2]
        if isinstance(year, str) and len(year) == 4 and year.isdecimal():
            dated[key] = (int(year), v)
        else:
            unparsed += 1
    for name, rule in cohorts.items():
        out[name] = summarize([(key, val) for key, (year, val) in dated.items()
                               if rule(year)])
    by_class = {}
    for klass in sorted({k[1] for k in holdout}):
        by_class[klass] = summarize([(key, val) for key, val in holdout.items()
                                    if key[1] == klass])
    return {
        "age_cohorts": out,
        "vehicle_types": by_class,
        "unclassified_manufacture_year_cells": unparsed,
        "year_interpretation": "Plain four-digit year labels only; excludes suppressed/missing/unparseable years",
    }


def _safe_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".partial")
    try:
        part.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)


def write_joint(joint: Joint, path: Path) -> None:
    """One locally stored *expected aggregate cell* per support combination."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError('Install data extras: py -3 -m pip install -e ".[data,model]"') from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".partial")
    schema = pa.schema([
        ("registered_state", pa.string()), ("vehicle_type", pa.string()),
        ("manufacture_year", pa.string()), ("motive_power", pa.string()),
        ("expected_synthetic_vehicles", pa.float64()),
        ("reference_date", pa.string()), ("model_status", pa.string()),
    ])
    try:
        table = pa.Table.from_pydict({
            "registered_state": joint.states.tolist(),
            "vehicle_type": joint.types.tolist(),
            "manufacture_year": joint.years.tolist(),
            "motive_power": joint.fuels.tolist(),
            "expected_synthetic_vehicles": joint.weights.tolist(),
            "reference_date": [REFERENCE_DATE] * len(joint.weights),
            "model_status": ["synthetic_joint_estimate_not_actual_vehicle_records"] * len(joint.weights),
        }, schema=schema)
        pq.write_table(table, part, compression="zstd")
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)


def write_sample(joint: Joint, path: Path, *, n: int, seed: int) -> None:
    """Generate a reproducible *clearly-labelled* local synthetic sample.

    Sampled rows contain only four non-identifying aggregate descriptors;
    they have no identity/VIN/postcode/address/model and are not real records.
    """
    if not 1 <= n <= 200000:
        raise ValueError("M1.3a sample size must be 1–200,000 (not a full fleet release)")
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError('Install data extras: py -3 -m pip install -e ".[data,model]"') from exc
    probabilities = joint.weights / joint.weights.sum()
    positions = np.random.default_rng(seed).choice(len(probabilities), size=n, p=probabilities)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".partial")
    try:
        sample = pa.table({
            "synthetic_record_id": [f"SYN-{seed:08d}-{i:07d}" for i in range(n)],
            "registered_state": joint.states[positions].tolist(),
            "vehicle_type": joint.types[positions].tolist(),
            "manufacture_year": joint.years[positions].tolist(),
            "motive_power": joint.fuels[positions].tolist(),
            "is_synthetic": [True] * n,
        })
        pq.write_table(sample, part, compression="zstd")
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)


def run_m13(
    *, root: Path = ROOT, iterations: int = 32,
    relaxation: float = 0.35, pseudocount: float = 2.0,
    seed: int = 20261121, sample_size: int = 0,
    max_support: int = 500000,
) -> dict:
    controls, workbook = read_controls(root)
    catalogue = {s["projection_id"]: s for s in load_bitre_catalog(root)}
    source_data = {}
    lineage = []
    for pid in (*TRAIN_IDS, HOLDOUT_ID):
        print(f"[M1.3] Reading verified {'HELD-OUT' if pid == HOLDOUT_ID else 'training'} source {pid}", flush=True)
        source_data[pid], info = read_projection(_stage_path(root, catalogue[pid]), catalogue[pid])
        lineage.append(info)
    model_inputs = {pid: source_data[pid] for pid in TRAIN_IDS}
    joint = build_support(controls, model_inputs, max_support=max_support)
    constraints = constraints_for_joint(joint, model_inputs)
    enforce_hard_totals(joint)
    baseline = evaluate_holdout(joint, source_data[HOLDOUT_ID])
    fit_report = fit(joint, constraints, iterations=iterations,
                     relaxation=relaxation, pseudocount=pseudocount)
    heldout = evaluate_holdout(joint, source_data[HOLDOUT_ID])
    classic_diagnostics = holdout_subgroup_metrics(joint, source_data[HOLDOUT_ID])
    outputs = root / "data/processed/m13"
    distribution_path = outputs / "joint-state-type-year-fuel.parquet"
    write_joint(joint, distribution_path)
    sample_path = None
    if sample_size:
        sample_path = outputs / f"synthetic-pilot-n{sample_size}-seed{seed}.parquet"
        write_sample(joint, sample_path, n=sample_size, seed=seed)
    report = {
        "pipeline": "m1.3a-national-synthetic-four-way-pilot",
        "status": "initial_calibrated_joint_pilot_not_national_vehicle_release",
        "reference_date": REFERENCE_DATE,
        "published_total_operational_anchor": TOTAL,
        "state_type_workbook_controls": len(controls),
        "model_dimensions": list(FIELDS),
        "joint_support_cells": len(joint.weights),
        "sum_expected_synthetic_vehicles": float(joint.weights.sum()),
        "source_lineage": lineage,
        "training_sources": list(TRAIN_IDS),
        "holdout_source": HOLDOUT_ID,
        "holdout_excluded_from_training_support_fitting_and_tuning": True,
        "initial_holdout": baseline,
        "fitted_holdout": heldout,
        "heldout_segment_diagnostics": classic_diagnostics,
        "fit": fit_report,
        "expected_joint_parquet": str(distribution_path),
        "synthetic_sample_parquet": str(sample_path) if sample_path else None,
        "synthetic_sample_size": sample_size,
        "random_seed": seed,
        "non_modelled_dimensions": [
            "make", "model", "registration_postcode", "garaging_postcode",
            "vehicle_age_adjustments", "insurance_coverage",
        ],
        "state_supplementary_evidence": {
            "used_in_fitting": False,
            "reason": "State evidence has distinct vintages and coverage; ACT row date unknown, QLD 2022 grain/privacy and NSW source confidentiality need review",
        },
        "caution": "Counts are fitted expectations from confidentialised independent aggregates; not an observed joint or real/policy-level fleet.",
        "population_release_created": False,
    }
    report_path = root / "data/reports/m13/pilot-validation.json"
    _safe_json(report_path, report)
    print(f"[M1.3] joint cells={len(joint.weights):,}, sum={joint.weights.sum():,.2f}, "
          f"heldout WAPE={heldout['overall_published_cell_wape']:.4%}", flush=True)
    return report
