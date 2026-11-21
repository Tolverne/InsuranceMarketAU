"""M1.1 disclosure-aware reconciliation of independently published BITRE projections.

Only comparable shared marginal *aggregates* are compared. The 17 source
tables are never joined row-to-row. Missing/suppressed groups are not zeros.
Registered and garaging postcodes remain separate geographic roles.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import csv
import json
import math
import os
from pathlib import Path
from typing import Any

from insurance_market_au.data_foundation.m1 import (
    ROOT, REFERENCE_DATE, load_bitre_catalog, mapped_columns,
)
from insurance_market_au.data_foundation.m11_controls import (
    ALL_MOTOR_VEHICLES, extract_workbook_controls, find_workbook,
    write_controls,
)


@dataclass(frozen=True)
class Margin:
    name: str
    fields: tuple[str, ...]
    anchor_id: str
    geography_role: str | None = None


# Compact, identifiable overlapping margins. Do not compare registration
# postcode with garaging postcode, or assume any nonexistent full joint.
MARGINS = (
    Margin("state_vehicle_type", ("registered_state", "vehicle_type"), "workbook_table1"),
    Margin("type_motive_power", ("vehicle_type", "motive_power"), "B26-02"),
    Margin("type_manufacture_year", ("vehicle_type", "manufacture_year"), "B26-01"),
    Margin("state_type_motive_power",
           ("registered_state", "vehicle_type", "motive_power"), "B26-03"),
    Margin("state_type_manufacture_year",
           ("registered_state", "vehicle_type", "manufacture_year"), "B26-01"),
    Margin("type_registered_postcode",
           ("vehicle_type", "registered_postcode"), "B26-04", "registration"),
    Margin("type_garaging_postcode",
           ("vehicle_type", "garaging_postcode"), "B26-09", "garaging_with_fallback"),
    Margin("type_make_model", ("vehicle_type", "make", "model"), "B26-05"),
)


def workbook_state_type_anchor(controls: dict) -> dict[tuple[str, ...], list[int]]:
    anchor = {}
    for cell in controls["controls"]:
        if cell["state"] == "AUS" or cell["vehicle_type"] == ALL_MOTOR_VEHICLES:
            continue
        key = (cell["state"], cell["vehicle_type"])
        if key in anchor:
            raise ValueError(f"Repeated workbook state/vehicle-type cell {key}")
        anchor[key] = [cell["vehicles"], 0, int(cell["vehicles"] == 0)]
    if len(anchor) != 80:
        raise ValueError("Expected 8 states × 10 classes in Table 1 workbook controls")
    return anchor


def available_margins(headers: list[str]) -> tuple[Margin, ...]:
    mapped, _ = mapped_columns(headers)
    return tuple(margin for margin in MARGINS if set(margin.fields) <= set(mapped))


def _stage_path(root: Path, source: dict) -> Path:
    return (root / "data/processed/m1/bitre" / REFERENCE_DATE /
            f"{source['projection_id'].lower()}--{source['sha256'][:12]}.parquet")


def aggregate_source_marginals(
    path: Path, source: dict, *, batch_size: int = 32768,
) -> tuple[dict[str, dict[tuple[str, ...], list[int]]], dict]:
    """Produce sparse common marginals in one bounded-memory Parquet pass.

    Each value is [sum_of_numeric_published_counts, unknown_cell_count,
                   published_zero_count]. No counts are imputed.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError('Install Parquet support: py -3 -m pip install -e ".[data]"') from exc
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing staged {source['projection_id']} Parquet: {path}. "
            "Run: py -3 scripts/m1_ingest.py --parquet"
        )
    parquet = pq.ParquetFile(path)
    if parquet.metadata.num_rows != source["expected_rows"]:
        raise ValueError(f"{source['projection_id']} staging row-count differs from verified physical contract")
    required = {"vehicle_count", "is_published_total", "projection_id",
                "source_release_id", "count_status", "observation_date", "source_row"}
    active = available_margins(source["expected_headers"])
    fields = set(required)
    for margin in active:
        fields.update(margin.fields)
    missing = fields - set(parquet.schema_arrow.names)
    if missing:
        raise ValueError(f"Missing Parquet fields {sorted(missing)} in {path.name}")
    # A dict per *margin*, not per input row: avoids materialising the huge
    # postcode × make/model × year × fuel joint.
    aggregates: dict[str, dict[tuple[str, ...], list[int]]] = {
        m.name: defaultdict(lambda: [0, 0, 0]) for m in active
    }
    lineage = f"bitre-2026:{source['resource_id']}:{source['sha256'][:12]}"
    total_rows = 0
    excluded_total_rows = 0
    detail_numeric_total = 0
    detail_non_numeric = 0
    detail_numeric_zero_rows = 0
    for batch in parquet.iter_batches(batch_size=batch_size, columns=sorted(fields)):
        columns = {
            name: batch.column(batch.schema.get_field_index(name)).to_pylist()
            for name in fields
        }
        for i in range(batch.num_rows):
            total_rows += 1
            if columns["observation_date"][i] != REFERENCE_DATE:
                raise ValueError(f"{path.name}: reference date drift at row {total_rows}")
            if columns["source_row"][i] != total_rows:
                raise ValueError(f"{path.name}: staging source row order/sequence drift at row {total_rows}")
            if columns["projection_id"][i] != source["projection_id"]:
                raise ValueError(f"{path.name}: projection_id drift at row {total_rows}")
            if columns["source_release_id"][i] != lineage:
                raise ValueError(f"{path.name}: source release lineage drift at row {total_rows}")
            if columns["is_published_total"][i]:
                excluded_total_rows += 1
                continue
            count = columns["vehicle_count"][i]
            status = columns["count_status"][i]
            if (count is None) == (status == "published_confidentialised_numeric"):
                raise ValueError(f"{path.name}: inconsistent count/status at row {total_rows}")
            if count is None:
                detail_non_numeric += 1
            elif not isinstance(count, int) or count < 0:
                raise ValueError(f"{path.name}: invalid count at row {total_rows}")
            else:
                detail_numeric_total += count
                if count == 0:
                    detail_numeric_zero_rows += 1
            for margin in active:
                key = tuple(
                    "<NULL>" if columns[column][i] is None else str(columns[column][i])
                    for column in margin.fields
                )
                cell = aggregates[margin.name][key]
                if count is None:
                    cell[1] += 1
                else:
                    cell[0] += count
                    if count == 0:
                        cell[2] += 1
    if total_rows != source["expected_rows"]:
        raise ValueError(f"{source['projection_id']}: Parquet row count changed mid-read")
    if excluded_total_rows != source["expected_published_total_rows"]:
        raise ValueError(f"{source['projection_id']}: unexpected published totals in staging")
    if detail_numeric_total != source["expected_detail_numeric_total"]:
        raise ValueError(f"{source['projection_id']}: detailed numeric sum differs from source contract")
    return aggregates, {
        "projection_id": source["projection_id"],
        "source_sha256": source["sha256"],
        "staging_file": str(path),
        "source_rows": total_rows,
        "published_total_rows_excluded": excluded_total_rows,
        "published_detail_numeric_total": detail_numeric_total,
        "published_zero_rows": detail_numeric_zero_rows,
        "nonnumeric_cells": detail_non_numeric,
        "margins_available": [m.name for m in active],
        "distinct_groups": {name: len(groups) for name, groups in aggregates.items()},
        "suppression_note": (
            "Published numeric 0 may be modified or suppressed by disclosure control; "
            "it does not establish a structural zero."
        ),
    }


