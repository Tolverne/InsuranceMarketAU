"""M1.0 BITRE 2026 source profiles and separately-grained stock observations.

No synthetic vehicles are created here. All 17 BITRE extracts are distinct
confidentialised projections; never join their rows as vehicle microdata.
Source files and output parquet stay in git-ignored directories.
"""
from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
REFERENCE_DATE = "2026-01-31"
COUNT_HEADERS = ("no_vehicles", "vehicle_count")
# Exact, auditable physical-column aliases. Do not silently infer from a title.
ALIASES = {
    "vehicle_type": ("vehicle_type",),
    "registered_state": ("state_abb", "state", "registered_state"),
    "registered_postcode": ("registered_postcode", "postcode_registration", "postcode_of_registration"),
    "garaging_postcode": ("garaging_postcode", "postcode_garaging", "postcode_of_garaging"),
    "manufacture_year": ("year_of_manufacture", "manufacture_year"),
    "motive_power": ("motive_power", "fuel_type"),
    "make": ("make", "vehicle_make"),
    "model": ("model", "vehicle_model"),
}
CANONICAL_COLUMNS = [
    "vehicle_type", "registered_state", "registered_postcode", "garaging_postcode",
    "manufacture_year", "motive_power", "make", "model",
]
KNOWN_SUPPRESSION = {"..", ".", "*", "-", "np", "n.p.", "s", "suppressed", "confidential", "n/a", "na", ""}
CONTROL_PROJECTIONS = {"B26-01", "B26-03", "B26-10"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_bitre_catalog(root: Path = ROOT) -> list[dict[str, Any]]:
    acquired = json.loads((root / "catalog/acquisition/bitre-2026-acquired-metadata.json").read_text(encoding="utf-8"))
    projections = json.loads((root / "catalog/feasibility/bitre_2026_projections.json").read_text(encoding="utf-8"))
    observed = json.loads((root / "catalog/acquisition/bitre-2026-physical-schemas.json").read_text(encoding="utf-8"))
    physical = {entry["projection_id"]: entry for entry in observed["projection_schemas"]}
    items = {entry["projection_id"]: entry for entry in acquired["resources"]}
    definitions = {entry["projection_id"]: entry for entry in projections["observations"]}
    if len(items) != 18 or len(definitions) != 17 or len(physical) != 17:
        raise ValueError("BITRE inventory must contain 17 cross-tabs and explanatory notes")
    output = []
    for pid, definition in sorted(definitions.items()):
        item = items[pid]
        layout = physical[pid]
        if item["sha256"] != layout["sha256"] or item["resource_id"] != layout["resource_id"]:
            raise ValueError(f"Physical schema is tied to a different source release: {pid}")
        output.append({**item, "expected_dimensions": definition["dimensions"],
                       "postcode_role": definition["postcode_role"],
                       "expected_headers": layout["headers"],
                       "expected_rows": layout["rows"],
                       "expected_detail_numeric_total": layout["detail_numeric_total"],
                       "expected_published_total_rows": layout["published_total_rows"]})
    return output


def find_local_source(resource: dict, raw_root: Path, verify: bool = True) -> Path:
    folder = raw_root / "bitre" / REFERENCE_DATE
    candidates = list(folder.glob(f"*{resource['resource_id']}*--{resource['sha256'][:12]}.csv"))
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"{resource['projection_id']}: expected exactly one known source file in {folder}, "
            f"with UUID {resource['resource_id']} and SHA prefix {resource['sha256'][:12]}; "
            f"found {len(candidates)}. Rerun the BITRE acquisition script."
        )
    path = candidates[0]
    if verify and sha256_file(path).lower() != resource["sha256"].lower():
        raise ValueError(f"{resource['projection_id']}: source checksum mismatch — do not ingest")
    return path


