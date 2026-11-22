"""M1.5 immutable, source-audited local synthetic population releases.

A "published" release means content-frozen *local research asset*, NOT
commercial approval or an observed vehicle registry. The registry is a
directory of content-addressed frozen manifests; it has no mutable "latest"
pointer. Downstream consumers must pin a release_id and validate content.

Only two known model exporters are admitted: M1.3b uncalibrated baseline
or M1.4b weight-only research candidate. No raw BITRE source-record, VIN,
policy, individual driver or postcode-to-address data is ingested.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Iterator

from insurance_market_au.data_foundation.m1 import ROOT, REFERENCE_DATE, load_bitre_catalog, sha256_file
from insurance_market_au.data_foundation.m13 import TOTAL
from insurance_market_au.data_foundation.m13b import (
    HOLDOUT_SPECS, PATH_REPORT, PATH_ROWS, TRAIN_SPECS,
    _load_base_joint, _require_pyarrow, _sample_schema,
)
from insurance_market_au.data_foundation.m14 import read_sample_predictions
from insurance_market_au.data_foundation.m14b import (
    PATH_CALIBRATED, PATH_REPORT_CALIBRATED, VERSION as CALIBRATION_VERSION,
)

REGISTRY = "data/releases/population"
CONTRACT = "fleet-state-weighted-v1"
VERSION = "m15-population-registry-v1"
RELEASE_RE = re.compile(r"^pop-[0-9]{8}-[0-9a-f]{24}$")
BASE_DIMS = ("registered_state", "vehicle_type", "manufacture_year", "motive_power")
FILTER_DIMS = (*BASE_DIMS, "make", "model", "registered_postcode", "garaging_postcode")
OUTPUT_FILES = ("fleet-state.parquet", "fourway-controls.parquet")
SOURCE_IDS = tuple(dict.fromkeys(("B26-01","B26-02","B26-03",*TRAIN_SPECS)))
RESEARCH_LIMITATIONS = [
    "BITRE confidentialised published counts are not independently verified vehicle-level truth",
    "Model/year/fuel/postcode relationships are inferred across separately published aggregates",
    "Registration postcode and garaging postcode are different source roles; their pairing is unobserved",
    "Source-low and published-zero categories do not imply true physical zero vehicles",
    "Sparse historic and make/model/postcode segment estimates are not approved for pricing",
    "Weighted representative records are neither registered physical vehicles nor policies",
    "An asset published in the local registry does NOT mean approved for commercial deployment",
]


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: dict) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2,
                  ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _destination(root: Path, release_id: str) -> Path:
    if not RELEASE_RE.fullmatch(release_id):
        raise ValueError("Invalid population release ID; path traversal and aliases forbidden")
    return root / REGISTRY / release_id


def _schema_contract(root: Path):
    from jsonschema import Draft202012Validator, FormatChecker
    # Contract is repository code, not part of the isolated data/root
    # that contains staged/modelled source files (e.g. a pytest fixture).
    f = ROOT / "contracts/schemas/population-release.schema.json"
    if not f.is_file():
        raise FileNotFoundError(f"Population metadata schema unavailable: {f}")
    document = json.loads(f.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(document)
    return Draft202012Validator(document, format_checker=FormatChecker())


def _parquet_properties(path: Path, *, controls: Path | None = None) -> dict:
    """Verify exact weighted-synthetic Arrow schema and four-way mass.

    Stream batches so a research release can be verified without ever
    materialising a 22.77m vehicle table or relying on original research
    input files. A frozen four-way control snapshot is the accounting proof.
    """
    pa, pq = _require_pyarrow()
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing, invalid or symlinked fleet Parquet: {path}")
    reader = pq.ParquetFile(path)
    expected = _sample_schema(pa)
    if not reader.schema_arrow.equals(expected, check_metadata=False):
        raise ValueError("Physical vehicle field names, types or semantics differ from fleet-state-weighted-v1")
    if not reader.metadata.num_rows:
        raise ValueError("Empty synthetic population cannot be released")
    seen_ids: set[int] = set()
    sum_weight = 0.0
    squared_weight = 0.0
    base_mass: dict[tuple[str, str, str, str], float] = defaultdict(float)
    sample_size = 0
    for batch in reader.iter_batches(batch_size=24000,
                                     columns=["synthetic_row_id", *BASE_DIMS,
                                              "expected_vehicle_weight", "is_synthetic"]):
        values = batch.to_pydict()
        for i in range(batch.num_rows):
            row_id = values["synthetic_row_id"][i]
            weight = values["expected_vehicle_weight"][i]
            if (type(row_id) is not int or row_id < 0 or row_id in seen_ids
                or values["is_synthetic"][i] is not True
                or weight is None or not math.isfinite(weight) or weight <= 0):
                raise ValueError("Non-synthetic, duplicate-ID or invalid-weight population row")
            dims = tuple(values[k][i] for k in BASE_DIMS)
            if any(not isinstance(k, str) or not k for k in dims):
                raise ValueError("Missing or malformed four-way vehicle classifications")
            seen_ids.add(row_id)
            sample_size += 1
            sum_weight += weight
            squared_weight += weight * weight
            base_mass[dims] += weight
    if len(seen_ids) != sample_size or min(seen_ids) != 0 or max(seen_ids) != sample_size - 1:
        raise ValueError("Synthetic row IDs must form a stable unique sequence 0..n-1")
    if abs(sum_weight - TOTAL) > 0.1:
        raise ValueError("Released expected national fleet mass does not match accounting controls")
    maximum_difference = None
    control_rows = None
    if controls is not None:
        if controls.is_symlink() or not controls.is_file():
            raise ValueError("Frozen original four-way controls missing or symlinked")
        control = pq.read_table(controls)
        required = set((*BASE_DIMS, "expected_synthetic_vehicles"))
        if not required <= set(control.column_names):
            raise ValueError("Snapshot of original four-way control columns is incomplete")
        values = control.to_pydict()
        original = {
            tuple(values[k][i] for k in BASE_DIMS): float(values["expected_synthetic_vehicles"][i])
            for i in range(control.num_rows)
        }
        if len(original) != control.num_rows or set(base_mass) != {k for k,v in original.items() if v>0}:
            raise ValueError("Missing, extra or duplicate original positive four-way support cells")
        maximum_difference = max(abs(v - base_mass.get(k, 0.0)) for k,v in original.items())
        control_rows = len(original)
        if maximum_difference > 1e-5:
            raise ValueError(f"Original state/type/year/fuel accounting control drift: {maximum_difference}")
    return {
        "synthetic_rows": sample_size,
        "expected_vehicles": sum_weight,
        "effective_sample_size": sum_weight**2/squared_weight,
        "fourway_positive_support": len(base_mass),
        "fourway_control_rows": control_rows,
        "maximum_fourway_count_residual": maximum_difference,
        "data_schema": CONTRACT,
        "source_records_or_real_vehicles_exported": False,
    }


def _inputs(root: Path, kind: str):
    if kind not in ("baseline", "candidate"):
        raise ValueError("Choose baseline or candidate; arbitrary paths cannot be published")
    original_file = root / PATH_ROWS
    baseline_report = root / PATH_REPORT
    if not original_file.is_file() or not baseline_report.is_file():
        raise FileNotFoundError("Create M1.3b weighted sample first: py -3 scripts/m13b_expand.py")
    base_report = json.loads(baseline_report.read_text(encoding="utf-8"))
    if base_report.get("status") != "weighted_synthetic_analytic_POC_not_fleet_release":
        raise ValueError("Unrecognised M1.3b research provenance")
    if base_report.get("reference_date") != REFERENCE_DATE:
        raise ValueError("Synthetic model reference date differs from January 2026")
    if set(base_report.get("training_projections", [])) != set(TRAIN_SPECS):
        raise ValueError("Unexpected conditional source training list")
    if set(base_report.get("heldout_projections_excluded_from_sampling", [])) != set(HOLDOUT_SPECS):
        raise ValueError("M1.3b independent holdout source firewall differs")
    _, assurance = read_sample_predictions(root, original_file, baseline_report)
    baseline_sha = assurance["sample_sha256"]

    source = original_file if kind == "baseline" else root / PATH_CALIBRATED
    source_report = baseline_report if kind == "baseline" else root / PATH_REPORT_CALIBRATED
    if not source.is_file() or not source_report.is_file():
        raise FileNotFoundError("Create calibrated M1.4b candidate first: py -3 scripts/m14b_calibrate.py")
    upstream = json.loads(source_report.read_text(encoding="utf-8"))
    if kind == "candidate":
        if (upstream.get("pipeline") != CALIBRATION_VERSION
            or upstream.get("original_m13b_sha256") != baseline_sha
            or upstream.get("calibrated_sample_sha256") != sha256_file(source)
            or upstream.get("reference_date") != REFERENCE_DATE
            or set(upstream.get("training_source_ids",[])) != set(TRAIN_SPECS)
            or set(upstream.get("heldout_ids_strictly_excluded",[])) != set(HOLDOUT_SPECS)
            or upstream.get("governance",{}).get("automatic_promotion_to_production") is not False):
            raise ValueError("M1.4b candidate provenance/source isolation failed")
    model_version = base_report["pipeline"] if kind=="baseline" else upstream["pipeline"]
    # M1.4b must retain all identical attribute rows, not only its counts.
    if kind=="candidate":
        _, pq = _require_pyarrow()
        a, b = pq.ParquetFile(original_file), pq.ParquetFile(source)
        if a.schema_arrow != b.schema_arrow or a.metadata.num_rows != b.metadata.num_rows:
            raise ValueError("Candidate changes underlying synthetic source schema/rows")
        cols = [n for n in a.schema_arrow.names if n != "expected_vehicle_weight"]
        ai = a.iter_batches(batch_size=24000,columns=cols)
        bi = b.iter_batches(batch_size=24000,columns=cols)
        for x,y in zip(ai,bi,strict=True):
            if not x.equals(y):
                raise ValueError("Candidate changes synthetic row attributes/identifiers")
    original_controls = root / "data/processed/m13/joint-state-type-year-fuel.parquet"
    if not original_controls.is_file():
        raise FileNotFoundError("The immutable four-way control snapshot requires the original M1.3a Parquet")
    raw = {x["projection_id"]:x for x in load_bitre_catalog(root)}
    sources = {pid: raw[pid]["sha256"] for pid in SOURCE_IDS}
    if base_report["source_fingerprints"] != {pid:sources[pid] for pid in TRAIN_SPECS}:
        raise ValueError("Published training source checksums differ from M1.3b sample")
    original_controls_digest=sha256_file(original_controls)
    source_digest=sha256_file(source)
    upstream_digest=sha256_file(source_report)
    return source, source_report, original_controls, {
        "kind":kind, "model_version":model_version,
        "source_sha256":source_digest, "baseline_sha256":baseline_sha,
        "upstream_report_sha256":upstream_digest,
        "base_m13b_report_sha256":sha256_file(baseline_report),
        "original_fourway_controls_sha256":original_controls_digest,
        "source_projection_sha256":sources,
        "seed":int(base_report["seed"]),
        "sample_size":int(base_report["rows"]),
        "source_holdout_ids":list(HOLDOUT_SPECS),
        "calibration_approved":False,
    }


def _quality(root: Path, context: dict, metrics: dict) -> dict:
    kind = context["kind"]
    return {
        "schema_version": "m15-quality-v1",
        "model_kind": kind,
        "model_version": context["model_version"],
        "reference_date":REFERENCE_DATE,
        "input_provenance": context,
        "fleet_controls":metrics,
        "source_ids":list(SOURCE_IDS),
        "statistics": {
            "measured_holdout_error_for_this_release": None,
            "measured_holdout_available": False,
            "why": (
                "This frozen release has not independently demonstrated model accuracy "
                "for individual make/model/postcode vehicle populations. Earlier "
                "85k-row experiment errors must not be reused for a different seed/size."
            ),
        },
        "quality_gates":{
            "original_fourway_expected_masses_verified":True,
            "schema_and_positive_weights_verified":True,
            "confidentialised_source_zeros_are_not_structural":True,
            "make_model_postcode_associations_empirically_verified":False,
            "vehicle_level_truth_confirmed":False,
            "licence_and_privacy_review_approved":False,
            "commercial_pricing_use_approved":False,
            "insurance_exposure_representation_confirmed":False,
            "research_asset_publishable":True,
        },
        "release_purpose":"research_only_immutable_input_for_sensitivity_and_feature_prototyping",
        "estimate_uncertainty": (
            "Finite synthetic sample uncertainty plus unquantified model/source "
            "uncertainty. ESS is not a credible interval for insured market size."
        ),
        "limitations": RESEARCH_LIMITATIONS,
    }


def _manifest_payload(context: dict, quality_sha: str, fleet_sha: str,
                      control_sha: str) -> dict:
    return {
        "registry_version":VERSION,
        "reference_date":REFERENCE_DATE,
        "dataset_schema_version":CONTRACT,
        "method":context["model_version"],
        "model_kind":context["kind"],
        "model_source_sha256":fleet_sha,
        "model_report_sha256":context["upstream_report_sha256"],
        "fourway_controls_sha256":control_sha,
        "quality_sha256":quality_sha,
        "sampling_seed":context["seed"],
        "input_source_shas":context["source_projection_sha256"],
    }


def _manifest(context: dict, metrics: dict, payload: dict,
              digest: str, release_id: str) -> dict:
    return {
        "schema_version":"1.0.0",
        "release_id":release_id,
        "status":"published",
        "created_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reference_date":REFERENCE_DATE,
        "universe":"registered_all",
        "dataset_schema_version":CONTRACT,
        "source_ids":list(SOURCE_IDS),
        "source_definition": (
            "BITRE January 2026 published registration-stock accounting universe; "
            "not personal vehicle data, insured risk exposures or historic QLD flows"
        ),
        "geography_version":"BITRE-2026-registration-and-garaging-postcode-roles",
        "synthesis":{
            "method": context["kind"]+"_weighted_synthetic",
            "model_version":context["model_version"],
            "population_draw_id":f"sample-{context['seed']}-n{context['sample_size']}",
            "random_algorithm":"PCG64",
            "random_seed":context["seed"],
            "parameters_uri":"quality-report.json",
        },
        "outputs":[
            {"table":"fleet_state","uri":OUTPUT_FILES[0],
             "representation":"weighted_sample",
             "row_count":metrics["synthetic_rows"],
             "weighted_vehicle_count":metrics["expected_vehicles"],
             "content_sha256":payload["model_source_sha256"]},
            {"table":"fourway_controls","uri":OUTPUT_FILES[1],
             "representation":"aggregate",
             "row_count":metrics["fourway_control_rows"],
             "weighted_vehicle_count":TOTAL,
             "content_sha256":payload["fourway_controls_sha256"]},
        ],
        "quality_report_uri":"quality-report.json",
        "release_content_sha256":digest,
        "known_limitations":RESEARCH_LIMITATIONS,
    }


def publish_population(root: Path=ROOT, *, kind: str="baseline") -> dict:
    """Publish an isolated, frozen, content-addressed RESEARCH population.

    No existing release is ever rewritten. Source files are snapshotted into
    a temporary sibling and atomically renamed once complete. Identical
    source/model/version content is idempotent; corrupted identical-ID
    directories make a release fail loudly.
    """
    source, report_path, controls, context = _inputs(root,kind)
    metrics=_parquet_properties(source,controls=controls)
    if metrics["synthetic_rows"]!=context["sample_size"]:
        raise ValueError("Population count does not agree with source simulation manifest")
    quality=_quality(root,context,metrics)
    quality_sha=_sha(quality)
    payload=_manifest_payload(context,quality_sha,context["source_sha256"],
                              context["original_fourway_controls_sha256"])
    digest=_sha(payload)
    release_id=f"pop-{REFERENCE_DATE.replace('-','')}-{digest[:24]}"
    destination=_destination(root,release_id)
    if destination.exists():
        result=verify_population(root,release_id)
        if result["manifest"]["release_content_sha256"] != digest:
            raise ValueError("Existing content-addressed population conflicts with requested release")
        return {**result, "created":False}
    registry=root/REGISTRY
    registry.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix=".m15-pending-",dir=registry))
    try:
        for original,name,digest_expected in (
            (source,OUTPUT_FILES[0],context["source_sha256"]),
            (controls,OUTPUT_FILES[1],context["original_fourway_controls_sha256"]),
        ):
            with original.open("rb") as src, (staging/name).open("xb") as dst:
                shutil.copyfileobj(src,dst,1024*1024)
                dst.flush()
                os.fsync(dst.fileno())
            if sha256_file(staging/name)!=digest_expected or sha256_file(original)!=digest_expected:
                raise ValueError("A source file changed during content-addressed publication")
        _write_json(staging/"quality-report.json",quality)
        _write_json(staging/"manifest.json",
                    _manifest(context,metrics,payload,digest,release_id))
        if _sha(json.loads((staging/"quality-report.json").read_text(encoding="utf-8")))!=quality_sha:
            raise ValueError("Quality metadata failed reproducible content encoding")
        try:
            os.rename(staging,destination)
        except OSError:
            if not destination.is_dir():
                raise
            existing=verify_population(root,release_id)
            if existing["manifest"]["release_content_sha256"]!=digest:
                raise ValueError("Concurrent release creation produced mismatched immutable content")
            return {**existing,"created":False}
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    result=verify_population(root,release_id)
    return {**result,"created":True}


def verify_population(root: Path, release_id: str) -> dict:
    """Validate the entire frozen release without requiring source acquisition.

    Consumers should verify once on open, not assume the local filesystem
    enforces true physical write protection.
    """
    directory=_destination(root,release_id)
    if not directory.is_dir() or directory.is_symlink():
        raise FileNotFoundError(f"Population release missing: {release_id}")
    file=directory/"manifest.json"
    if file.is_symlink() or not file.is_file():
        raise ValueError("Missing, symlinked or damaged release manifest")
    manifest=json.loads(file.read_text(encoding="utf-8"))
    errors=list(_schema_contract(root).iter_errors(manifest))
    if errors:
        raise ValueError("Population release JSON Schema violation: "+errors[0].message)
    if (manifest["release_id"]!=release_id or manifest["status"]!="published"
        or manifest["universe"]!="registered_all" or manifest["reference_date"]!=REFERENCE_DATE
        or manifest["dataset_schema_version"]!=CONTRACT
        or manifest["source_ids"]!=list(SOURCE_IDS)
        or manifest["quality_report_uri"]!="quality-report.json"
        or [o["uri"] for o in manifest["outputs"]]!=list(OUTPUT_FILES)
        or [o["table"] for o in manifest["outputs"]] != ["fleet_state","fourway_controls"]
        or [o["representation"] for o in manifest["outputs"]] != ["weighted_sample","aggregate"]):
        raise ValueError("Unknown or malicious release layout, population universe or schema")
    quality_path=directory/"quality-report.json"
    if quality_path.is_symlink() or not quality_path.is_file():
        raise ValueError("Missing or symlinked quality evidence")
    quality=json.loads(quality_path.read_text(encoding="utf-8"))
    if (quality.get("quality_gates",{}).get("commercial_pricing_use_approved") is not False
        or quality.get("quality_gates",{}).get("research_asset_publishable") is not True
        or quality.get("reference_date")!=REFERENCE_DATE
        or quality.get("model_version")!=manifest["synthesis"]["model_version"]):
        raise ValueError("Research quality controls or lineage were changed")
    for name,output in zip(OUTPUT_FILES,manifest["outputs"]):
        if (directory/name).is_symlink() or sha256_file(directory/name)!=output["content_sha256"]:
            raise ValueError(f"Frozen population release file changed: {name}")
    context=quality["input_provenance"]
    payload=_manifest_payload(context,_sha(quality),
        manifest["outputs"][0]["content_sha256"],manifest["outputs"][1]["content_sha256"])
    digest=_sha(payload)
    if (manifest["release_content_sha256"]!=digest
        or release_id!=f"pop-{REFERENCE_DATE.replace('-','')}-{digest[:24]}"):
        raise ValueError("Content digest or release ID differs from frozen quality/Parquet inputs")
    properties=_parquet_properties(directory/OUTPUT_FILES[0],
                                  controls=directory/OUTPUT_FILES[1])
    if (properties["synthetic_rows"]!=manifest["outputs"][0]["row_count"]
        or properties["fourway_control_rows"]!=manifest["outputs"][1]["row_count"]
        or abs(properties["expected_vehicles"]-manifest["outputs"][0]["weighted_vehicle_count"])>0.1
        or properties["maximum_fourway_count_residual"]>1e-5):
        raise ValueError("Released synthetic fleet no longer matches its physical control metadata")
    return {
        "release_id":release_id,
        "manifest":manifest,
        "quality":quality,
        "physical_checks":properties,
        "directory":str(directory),
        "verified":True,
    }


def list_populations(root: Path=ROOT) -> list[dict]:
    """Discover completed local research releases; never rely on a latest alias."""
    directory=root/REGISTRY
    if not directory.exists():
        return []
    found=[]
    for path in directory.iterdir():
        if not path.is_dir() or path.is_symlink() or not RELEASE_RE.fullmatch(path.name):
            continue
        try:
            manifest=json.loads((path/"manifest.json").read_text(encoding="utf-8"))
            if manifest["release_id"]!=path.name:
                raise ValueError("Manifest ID differs from location")
            found.append({
                "release_id":path.name,
                "reference_date":manifest["reference_date"],
                "model_version":manifest["synthesis"]["model_version"],
                "population_draw_id":manifest["synthesis"]["population_draw_id"],
                "rows":manifest["outputs"][0]["row_count"],
                "expected_vehicles":manifest["outputs"][0]["weighted_vehicle_count"],
                "status":manifest["status"],
                "verification":"must_verify_before_use",
                "commercially_approved":False,
            })
        except (OSError,ValueError,KeyError,TypeError) as exc:
            found.append({"release_id":path.name,"status":"unreadable",
                          "verification":"failed","reason":str(exc),"commercially_approved":False})
    return sorted(found,key=lambda x:x["release_id"])