def _percentile(values: list[int], proportion: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(proportion * len(ordered)) - 1))]


def compare_groups(
    margin: Margin,
    anchor: dict[tuple[str, ...], list[int]],
    candidate: dict[tuple[str, ...], list[int]],
    *, reference: str, candidate_id: str, detailed_writer: csv.DictWriter | None = None,
    top_n: int = 12,
) -> dict[str, Any]:
    """Numerical discrepancies on common supported keys only.

    In particular, absent groups and groups with unobserved cells are
    *excluded* from the paired difference metrics and reported separately.
    No confidentiality tolerance is invented.
    """
    left_only = set(anchor) - set(candidate)
    right_only = set(candidate) - set(anchor)
    common = set(anchor) & set(candidate)
    compared = 0
    missing_values = 0
    nonzero = 0
    signed_sum = 0
    abs_sum = 0
    deltas: list[int] = []
    top: list[dict] = []
    max_rel_percent: float | None = None
    for key in sorted(common):
        a = anchor[key]
        b = candidate[key]
        if a[1] or b[1]:
            missing_values += 1
            continue
        delta = b[0] - a[0]
        compared += 1
        signed_sum += delta
        absolute = abs(delta)
        abs_sum += absolute
        deltas.append(absolute)
        if delta != 0:
            nonzero += 1
        relative = absolute / max(1, abs(a[0])) * 100
        max_rel_percent = max(relative, max_rel_percent or 0)
        item = {
            "key": dict(zip(margin.fields, key)),
            "reference_count": a[0],
            "candidate_count": b[0],
            "delta_candidate_minus_reference": delta,
            "absolute_delta": absolute,
            "relative_abs_percent": round(relative, 6),
        }
        if detailed_writer is not None:
            detailed_writer.writerow({
                "margin": margin.name,
                "reference": reference,
                "candidate": candidate_id,
                "dimensions_json": json.dumps(item["key"], ensure_ascii=False, sort_keys=True),
                "reference_count": a[0],
                "candidate_count": b[0],
                "signed_delta": delta,
                "absolute_delta": absolute,
                "status": "comparable_published_counts_not_true_counts",
            })
        top.append(item)
        if len(top) > top_n * 3:
            top.sort(key=lambda x: (-x["absolute_delta"], json.dumps(x["key"], sort_keys=True)))
            top = top[:top_n]
    top.sort(key=lambda x: (-x["absolute_delta"], json.dumps(x["key"], sort_keys=True)))
    return {
        "margin": margin.name,
        "dimensions": margin.fields,
        "geography_role": margin.geography_role,
        "anchor": reference,
        "candidate": candidate_id,
        "anchor_groups": len(anchor),
        "candidate_groups": len(candidate),
        "matched_comparable_groups": compared,
        "matched_groups_with_missing_values": missing_values,
        "anchor_only_groups_not_assumed_zero": len(left_only),
        "candidate_only_groups_not_assumed_zero": len(right_only),
        "nonzero_differences": nonzero,
        "signed_sum_candidate_minus_anchor": signed_sum,
        "sum_absolute_difference": abs_sum,
        "median_abs_difference": _percentile(deltas, 0.5),
        "p95_abs_difference": _percentile(deltas, 0.95),
        "maximum_abs_difference": max(deltas) if deltas else None,
        "maximum_relative_difference_percent": (
            round(max_rel_percent, 6) if max_rel_percent is not None else None
        ),
        "largest_discrepancies": top[:top_n],
        "constraint_policy": (
            "diagnostic_publisher_anchored" if reference == "workbook_table1"
            else "soft_projection_comparison"
        ),
        "tolerance": "not_invented_confidentialisation_parameters_unknown",
        "missing_group_semantics": "unobserved_not_zero",
        "point_estimate_warning": "published_detail_counts_may_be_perturbed_or_suppressed",
    }