def count_value(value: str | None) -> tuple[str, int | None]:
    raw = "" if value is None else value.strip()
    if raw.replace(",", "").isdigit():
        return "published_confidentialised_numeric", int(raw.replace(",", ""))
    if raw.startswith("-") and raw[1:].replace(",", "").isdigit():
        raise ValueError(f"negative registered vehicle count: {raw}")
    # We do not assume unknown textual sentinels mean zero. Flag for review.
    return ("suppressed_or_not_numeric" if raw.casefold() in KNOWN_SUPPRESSION
            else "unrecognized_count_token"), None


def _normalise_header(label: str) -> str:
    return "_".join(label.strip().casefold().replace("-", "_").split())


def mapped_columns(headers: list[str]) -> tuple[dict[str, str], list[str]]:
    original = {_normalise_header(h): h for h in headers}
    mapping = {}
    for canon, choices in ALIASES.items():
        for candidate in choices:
            if candidate in original:
                mapping[canon] = original[candidate]
                break
    return mapping, [name for name in headers if name not in mapping.values()
                     and _normalise_header(name) not in COUNT_HEADERS]


def is_published_total(dimensions: dict[str, str | None]) -> bool:
    """Identify displayed aggregates without confusing them with leaf observations.

    In the verified 2026 BITRE extracts vehicle_type 'Total' or '-' denotes
    the national grand-total row. Other fields sometimes say 'Total' too.
    A hyphen in another dimension *alone* is not treated as a total.
    """
    values = {_normalise_header(key): (value or "").strip().casefold()
              for key, value in dimensions.items()}
    return values.get("vehicle_type") in {"total", "-"} or any(
        value == "total" for value in values.values()
    )


def _schema():
    try:
        import pyarrow as pa
    except ImportError as exc:
        raise RuntimeError('Install Parquet support: py -3 -m pip install -e ".[data]"') from exc
    return pa.schema([
        pa.field("source_release_id", pa.string()),
        pa.field("projection_id", pa.string()),
        pa.field("observation_date", pa.string()),
        pa.field("source_row", pa.int64()),
        pa.field("vehicle_count", pa.int64()),
        pa.field("published_count_raw", pa.string()),
        pa.field("count_status", pa.string()),
        pa.field("is_published_total", pa.bool_()),
        *[pa.field(name, pa.string()) for name in CANONICAL_COLUMNS],
        pa.field("source_dimensions_json", pa.string()),
    ])


