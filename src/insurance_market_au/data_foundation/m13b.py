"""M1.3b — source-conditioned, weighted synthetic fleet explorer extension.

Never join independently disclosed BITRE aggregate projections row-to-row.
Use separately fitted conditional categorical distributions to assign
make/model, postcode of registration, and postcode of garaging to the M1.3a
four-way synthetic cells. The output is Monte Carlo *analytic support*,
not observed vehicles, VIN-level records or a full-population release.

M1.3b conditional training:
  B26-15 state/class/year -> make/model
  B26-07 class/year -> make/model (fallback)
  B26-05 class/fuel -> make/model (fuel affinity)
  B26-13 state/class/make/model -> registration postcode
  B26-08 state/class/year -> registration postcode
  B26-06 state/class/fuel -> registration postcode
  B26-04 state/class -> registration postcode (fallback)
  B26-09 state/class/fuel -> garaging postcode (independent marginal)
Strictly withheld source projections are B26-14, B26-16 and B26-17.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import sqlite3
from typing import Any

import numpy as np

from insurance_market_au.data_foundation.m1 import (
    ROOT, REFERENCE_DATE, load_bitre_catalog,
)
from insurance_market_au.data_foundation.m13 import TOTAL

TRAIN_SPECS = {
    "B26-15": (("registered_state", "vehicle_type", "manufacture_year"), ("make", "model")),
    "B26-07": (("vehicle_type", "manufacture_year"), ("make", "model")),
    "B26-05": (("vehicle_type", "motive_power"), ("make", "model")),
    "B26-13": (("registered_state", "vehicle_type", "make", "model"), ("registered_postcode",)),
    "B26-08": (("registered_state", "vehicle_type", "manufacture_year"), ("registered_postcode",)),
    "B26-06": (("registered_state", "vehicle_type", "motive_power"), ("registered_postcode",)),
    "B26-04": (("registered_state", "vehicle_type"), ("registered_postcode",)),
    "B26-09": (("registered_state", "vehicle_type", "motive_power"), ("garaging_postcode",)),
}
HOLDOUT_SPECS = {
    "B26-14": ("vehicle_type", "manufacture_year", "motive_power", "make", "model"),
    "B26-16": ("vehicle_type", "registered_state", "registered_postcode", "manufacture_year", "make"),
    "B26-17": ("vehicle_type", "registered_state", "registered_postcode", "motive_power", "make", "model"),
}
VERSION = "m13b-conditional-v2"
SEED = 20261121
MINIMUM_SAMPLE = 64008
PATH_DB = "data/processed/m13b/conditionals.sqlite"
PATH_ROWS = "data/processed/m13b/weighted-synthetic-fleet.parquet"
PATH_REPORT = "data/reports/m13b/validation.json"


def _key(items: tuple[str, ...] | list[str]) -> str:
    return json.dumps(list(items), ensure_ascii=False, separators=(",", ":"))


def _stage_path(root: Path, item: dict) -> Path:
    return (root / "data/processed/m1/bitre" / REFERENCE_DATE /
            f"{item['projection_id'].lower()}--{item['sha256'][:12]}.parquet")


def _require_pyarrow():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("Install data and model extras: py -3 -m pip install -e \".[data,model,explore]\"") from exc
    return pa, pq


def _source_validations(source: dict, parquet) -> tuple[str, str]:
    if parquet.metadata.num_rows != source["expected_rows"]:
        raise ValueError(f"{source['projection_id']} source staging row-count drift")
    return (
        source["projection_id"],
        f"bitre-2026:{source['resource_id']}:{source['sha256'][:12]}",
    )


def _source_rows(source: dict, columns: tuple[str, ...], *, root: Path,
                 batch_rows: int = 40000):
    """Yield source detail batches after checking all pinned lineage/total invariants.

    This is intentionally a sequential reader: checksum-identified M1 staging
    files are independently validated rather than trusted as joined microdata.
    """
    _, pq = _require_pyarrow()
    path = _stage_path(root, source)
    if not path.is_file():
        raise FileNotFoundError(
            f"{source['projection_id']} staged source missing: {path}. "
            "Run py -3 scripts/m1_ingest.py --parquet"
        )
    p = pq.ParquetFile(path)
    pid, lineage = _source_validations(source, p)
    needed = list(dict.fromkeys((*columns, "source_row", "projection_id",
                                 "source_release_id", "observation_date",
                                 "vehicle_count", "count_status", "is_published_total")))
    if not set(needed) <= set(p.schema_arrow.names):
        raise ValueError(f"{pid} staged source is missing {sorted(set(needed) - set(p.schema_arrow.names))}")
    total_rows = 0
    detail_mass = 0
    total_flags = 0
    for batch in p.iter_batches(batch_size=batch_rows, columns=needed):
        data = batch.to_pydict()
        detail = []
        for i in range(batch.num_rows):
            total_rows += 1
            if (data["source_row"][i] != total_rows
                or data["projection_id"][i] != pid
                or data["source_release_id"][i] != lineage
                or data["observation_date"][i] != REFERENCE_DATE):
                raise ValueError(f"{pid}: source row/date/lineage drift at {total_rows}")
            if data["is_published_total"][i]:
                total_flags += 1
                continue
            mass = data["vehicle_count"][i]
            if mass is None:
                raise ValueError(f"{pid}: nonnumeric published cell requires a separate suppression policy")
            if (not isinstance(mass, int) or mass < 0 or
                data["count_status"][i] != "published_confidentialised_numeric"):
                raise ValueError(f"{pid}: invalid count/status at row {total_rows}")
            values = tuple(data[c][i] for c in columns)
            if any(v is None for v in values):
                raise ValueError(f"{pid}: missing published dimension at row {total_rows}")
            detail_mass += mass
            detail.append((values, mass))
        yield detail
    if (total_rows != source["expected_rows"]
        or detail_mass != source["expected_detail_numeric_total"]
        or total_flags != source["expected_published_total_rows"]):
        raise ValueError(f"{pid}: published count totals or physical row count changed")


def prepare_conditionals(root: Path = ROOT, *, rebuild: bool = False) -> dict:
    """Create local-only indexed SQLite conditional counts in a bounded-memory pass."""
    _, _ = _require_pyarrow()
    sources = {x["projection_id"]: x for x in load_bitre_catalog(root)}
    directory = root / "data/processed/m13b"
    directory.mkdir(parents=True, exist_ok=True)
    db_path = root / PATH_DB
    manifest_path = directory / "conditionals-manifest.json"
    signature = {
        "version": VERSION,
        "reference_date": REFERENCE_DATE,
        "sources": {pid: sources[pid]["sha256"] for pid in TRAIN_SPECS},
    }
    if db_path.is_file() and manifest_path.is_file() and not rebuild:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if all(existing.get(k) == signature[k] for k in signature):
            with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as con:
                tables = con.execute("SELECT COUNT(*) FROM conditional").fetchone()[0]
            if tables > 0:
                return existing
    partial = db_path.with_name(db_path.name + ".partial")
    partial.unlink(missing_ok=True)
    con = sqlite3.connect(partial)
    try:
        con.execute("PRAGMA journal_mode=OFF")
        con.execute("PRAGMA synchronous=OFF")
        con.execute("PRAGMA temp_store=MEMORY")
        con.execute("CREATE TABLE conditional (source_id TEXT NOT NULL, scope TEXT NOT NULL, choice TEXT NOT NULL, published_mass INTEGER NOT NULL)")
        observed = {}
        for pid, (scope_dims, choice_dims) in TRAIN_SPECS.items():
            print(f"[M1.3b] Indexing verified conditional source {pid}", flush=True)
            read_rows = 0
            for rows in _source_rows(sources[pid], (*scope_dims, *choice_dims), root=root):
                inserts = []
                for values, mass in rows:
                    scope = _key(values[:len(scope_dims)])
                    choice = _key(values[len(scope_dims):])
                    inserts.append((pid, scope, choice, mass))
                    if pid == "B26-09":
                        # State × type garaging fallback, derived ONLY from
                        # the same garaging-postcode publisher projection.
                        inserts.append(("B26-09-ST", _key(values[:2]),
                                        _key(values[3:]), mass))
                con.executemany("INSERT INTO conditional VALUES(?,?,?,?)", inserts)
                read_rows += len(inserts)
            observed[pid] = {
                "sha256": sources[pid]["sha256"],
                "detail_rows": read_rows,
                "original_dimensions": [*scope_dims, *choice_dims],
            }
        con.commit()
        con.execute("CREATE INDEX conditional_lookup ON conditional (source_id, scope)")
        con.commit()
        con.close()
        con = None
        os.replace(partial, db_path)
        report = {**signature,
                  "sources_processed": observed,
                  "local_db_file": str(db_path),
                  "candidate_source_count": len(TRAIN_SPECS),
                  "heldout_sources_excluded": list(HOLDOUT_SPECS),
                  "publisher_zero_is_not_structural": True,
                  "source_geography_roles_not_interchangeable": True}
        _atomic_json(manifest_path, report)
        return report
    finally:
        if con is not None:
            con.close()
        partial.unlink(missing_ok=True)


def _atomic_json(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


class ConditionalSampler:
    def __init__(self, path: Path, seed: int):
        self.conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        self.rng = np.random.default_rng(seed)
        self.fallbacks: Counter[str] = Counter()
        self._fuel_affinity = self._load_fuel_affinity()

    @lru_cache(maxsize=12000)
    def lookup(self, pid: str, scope: tuple[str, ...]) -> tuple[tuple[tuple[str, ...], ...], np.ndarray]:
        rows = self.conn.execute(
            "SELECT choice, SUM(published_mass) FROM conditional WHERE source_id=? AND scope=? GROUP BY choice ORDER BY choice",
            (pid, _key(scope)),
        ).fetchall()
        if not rows:
            return (), np.array([], dtype=np.float64)
        values = tuple(tuple(json.loads(choice)) for choice, _ in rows)
        # Small positive floor for publisher-zero categories; unobserved
        # combinations are dealt with through explicit parent fallbacks.
        counts = np.asarray([max(0, mass) + 0.5 for _, mass in rows], dtype=np.float64)
        return values, counts

    def _load_fuel_affinity(self) -> dict:
        # 05 contains only ~11,646 published cells, so this is a small
        # cache; it is used for a mild fuel-bias correction among choices
        # that are present in the state/class/year model distribution.
        counts: dict[tuple[str, str, str, str], float] = defaultdict(float)
        denominator: dict[tuple[str, str, str], float] = defaultdict(float)
        for scope, choice, mass in self.conn.execute(
            "SELECT scope,choice,SUM(published_mass) FROM conditional "
            "WHERE source_id='B26-05' GROUP BY scope,choice"
        ):
            klass, fuel = json.loads(scope)
            make, model = json.loads(choice)
            mass = max(0.0, float(mass))
            counts[klass, fuel, make, model] += mass
            denominator[klass, make, model] += mass
        return {k: (v + 0.5) / (denominator[k[0], k[2], k[3]] + 2.0)
                for k, v in counts.items()}

    def draw(self, pid: str, scope: tuple[str, ...], size: int = 1,
             *, affinity: dict | None = None) -> list[tuple[str, ...]]:
        items, mass = self.lookup(pid, scope)
        if not items:
            return []
        probabilities = mass.copy()
        if affinity is not None:
            for i, (make, model) in enumerate(items):
                factor = affinity.get((scope[1], scope[-1], make, model), 1.0)
                probabilities[i] *= np.clip(factor / 0.3, 0.25, 4.0) ** 0.5
        probabilities /= probabilities.sum()
        indexes = self.rng.choice(len(items), size=size, p=probabilities)
        return [items[i] for i in np.atleast_1d(indexes)]

    def model(self, state: str, klass: str, year: str, fuel: str, size: int) -> list[tuple[str, str]]:
        # Prefer source-observed make/model/year combinations. Adjust fuel
        # weights only within those source candidates (not the reverse).
        items, mass = self.lookup("B26-15", (state, klass, year))
        used = "B26-15"
        if not items:
            items, mass = self.lookup("B26-07", (klass, year))
            used = "B26-07"
        if not items:
            items, mass = self.lookup("B26-05", (klass, fuel))
            used = "B26-05"
        if not items:
            self.fallbacks["model_unknown"] += size
            return [("UNSPECIFIED", "UNSPECIFIED")] * size
        if used != "B26-15":
            self.fallbacks[f"model_fallback_{used}"] += size
        probs = mass.copy()
        if used in {"B26-15", "B26-07"}:
            for i, (make, model) in enumerate(items):
                factor = self._fuel_affinity.get((klass, fuel, make, model), 1.0)
                probs[i] *= float(np.clip(factor / 0.3, 0.2, 5.0) ** 0.5)
        probs /= probs.sum()
        chosen = self.rng.choice(len(items), size=size, p=probs)
        return [items[i] for i in np.atleast_1d(chosen)]

    def postcode(self, state: str, klass: str, year: str, fuel: str,
                 make: str, model: str) -> str:
        # Mixture of separately observed conditionals, not a false exact
        # model × year × fuel × postcode match.  Source 13 constrains the
        # model relationship; 08 and 06 constrain age and fuel relationships.
        u = self.rng.random()
        if u < 0.55:
            attempts = [
                ("B26-13", (state, klass, make, model)),
                ("B26-08", (state, klass, year)),
                ("B26-06", (state, klass, fuel)),
            ]
        elif u < 0.80:
            attempts = [
                ("B26-08", (state, klass, year)),
                ("B26-13", (state, klass, make, model)),
                ("B26-06", (state, klass, fuel)),
            ]
        else:
            attempts = [
                ("B26-06", (state, klass, fuel)),
                ("B26-13", (state, klass, make, model)),
                ("B26-08", (state, klass, year)),
            ]
        attempts.append(("B26-04", (state, klass)))
        for index, (pid, key) in enumerate(attempts):
            choice = self.draw(pid, key)
            if choice:
                if index:
                    self.fallbacks["registered_postcode_fallback"] += 1
                return str(choice[0][0])
        self.fallbacks["registered_postcode_unknown"] += 1
        return "UNSPECIFIED"

    def garage(self, state: str, klass: str, fuel: str) -> str:
        choice = self.draw("B26-09", (state, klass, fuel))
        if choice:
            return str(choice[0][0])
        # Never equate registration to garaging. Use only a broader
        # garaging marginal from B26-09 when the fuel cell is absent.
        fallback = self.draw("B26-09-ST", (state, klass))
        if fallback:
            self.fallbacks["garaging_postcode_state_type_fallback"] += 1
            return str(fallback[0][0])
        self.fallbacks["garaging_postcode_unknown"] += 1
        return "UNSPECIFIED"

    def close(self) -> None:
        self.conn.close()


def _allocations(weights: np.ndarray, requested: int, rng: np.random.Generator) -> np.ndarray:
    """PPS deterministic stratified allocation with >=1 row per positive cell.

    Every base four-way calibrated expected cell is retained exactly after
    assigning expected_mass / allocated_count to each of its sampled rows.
    """
    positive = weights > 0
    minimum = int(positive.sum())
    if requested < minimum:
        raise ValueError(
            f"Requested {requested:,} rows, but the four-way model has {minimum:,} "
            f"positive support cells; use --rows at least {minimum}"
        )
    extra = requested - minimum
    expected = extra * weights / weights.sum()
    floors = np.floor(expected).astype(np.int64)
    residual = int(extra - floors.sum())
    allocations = floors + positive.astype(np.int64)
    if residual:
        fractional = expected - floors
        choices = rng.choice(len(weights), size=residual, replace=False,
                             p=fractional / fractional.sum())
        allocations[choices] += 1
    if int(allocations.sum()) != requested or np.any(positive & (allocations <= 0)):
        raise ValueError("Sampling allocation invariant failed")
    return allocations


def _load_base_joint(root: Path):
    pa, pq = _require_pyarrow()
    path = root / "data/processed/m13/joint-state-type-year-fuel.parquet"
    report = root / "data/reports/m13/pilot-validation.json"
    if not path.is_file() or not report.is_file():
        raise FileNotFoundError("Fit M1.3a first: py -3 scripts/m13_fit.py")
    audit = json.loads(report.read_text(encoding="utf-8"))
    if (audit["published_total_operational_anchor"] != TOTAL
        or audit["reference_date"] != REFERENCE_DATE
        or audit["holdout_source"] != "B26-10"):
        raise ValueError("Stale or unexpected M1.3a source model")
    p = pq.read_table(path, columns=[
        "registered_state", "vehicle_type", "manufacture_year", "motive_power",
        "expected_synthetic_vehicles", "reference_date",
    ])
    if p.num_rows != audit["joint_support_cells"]:
        raise ValueError("The base fitted joint does not match its validation report")
    values = p.to_pydict()
    if set(values["reference_date"]) != {REFERENCE_DATE}:
        raise ValueError("Inconsistent base joint observation date")
    weights = np.asarray(values["expected_synthetic_vehicles"], dtype=np.float64)
    if (not np.all(np.isfinite(weights)) or np.any(weights < 0)
        or abs(float(weights.sum()) - TOTAL) > 0.01):
        raise ValueError("Four-way model does not preserve published national accounting mass")
    return values, weights, audit


def _sample_schema(pa):
    return pa.schema([
        ("synthetic_row_id", pa.int64()), ("registered_state", pa.string()),
        ("vehicle_type", pa.string()), ("manufacture_year", pa.string()),
        ("motive_power", pa.string()), ("make", pa.string()), ("model", pa.string()),
        ("registered_postcode", pa.string()), ("garaging_postcode", pa.string()),
        ("expected_vehicle_weight", pa.float64()),
        ("is_synthetic", pa.bool_()), ("uncertainty_kind", pa.string()),
    ])


def build_weighted_sample(root: Path = ROOT, *, rows: int = 220000,
                          seed: int = SEED, rebuild_conditionals: bool = False) -> dict:
    """Create a local filtered-analysis POC with exact four-way weighted totals."""
    pa, pq = _require_pyarrow()
    if rows > 2_000_000:
        raise ValueError("M1.3b POC max 2 million weighted sample rows, not 22.77m vehicle release")
    base, weights, old_report = _load_base_joint(root)
    preparation = prepare_conditionals(root, rebuild=rebuild_conditionals)
    rng = np.random.default_rng(seed)
    allocated = _allocations(weights, rows, rng)
    output = root / PATH_ROWS
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".partial")
    temp.unlink(missing_ok=True)
    schema = _sample_schema(pa)
    sampler = ConditionalSampler(root / PATH_DB, seed)
    writer = None
    storage = {field.name: [] for field in schema}
    observed = Counter()
    actual_weighted_mass = 0.0
    current_id = 0
    try:
        writer = pq.ParquetWriter(temp, schema, compression="zstd")
        def flush():
            for key in storage:
                if not storage[key]:
                    return
            writer.write_table(pa.Table.from_pydict(storage, schema=schema))
            for value in storage.values():
                value.clear()
        for idx, allocation in enumerate(allocated):
            if allocation <= 0:
                continue
            state = str(base["registered_state"][idx])
            klass = str(base["vehicle_type"][idx])
            year = str(base["manufacture_year"][idx])
            fuel = str(base["motive_power"][idx])
            mass = float(weights[idx])
            each = mass / int(allocation)
            models = sampler.model(state, klass, year, fuel, int(allocation))
            for make, model in models:
                reg_pc = sampler.postcode(state, klass, year, fuel, make, model)
                garage_pc = sampler.garage(state, klass, fuel)
                values = {
                    "synthetic_row_id": current_id,
                    "registered_state": state, "vehicle_type": klass,
                    "manufacture_year": year, "motive_power": fuel,
                    "make": make, "model": model,
                    "registered_postcode": reg_pc, "garaging_postcode": garage_pc,
                    "expected_vehicle_weight": each,
                    "is_synthetic": True,
                    "uncertainty_kind": "conditional_Monte_Carlo_not_observed_joint",
                }
                for key, value in values.items():
                    storage[key].append(value)
                current_id += 1
                actual_weighted_mass += each
                observed["rows"] += 1
                observed["unknown_make_model"] += int(make == "UNSPECIFIED")
                observed["unknown_registration_postcode"] += int(reg_pc == "UNSPECIFIED")
                observed["unknown_garaging_postcode"] += int(garage_pc == "UNSPECIFIED")
                if len(storage["synthetic_row_id"]) >= 25000:
                    flush()
            if idx % 8000 == 0:
                print(f"[M1.3b] four-way cells {idx+1:,}/{len(allocated):,}, "
                      f"synthetic weighted rows {current_id:,}/{rows:,}", flush=True)
        flush()
        writer.close()
        writer = None
        if current_id != rows or abs(actual_weighted_mass - TOTAL) > 0.1:
            raise ValueError("M1.3b weighted sample fails national expected mass invariant")
        os.replace(temp, output)
    finally:
        sampler.close()
        if writer is not None:
            writer.close()
        temp.unlink(missing_ok=True)
    if current_id != rows or abs(actual_weighted_mass - TOTAL) > 0.1:
        raise ValueError("M1.3b weighted sample fails national expected mass invariant")
    report = {
        "pipeline": VERSION,
        "status": "weighted_synthetic_analytic_POC_not_fleet_release",
        "national_published_accounting_anchor": TOTAL,
        "reference_date": REFERENCE_DATE,
        "rows": rows,
        "seed": seed,
        "base_joint_cells": len(weights),
        "base_joint_fit_source": str(root / "data/reports/m13/pilot-validation.json"),
        "weighted_total_expected": actual_weighted_mass,
        "exact_fourway_control_in_sample": True,
        "sample_file": str(output),
        "training_projections": list(TRAIN_SPECS),
        "heldout_projections_excluded_from_sampling": list(HOLDOUT_SPECS),
        "source_fingerprints": preparation["sources"],
        "conditional_sources": preparation["sources_processed"],
        "geographies_are_distinct": {
            "registered_postcode": "postcode_of_registration",
            "garaging_postcode": "reported_garaging_postcode_with_publisher_fallback",
            "pair_relationship_observed": False,
        },
        "model_caveats": [
            "Filters on make/model/postcodes produce conditional Monte Carlo estimates, not exact population counts",
            "National four-way calibration is preserved in *weighted* sample, not exact source-wise fine-grained margins",
            "Registered and garaging postcode are not observed jointly in published projections",
            "Model-year-fuel-location combination inferred from separately published aggregates",
            "BITRE low/zero counts are disclosure adjusted, not true structural zeros",
            "Rare vehicle/model or postcode selections with few effective synthetic samples are unstable",
            "Different dated state records and QLD VIN-prefix data were NOT used",
        ],
        "quality": {
            "unknown_attribute_counts": dict(observed),
            "fallback_counts": dict(sampler.fallbacks),
            "design": "one weighted representative per four-way support cell, extra samples allocated PPS",
        },
        "population_release_created": False,
        "source_microdata_linkage_performed": False,
    }
    _atomic_json(root / PATH_REPORT, report)
    return report


def validate_holdout_margins(
    root: Path = ROOT, *, minimum_published: int = 100,
) -> dict:
    """Evaluate *without tuning* the model on three separately published projections.

    For the 3.1m-row and 2.1m-row sources, metrics are restricted to
    originally published cells with counts >= minimum_published, rather than
    claiming the 220k synthetic POC represents every suppressed small cell.
    The three holdout source files are never consulted for conditional
    sampling or the source index.
    """
    if minimum_published < 1:
        raise ValueError("Only positive-count holdout cells may be compared")
    _, pq = _require_pyarrow()
    data_file = root / PATH_ROWS
    report_file = root / PATH_REPORT
    if not data_file.is_file() or not report_file.is_file():
        raise FileNotFoundError("Run the M1.3b weighted-sample build before validation")
    report = json.loads(report_file.read_text(encoding="utf-8"))
    if (report.get("status") != "weighted_synthetic_analytic_POC_not_fleet_release"
        or set(report["training_projections"]) & set(HOLDOUT_SPECS)):
        raise ValueError("M1.3b training/holdout isolation contract failed")
    sources = {x["projection_id"]: x for x in load_bitre_catalog(root)}
    sample = pq.ParquetFile(data_file)
    dimensions = set(v for cols in HOLDOUT_SPECS.values() for v in cols)
    if not dimensions <= set(sample.schema_arrow.names):
        raise ValueError("M1.3b synthetic sample lacks holdout comparison dimensions")
    estimates = {pid: defaultdict(float) for pid in HOLDOUT_SPECS}
    total = 0.0
    rows = 0
    for batch in sample.iter_batches(batch_size=25000,
                                     columns=[*sorted(dimensions), "expected_vehicle_weight","is_synthetic"]):
        data = batch.to_pydict()
        for i in range(batch.num_rows):
            if not data["is_synthetic"][i]:
                raise ValueError("M1.3b holdout validation must not use actual vehicles")
            mass = data["expected_vehicle_weight"][i]
            if mass is None or not math.isfinite(mass) or mass <= 0:
                raise ValueError("Invalid simulated expected mass")
            rows += 1
            total += mass
            for pid, cols in HOLDOUT_SPECS.items():
                key = tuple(data[c][i] for c in cols)
                estimates[pid][key] += mass
    if rows != report["rows"] or abs(total - TOTAL) > 0.1:
        raise ValueError("Model/validation sample total or row count changed")
    checks = []
    for pid, columns in HOLDOUT_SPECS.items():
        print(f"[M1.3b] Validating held-out published source {pid}", flush=True)
        published_cells = 0
        supported_cells = 0
        unsupported_cells = 0
        observed_mass = 0.0
        predicted_mass_on_published_cells = 0.0
        absolute_error = 0.0
        vintage = {"before_1980": [0.0,0.0,0], "before_1990":[0.0,0.0,0],
                   "before_2000":[0.0,0.0,0]}
        source = sources[pid]
        for batch in _source_rows(source, columns, root=root):
            for key, observed in batch:
                if observed < minimum_published:
                    continue
                published_cells += 1
                prediction = estimates[pid].get(key, 0.0)
                observed_mass += observed
                predicted_mass_on_published_cells += prediction
                error = abs(observed - prediction)
                absolute_error += error
                if key in estimates[pid]:
                    supported_cells += 1
                else:
                    unsupported_cells += 1
                if "manufacture_year" in columns:
                    field = key[columns.index("manufacture_year")]
                    if isinstance(field, str) and len(field) == 4 and field.isdecimal():
                        year = int(field)
                        for limit in (1980, 1990, 2000):
                            if year < limit:
                                accumulator = vintage[f"before_{limit}"]
                                accumulator[0] += observed
                                accumulator[1] += error
                                accumulator[2] += 1
        checks.append({
            "source_id":pid,
            "source_sha256":source["sha256"],
            "published_holdout_dimensions":list(columns),
            "count_threshold_for_this_metric":minimum_published,
            "published_cells_above_threshold":published_cells,
            "published_cells_covered_by_sample":supported_cells,
            "published_cells_unsupported_in_sample":unsupported_cells,
            "sum_published_counts_on_thresholded_cells":observed_mass,
            "sum_sample_expected_on_same_published_cells":predicted_mass_on_published_cells,
            "absolute_percentage_error_on_thresholded_cells":(
                absolute_error/observed_mass if observed_mass else None
            ),
            "older_cohorts_on_thresholded_cells":{
                k:{"source_count":v[0],"WAPE":v[1]/v[0] if v[0] else None,
                   "published_cells":v[2]} for k,v in vintage.items()
            },
            "holdout_used_for_fitting":False,
            "note":(
                "Diagnostic only: disclosure-adjusted published high-count cells "
                "vs a finite Monte Carlo weighted synthetic sample. Large errors "
                "are possible especially in rare model-year/postcode intersections. "
                "Not a measured error rate against physical vehicles."
            ),
        })
    report["heldout_validation"] = checks
    report["validation_status"] = "independent_heldout_source_checks_completed_not_vehicle_truth"
    _atomic_json(report_file, report)
    return report