CSV_COLUMNS = [
    "margin", "reference", "candidate", "dimensions_json", "reference_count",
    "candidate_count", "signed_delta", "absolute_delta", "status",
]


def reconcile_marginals(
    controls: dict, resources: list[dict], *, root: Path = ROOT,
    detail_csv: Path | None = None, batch_size: int = 32768,
) -> dict:
    """Reconcile overlapping source projections, without fitting a population."""
    observed: dict[str, dict[str, dict[tuple[str, ...], list[int]]]] = {}
    summaries = []
    for index, source in enumerate(resources, 1):
        print(f"[M1.1 {index}/{len(resources)}] {source['projection_id']}: "
              "streaming common margins", flush=True)
        current, info = aggregate_source_marginals(
            _stage_path(root, source), source, batch_size=batch_size
        )
        observed[source["projection_id"]] = current
        summaries.append(info)
        print(f"  margins={info['margins_available']}, "
              f"groups={info['distinct_groups']}", flush=True)

    anchors = {"state_vehicle_type": workbook_state_type_anchor(controls)}
    for margin in MARGINS:
        if margin.anchor_id == "workbook_table1":
            continue
        if margin.anchor_id in observed and margin.name in observed[margin.anchor_id]:
            anchors[margin.name] = observed[margin.anchor_id][margin.name]

    pairwise = []
    tmp_csv = None
    stream = None
    writer = None
    try:
        if detail_csv is not None:
            detail_csv.parent.mkdir(parents=True, exist_ok=True)
            tmp_csv = detail_csv.with_name(detail_csv.name + ".partial")
            stream = tmp_csv.open("w", encoding="utf-8", newline="")
            writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
            writer.writeheader()
        for margin in MARGINS:
            if margin.name not in anchors:
                continue
            for source in resources:
                pid = source["projection_id"]
                if pid == margin.anchor_id:
                    continue
                candidate = observed[pid].get(margin.name)
                if candidate is None:
                    continue
                pairwise.append(compare_groups(
                    margin, anchors[margin.name], candidate,
                    reference=margin.anchor_id, candidate_id=pid,
                    detailed_writer=writer,
                ))
        if stream is not None:
            stream.close()
            stream = None
            os.replace(tmp_csv, detail_csv)
    finally:
        if stream is not None:
            stream.close()
        if tmp_csv is not None:
            tmp_csv.unlink(missing_ok=True)

    return {
        "pipeline": "m1.1-bitre-disclosure-aware-marginal-reconciliation",
        "status": "precalibration_diagnostics_not_population_release",
        "reference_date": REFERENCE_DATE,
        "sources_analysed": len(resources),
        "complete_17": len(resources) == 17,
        "national_workbook_control": controls["national_total"],
        "workbook_sha256": controls["source_file_sha256"],
        "workbook_internal_consistency": controls["internal_consistency"],
        "source_summaries": summaries,
        "comparisons": pairwise,
        "comparison_count": len(pairwise),
        "comparison_nonzero_count": sum(p["nonzero_differences"] > 0 for p in pairwise),
        "population_release_created": False,
        "disclosure_policy": (
            "Publisher states <3 values and secondary cells may be suppressed/"
            "perturbed. Do not interpret observed 0 as structural 0. "
            "Do not treat a missing group as zero or impose exact equalities "
            "on disclosed cells without an approved error model."
        ),
        "constraint_classification": {
            "national_total": "BITRE_published_high_priority_accounting_anchor",
            "state_class": "BITRE_published_anchoring_benchmark_subject_to_publication_consistency",
            "detailed_margins": "candidate_soft_constraints_pending_disclosure_model",
            "unidentified_joints": "not_observed_no_synthetic_vehicle_release",
        },
        "local_detail_comparisons_csv": str(detail_csv) if detail_csv else None,
    }