def profile_projection(path: Path, resource: dict[str, Any], *,
                       parquet_path: Path | None = None, batch_rows: int = 50000) -> dict[str, Any]:
    """Stream one raw *aggregate* CSV. A physical column is never inferred by position.

    When output requested, write bounded Parquet batches atomically. A partially
    completed parquet is never published.
    """
    if batch_rows < 1:
        raise ValueError("batch_rows must be positive")
    writer = None
    tmp_path = None
    if parquet_path is not None:
        import pyarrow.parquet as pq
        schema = _schema()
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = parquet_path.with_name(parquet_path.name + ".partial")
        tmp_path.unlink(missing_ok=True)
    stats: dict[str, Any] = {
        "projection_id": resource["projection_id"],
        "source_id": resource.get("resource_id"),
        "sha256": resource["sha256"],
        "reference_date": REFERENCE_DATE,
        "record_grain": "one published confidentialised aggregate stock cell",
        "geography_role": resource.get("postcode_role"),
        "rows": 0, "numeric_rows": 0, "numeric_total": 0,
        "detail_numeric_rows": 0, "detail_numeric_total": 0,
        "published_total_rows": 0, "published_total_numeric_total": 0,
        "zero_numeric_rows": 0, "suppressed_rows": 0, "unrecognized_count_rows": 0,
        "expected_dimensions": resource.get("expected_dimensions", []),
        "count_reconciliation_status": "diagnostic_only_not_hard_controls",
        "status": "profiled",
    }
    pairs: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # numeric total, unavailable cells
    buffer: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            headers = reader.fieldnames
            if not headers:
                raise ValueError(f"{path.name} has no column header")
            stats["headers"] = headers
            if resource.get("expected_headers") is not None and headers != resource["expected_headers"]:
                raise ValueError(f"{path.name}: physical header drift: {headers} != expected {resource['expected_headers']}")
            stats["physical_schema_contract_verified"] = resource.get("expected_headers") is not None
            cols = {_normalise_header(x): x for x in headers}
            count_col = next((cols[x] for x in COUNT_HEADERS if x in cols), None)
            if count_col is None:
                raise ValueError(f"Unknown count field in {path.name}: {headers}")
            mapping, other_cols = mapped_columns(headers)
            stats["mapped_columns"] = mapping
            stats["unmapped_columns"] = other_cols
            # An unfamiliar physical dimension is retained verbatim in the
            # JSON field, never silently labelled as a known canonical one.
            stats["mapping_review_needed"] = bool(other_cols)
            if "vehicle_type" not in mapping:
                raise ValueError(f"{path.name}: missing required vehicle_type field")
            if parquet_path is not None:
                writer = pq.ParquetWriter(str(tmp_path), schema=schema, compression="zstd")
            for ordinal, source_row in enumerate(reader, start=1):
                if None in source_row:
                    raise ValueError(f"{path.name}: row {ordinal} has more columns than header")
                count_status, count = count_value(source_row[count_col])
                dimensions = {col: source_row[col] for col in headers if col != count_col}
                published_total = is_published_total(dimensions)
                if published_total:
                    stats["published_total_rows"] += 1
                if count_status == "published_confidentialised_numeric":
                    stats["numeric_rows"] += 1
                    stats["numeric_total"] += count
                    if published_total:
                        stats["published_total_numeric_total"] += count
                    else:
                        stats["detail_numeric_rows"] += 1
                        stats["detail_numeric_total"] += count
                    if count == 0:
                        stats["zero_numeric_rows"] += 1
                elif count_status == "suppressed_or_not_numeric":
                    stats["suppressed_rows"] += 1
                else:
                    stats["unrecognized_count_rows"] += 1
                stats["rows"] += 1
                if resource["projection_id"] in CONTROL_PROJECTIONS and not published_total:
                    state_field = mapping.get("registered_state")
                    group = (source_row.get(state_field, "<NO_STATE>"), source_row[mapping["vehicle_type"]])
                    key = json.dumps(group)
                    if count is None:
                        pairs[key][1] += 1
                    else:
                        pairs[key][0] += count
                if parquet_path is not None:
                    canonical = {col: source_row.get(mapping[col]) if col in mapping else None
                                 for col in CANONICAL_COLUMNS}
                    buffer.append({
                        "source_release_id": f"bitre-2026:{resource['resource_id']}:{resource['sha256'][:12]}",
                        "projection_id": resource["projection_id"],
                        "observation_date": REFERENCE_DATE,
                        "source_row": ordinal,
                        "vehicle_count": count,
                        "published_count_raw": source_row.get(count_col),
                        "count_status": count_status,
                        "is_published_total": published_total,
                        **canonical,
                        "source_dimensions_json": json.dumps(dimensions, ensure_ascii=False, sort_keys=True),
                    })
                    if len(buffer) >= batch_rows:
                        writer.write_table(_rows_as_table(buffer, schema))
                        buffer.clear()
            if resource.get("expected_rows") is not None and stats["rows"] != resource["expected_rows"]:
                raise ValueError(f"{path.name}: observed rows {stats['rows']} differ from pinned release {resource['expected_rows']}")
            if (resource.get("expected_detail_numeric_total") is not None
                    and stats["detail_numeric_total"] != resource["expected_detail_numeric_total"]):
                raise ValueError(f"{path.name}: detail count mismatch against pinned release")
            if (resource.get("expected_published_total_rows") is not None
                    and stats["published_total_rows"] != resource["expected_published_total_rows"]):
                raise ValueError(f"{path.name}: published grand-total row count mismatch against pinned release")
            if parquet_path is not None:
                if buffer:
                    writer.write_table(_rows_as_table(buffer, schema))
                    buffer.clear()
                writer.close()
                writer = None
                os.replace(tmp_path, parquet_path)
        if pairs:
            stats["state_vehicle_type_controls"] = {
                key: {"sum_numeric": nums[0], "suppressed_cells": nums[1]}
                for key, nums in sorted(pairs.items())
            }
        if parquet_path is not None:
            stats["parquet_file"] = str(parquet_path)
        return stats
    finally:
        if writer is not None:
            writer.close()
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _rows_as_table(rows: list[dict], schema):
    import pyarrow as pa
    return pa.Table.from_pylist(rows, schema=schema)


def reconcile_profiles(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare same-date projected marginals; differences are diagnostic.

    BITRE suppresses cells <3 and perturbs/suppresses additional values.
    Never treat detailed extract sums as exact national controls.
    """
    checks = []
    byid = {p["projection_id"]: p for p in profiles if p.get("status") == "profiled"}
    for one, two in (("B26-01", "B26-03"), ("B26-01", "B26-10"), ("B26-03", "B26-10")):
        if one not in byid or two not in byid:
            continue
        a = byid[one].get("state_vehicle_type_controls", {})
        b = byid[two].get("state_vehicle_type_controls", {})
        for key in sorted(set(a) & set(b)):
            left, right = a[key], b[key]
            delta = right["sum_numeric"] - left["sum_numeric"]
            checks.append({
                "projections": [one, two],
                "key_state_vehicle_type_json": key,
                "left_numeric_total": left["sum_numeric"],
                "right_numeric_total": right["sum_numeric"],
                "delta": delta,
                "suppressed_cells": left["suppressed_cells"] + right["suppressed_cells"],
                "interpretable_as_exact_error": False,
            })
    return {
        "status": "diagnostic_not_calibrated",
        "why_not_exact": "BITRE disclosure: cells under three suppressed; secondary perturbation/suppression can distort sums.",
        "checks": checks,
        "abs_delta_total": sum(abs(x["delta"]) for x in checks),
        "checks_with_nonzero_delta": sum(bool(x["delta"]) for x in checks),
    }


def run_m1(root: Path = ROOT, *, raw_root: Path | None = None,
           parquet: bool = False, selected: set[str] | None = None,
           verify: bool = True, batch_rows: int = 50000) -> dict:
    resources = load_bitre_catalog(root)
    known = {r["projection_id"] for r in resources}
    if selected is not None and not selected <= known:
        raise ValueError(f"Unknown BITRE projections: {sorted(selected - known)}")
    chosen = [r for r in resources if selected is None or r["projection_id"] in selected]
    raw = raw_root or (root / "data/raw")
    profiles = []
    processed = root / "data/processed/m1/bitre/2026-01-31"
    for i, resource in enumerate(chosen, start=1):
        print(f"[M1 {i}/{len(chosen)}] Verifying and profiling {resource['projection_id']}", flush=True)
        path = find_local_source(resource, raw, verify=verify)
        output = processed / f"{resource['projection_id'].lower()}--{resource['sha256'][:12]}.parquet" if parquet else None
        profiles.append(profile_projection(path, resource, parquet_path=output, batch_rows=batch_rows))
        print(f"  rows={profiles[-1]['rows']:,}, detail_numeric_total={profiles[-1]['detail_numeric_total']:,}, "
              f"published_total_rows={profiles[-1]['published_total_rows']:,}, "
              f"unmapped={profiles[-1]['unmapped_columns']}", flush=True)
    report = {
        "pipeline": "m1.0-bitre-source-staging",
        "source_observation_date": REFERENCE_DATE,
        "projection_count": len(profiles),
        "complete_17": len(profiles) == 17,
        "source_checksum_verified": verify,
        "outputs": "parquet" if parquet else "profile_only",
        "licence_status": "pending_review",
        "population_release_created": False,
        "confidentialisation": "BITRE suppresses counts under 3 and additionally perturbs/suppresses cells; preserve nonnumeric tokens.",
        "source_universe": "unrestricted vehicle registrations per NEVDIS; not insured fleet or policies",
        "profiles": profiles,
        "reconciliation": reconcile_profiles(profiles),
    }
    report_path = root / "data/reports/m1/bitre-2026-profile.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