def run_m11(
    *, root: Path = ROOT, selected: set[str] | None = None,
    batch_size: int = 32768, with_details: bool = True,
) -> tuple[dict, dict]:
    controls = extract_workbook_controls(find_workbook(root))
    resources = load_bitre_catalog(root)
    known = {x["projection_id"] for x in resources}
    if selected is not None:
        if not selected or not selected <= known:
            raise ValueError(f"Unknown/empty selection: {sorted(selected - known)}")
        resources = [r for r in resources if r["projection_id"] in selected]
    output_dir = root / "data/reports/m1"
    controls_dir = root / "data/processed/m1/controls"
    write_controls(controls, controls_dir)
    label = "full" if len(resources) == 17 else "pilot"
    detail_csv = output_dir / f"bitre-2026-m11-{label}-residuals.csv" if with_details else None
    report = reconcile_marginals(
        controls, resources, root=root, detail_csv=detail_csv, batch_size=batch_size
    )
    report["selected_projections"] = [r["projection_id"] for r in resources]
    report["control_json"] = str(controls_dir / "bitre-2026-table1-controls.json")
    report_path = output_dir / f"bitre-2026-m11-{label}-reconciliation.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp = report_path.with_name(report_path.name + ".partial")
    try:
        tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, report_path)
    finally:
        tmp.unlink(missing_ok=True)
    return controls, report
