"""M1.2 jurisdiction-specific evidence harmonisation.

Reads locally acquired public source bytes; no raw data, unique vehicles,
or publisher categories are exported to Git.  Normalised cells remain
source-specific and do NOT imply the Australian joint distribution is known.

In particular:
- NSW ZIPs contain multiple MONTHLY source partitions and censored '<=5' counts.
- SA owner postcode and VIC garaging postcode are not equal constructs.
- QLD historical unit-like records have unverified grain: no count=1 shortcut.
- Registration stock and new/transfer flows are never added together.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime
from io import TextIOWrapper
import calendar
import csv
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterator
from zipfile import BadZipFile, ZipFile

from insurance_market_au.data_foundation.m1 import ROOT, sha256_file

REGISTRY = ROOT / "catalog/harmonization/m12-sources.json"
REFERENCE_DATE = "2026-01-31"
MONTH_RE = re.compile(r"_(20\d{2})(0[1-9]|1[0-2])_(?:\d+)\.csv$", re.I)
GOV_ACT_MANUAL_SHA = "6c74e748699ceb61c9a9b69f9bb4a7e5ce012307cbdd3db1525de9b29eab7a2d"
STATE_LABEL = {"NSW":"NSW","Vic":"Vic","Qld":"Qld","SA":"SA",
               "WA":"WA","Tas":"Tas","NT":"NT","ACT":"ACT"}


def load_registry(root: Path = ROOT) -> dict[str, Any]:
    cfg=json.loads((root/"catalog/harmonization/m12-sources.json").read_text(encoding="utf-8"))
    if cfg["reference_bitre_date"] != REFERENCE_DATE:
        raise ValueError("M1.2 BITRE control vintage drift")
    spec_ids=[x.get("id") or x.get("id_prefix") for x in cfg["sources"]]
    if len(spec_ids)!=len(set(spec_ids)):
        raise ValueError("Duplicate source IDs/prefixes in M1.2 source registry")
    return cfg


def match_source(cfg: dict, source_id: str) -> dict | None:
    matched=[
        spec for spec in cfg["sources"]
        if source_id == spec.get("id")
        or (spec.get("id_prefix") and source_id.startswith(spec["id_prefix"]))
    ]
    if len(matched)>1:
        raise ValueError(f"Ambiguous source {source_id} matches multiple M1.2 policies")
    return matched[0] if matched else None


def read_acquisitions(root: Path = ROOT) -> dict[str, dict]:
    """Latest *successfully acquired* version per ID, not catalogue list entries."""
    reports=root/"data/reports"
    result={}
    for p in sorted(reports.glob("acquisition-*.json")):
        report=json.loads(p.read_text(encoding="utf-8"))
        if report.get("mode")!="download":
            continue
        for row in report.get("resources", []):
            if row.get("status")!="downloaded" or not row.get("source_id"):
                continue
            if not row.get("sha256") or not row.get("path"):
                continue
            result[row["source_id"]]=row
    return result


def _resolve_acquired_path(root: Path, raw_dir: Path, row: dict) -> Path:
    supplied=Path(row["path"])
    path=(supplied if supplied.is_absolute() else root/supplied).resolve()
    safe=raw_dir.resolve()
    if not path.is_relative_to(safe):
        raise ValueError(f"Acquisition path outside raw source directory: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Downloaded source no longer present: {path}")
    if path.suffix.lower() not in {".csv",".zip"}:
        raise ValueError(f"Unexpected source format in {path}")
    if not re.fullmatch(r"[0-9a-f]{64}", str(row["sha256"]).lower()):
        raise ValueError("Invalid acquisition SHA-256")
    # Fast preflight matching immutable hash-named acquisition files; full
    # cryptographic check happens in scan_source before row processing.
    if f"--{row['sha256'][:12]}" not in path.name:
        raise ValueError(f"File name is inconsistent with acquisition hash: {path}")
    return path


def select_sources(root: Path, cfg: dict, groups: set[str]) -> tuple[list[dict], list[dict]]:
    rows=read_acquisitions(root)
    raw=(root/"data/raw").resolve()
    selected=[]
    warnings=[]
    for sid, row in sorted(rows.items()):
        spec=match_source(cfg,sid)
        if (spec is None or spec["tier"]=="quarantined"
                or not (spec["group"] in groups
                        or (spec["group"]=="sa_mirror" and "sa" in groups))):
            continue
        try:
            path=_resolve_acquired_path(root,raw,row)
        except (ValueError,FileNotFoundError) as exc:
            warnings.append({"source_id":sid,"status":"local_source_invalid","detail":str(exc)})
            continue
        selected.append({"source_id":sid,"spec":spec,"acquisition":row,"path":path,"manual":False})
    # ACT's downloaded-using-Windows-PowerShell file is outside the original
    # failed Python acquisition report and is explicitly verified by hash.
    if "act" in groups and not any(s["source_id"]=="act_make_model_suburb" for s in selected):
        act_spec=match_source(cfg,"act_make_model_suburb")
        path=raw/"act"/"2026"/act_spec["manual_filename"]
        if path.is_file():
            selected.append({
                "source_id":"act_make_model_suburb","spec":act_spec,"path":path,"manual":True,
                "acquisition":{"source_id":"act_make_model_suburb",
                               "sha256":act_spec["manual_sha256"],
                               "url":"https://www.data.act.gov.au/api/views/h4vn-y97q/rows.csv?accessType=DOWNLOAD",
                               "source":"manual_official_powershell_download"},
            })
        else:
            warnings.append({"source_id":"act_make_model_suburb","status":"missing_manual_act",
                             "detail":"Manual download not found; original Python attempt had an SSL certificate failure"})
    # South Australian mirror is FALLBACK ONLY, never added alongside original.
    if "sa" in groups:
        official=[x for x in selected if x["spec"]["group"]=="sa"]
        mirrors=[x for x in selected if x["spec"]["group"]=="sa_mirror"]
        if official:
            selected=[x for x in selected if x["spec"]["group"]!="sa_mirror"]
            for m in mirrors:
                status=("mirror_checksum_matches_official"
                        if any(m["acquisition"]["sha256"]==o["acquisition"]["sha256"]
                               for o in official) else "mirror_checksum_differs_review_required")
                warnings.append({"source_id":m["source_id"],"status":status,
                                 "detail":"Mirror not counted or staged; official SA source preferred"})
        elif mirrors:
            selected=[x for x in selected if x["spec"]["group"]!="sa_mirror"]+[mirrors[-1]]
            warnings.append({"source_id":mirrors[-1]["source_id"],
                             "status":"third_party_mirror_fallback",
                             "detail":"No official local SA file; do not approve publisher parity until checked"})
    # User can deliberately request sa_mirror only for isolated provenance audit.
    if "sa" not in groups and "sa_mirror" not in groups:
        selected=[x for x in selected if x["spec"]["group"]!="sa_mirror"]
    if "nsw" in groups:
        warnings.append({"source_id":"nsw_age_2026","status":"publisher_payload_quarantined",
                         "detail":"Official age URL returned the heavy configuration ZIP; never use as vehicle age"})
    selected.sort(key=lambda x:(x["spec"]["group"],x["source_id"]))
    return selected,warnings


def count_token(value: str | None, measure_col: str | None) -> dict[str, Any]:
    if measure_col is None:
        return {"status":"unverified_grain_no_count_inferred","count":None,
                "lower":None,"upper":None}
    raw="" if value is None else str(value).strip()
    if re.fullmatch(r"\d+(?:,\d{3})*",raw):
        number=int(raw.replace(",",""))
        return {"status":"published_numeric_not_truth","count":number,"lower":number,"upper":number}
    # NSW privacy redaction is marked <=5 in actual 2026 ZIPs.
    # ACT often suppresses <=10; an explicitly displayed inequality is bounded.
    match=re.fullmatch(r"(?:<=|≤)\s*(\d+)",raw)
    if match:
        limit=int(match.group(1))
        return {"status":"right_censored_published_upper_bound",
                "count":None,"lower":0,"upper":limit}
    if raw in {"","-","..","*","n/a","N/A","suppressed","Suppressed","NP"}:
        return {"status":"missing_or_suppressed_unbounded","count":None,
                "lower":None,"upper":None}
    return {"status":"unrecognised_count_token_requires_review",
            "count":None,"lower":None,"upper":None}


def parse_date(value: Any) -> str | None:
    if isinstance(value,datetime):
        return value.date().isoformat()
    if isinstance(value,date):
        return value.isoformat()
    text=str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d\d-\d\d",text):
        try:return date.fromisoformat(text).isoformat()
        except ValueError:return None
    for fmt in ("%d/%m/%Y","%Y/%m/%d","%d-%m-%Y","%d %B %Y","%d %b %Y",
                "%Y-%m-%dT%H:%M:%S.%f","%Y-%m-%dT%H:%M:%S"):
        try:return datetime.strptime(text,fmt).date().isoformat()
        except ValueError:continue
    return None


def zip_member_date(name: str) -> str:
    match=MONTH_RE.search(name)
    if match is None:
        raise ValueError(f"Unknown NSW monthly ZIP member vintage: {name}")
    year,month=map(int,match.groups())
    if year!=2026:
        raise ValueError(f"Source ZIP contains unexpected {year} monthly snapshot/flow")
    return date(year,month,calendar.monthrange(year,month)[1]).isoformat()


def _delimiter(header: str) -> str:
    # NSW official uses quoted pipe-separated files; VIC/SA/ACT use comma.
    return "|" if header.count("|")>header.count(",") else ","


@contextmanager
def _csv_reader_from_binary(stream):
    wrapper=TextIOWrapper(stream,encoding="utf-8-sig",errors="replace",newline="")
    try:
        first=wrapper.readline()
        if not first.strip():
            raise ValueError("Empty source member/file")
        delimiter=_delimiter(first)
        # CSV DictReader must receive the first line too (do not consume header).
        import itertools
        reader=csv.DictReader(itertools.chain([first],wrapper),delimiter=delimiter)
        yield reader
    finally:
        wrapper.detach()


def _iter_source_members(path: Path,spec: dict) -> Iterator[tuple[str,Any,str | None]]:
    if spec["format"]=="csv":
        with path.open("rb") as fp:
            with _csv_reader_from_binary(fp) as reader:
                yield path.name,reader,None
    elif spec["format"]=="zip":
        with ZipFile(path) as archive:
            infos=[i for i in archive.infolist() if not i.is_dir() and i.filename.lower().endswith(".csv")]
            if not infos:
                raise ValueError(f"No CSV members inside {path.name}")
            if len(set(x.filename for x in infos))!=len(infos):
                raise ValueError("ZIP archive contains duplicate member names")
            if any(i.file_size>500*1024*1024 for i in infos):
                raise ValueError("ZIP member exceeds 500 MiB security limit")
            # Preserve each month; sort chronologically so the same split
            # month cannot become a falsely independent 'latest snapshot'.
            for info in sorted(infos,key=lambda x:x.filename):
                if info.filename.startswith("/") or ".." in Path(info.filename).parts:
                    raise ValueError("Unsafe ZIP member name")
                snapshot=zip_member_date(info.filename)
                with archive.open(info) as fp:
                    with _csv_reader_from_binary(fp) as reader:
                        yield info.filename,reader,snapshot
    else:
        raise ValueError(f"Unsupported M1.2 physical format: {spec['format']}")


def _stage_schema():
    try:import pyarrow as pa
    except ImportError as exc:
        raise RuntimeError('Install Parquet extras: py -3 -m pip install -e ".[data]"') from exc
    return pa.schema([
        ("source_id",pa.string()),("source_sha256",pa.string()),("source_member",pa.string()),
        ("source_row",pa.int64()),("jurisdiction",pa.string()),
        ("observation_date",pa.string()),("observation_precision",pa.string()),
        ("measure_kind",pa.string()),("source_grain",pa.string()),
        ("geography_role",pa.string()),("geography_value",pa.string()),
        ("make",pa.string()),("model",pa.string()),("source_vehicle_class",pa.string()),
        ("source_manufacture_year",pa.string()),("source_fuel",pa.string()),
        ("source_attributes_json",pa.string()),("count_raw",pa.string()),
        ("published_count",pa.int64()),("count_lower",pa.int64()),("count_upper",pa.int64()),
        ("count_status",pa.string()),("candidate_bitre_class",pa.string()),
        ("bitre_class_mapping_status",pa.string()),
    ])


def _table(rows: list[dict],schema):
    import pyarrow as pa
    return pa.Table.from_pylist(rows,schema=schema)


def scan_source(item: dict, *, root: Path=ROOT,
                parquet: bool=False,batch_rows:int=50000,
                limit_rows:int | None=None) -> dict:
    """Streaming source profile and optional atomic typed Parquet staging.

    In QLD unverified-grain inputs, no row count is treated as a vehicle
    count.  Raw extra fields are never serialised in harmonised outputs.
    """
    if batch_rows<1 or (limit_rows is not None and limit_rows<1):
        raise ValueError("batch_rows/limit_rows must be positive")
    p=item["path"]
    spec=item["spec"]
    acquired=item["acquisition"]
    actual_sha=sha256_file(p)
    if actual_sha.lower()!=acquired["sha256"].lower():
        raise ValueError(f"Source SHA drift: {item['source_id']}. Halt before parsing.")
    expected_ext="."+spec["format"]
    if p.suffix.lower()!=expected_ext:
        raise ValueError(f"{p}: wrong extension for declared {spec['format']}")
    filename=re.sub(r"[^a-z0-9_-]","-",item["source_id"].lower())[:100]
    output=root/"data/processed/m12"/spec["kind"]/spec["state"].lower()/f"{filename}--{actual_sha[:12]}.parquet"
    tmp=output.with_name(output.name+".partial")
    writer=None
    buffer=[]
    if parquet:
        import pyarrow.parquet as pq
        schema=_stage_schema()
        output.parent.mkdir(parents=True,exist_ok=True)
        tmp.unlink(missing_ok=True)
    summary={
        "source_id":item["source_id"],"jurisdiction":spec["state"],
        "kind":spec["kind"],"grain":spec["grain"],"source_tier":spec["tier"],
        "reference_date_policy":spec["date_policy"],"publisher_reference":spec["date"],
        "geography_role":spec["geography_role"],"scope":spec["scope"],
        "source_sha256":actual_sha,"source_bytes":p.stat().st_size,
        "source_path":str(p),"manual_acquisition":bool(item["manual"]),
        "license_status":"pending_individual_source_review",
        "source_rows":0,"source_members":0,"numeric_rows":0,
        "censored_rows":0,"unknown_count_rows":0,
        "count_sum_numeric":0,"sum_known_lower_bound":0,
        "sum_known_upper_bound":0,"rows_without_finite_bounds":0,
        "auxiliary_total_rows":0,"schema_review_needed":False,
        "members":[],"observed_dates":{},"raw_header_by_member":{},
        "sample_limit_per_member":limit_rows,
        "bitre_comparability":"not_directly_equivalent_universe_vintage_and_or_geography",
        "cross_month_total_is_not_a_fleet_total":spec["date_policy"]=="zip_member_month",
        "source_class_crosswalk_approved":False,
        "parquet_file":str(output) if parquet else None,
    }
    try:
        if parquet:writer=pq.ParquetWriter(str(tmp),schema=schema,compression="zstd")
        for member,reader,member_date in _iter_source_members(p,spec):
            headers=reader.fieldnames
            if not headers:
                raise ValueError(f"{item['source_id']} / {member} missing physical CSV header")
            if None in headers or len(headers)!=len(set(headers)):
                raise ValueError(f"{item['source_id']} / {member} duplicate/empty headers")
            expected=spec.get("headers")
            if expected is not None and headers!=expected:
                raise ValueError(f"{item['source_id']} / {member}: header drift: {headers} != {expected}")
            summary["source_members"]+=1
            summary["raw_header_by_member"][member]=headers
            summary["schema_review_needed"] |= expected is None
            rows=0
            skipped_aux=0
            for row_no,record in enumerate(reader,1):
                if limit_rows is not None and row_no>limit_rows:
                    break
                if None in record:
                    raise ValueError(f"{item['source_id']} / {member} row {row_no}: unexpected extra columns")
                if any(value is None for value in record.values()):
                    raise ValueError(f"{item['source_id']} / {member} row {row_no}: missing column")
                raw_count=(record.get(spec["measure_col"]) if spec.get("measure_col") else None)
                auxiliary_col=spec.get("auxiliary_total_col")
                if auxiliary_col and not str(raw_count or "").strip() and str(record.get(auxiliary_col) or "").strip():
                    summary["auxiliary_total_rows"]+=1
                    skipped_aux+=1
                    continue
                status=count_token(raw_count,spec.get("measure_col"))
                if spec["date_policy"]=="fixed":
                    obs=spec["date"]
                    precision="date"
                elif spec["date_policy"]=="zip_member_month":
                    if not member_date:
                        raise ValueError(f"{item['source_id']}: no month parsed from {member}")
                    obs=member_date
                    precision="month_end_inferred_from_publisher_filename"
                elif spec["date_policy"]=="column_date":
                    obs=parse_date(record.get(spec["date_col"]))
                    precision="published_row_date" if obs else "unparsed_row_date"
                else:
                    obs=None
                    precision="publisher_year_only_not_assigned_daily_date"
                attribute={
                    field:record.get(physical) for field,physical in spec["fields"].items()
                }
                def clean(field):
                    x=attribute.get(field)
                    return (str(x).strip() or None) if x is not None else None
                location_col=spec.get("geography_col")
                where=(str(record[location_col]).strip() or None) if location_col else None
                summary["source_rows"]+=1
                rows+=1
                if status["count"] is not None:
                    summary["numeric_rows"]+=1
                    summary["count_sum_numeric"]+=status["count"]
                elif status["status"]=="right_censored_published_upper_bound":
                    summary["censored_rows"]+=1
                else:
                    summary["unknown_count_rows"]+=1
                if status["lower"] is None or status["upper"] is None:
                    summary["rows_without_finite_bounds"]+=1
                else:
                    summary["sum_known_lower_bound"]+=status["lower"]
                    summary["sum_known_upper_bound"]+=status["upper"]
                date_key=obs or "DATE_UNKNOWN"
                if date_key not in summary["observed_dates"]:
                    summary["observed_dates"][date_key]={
                        "source_rows":0,"numeric_count_sum":0,
                        "lower_sum_known":0,"upper_sum_known":0,
                        "censored_rows":0,"unknown_rows":0
                    }
                daily=summary["observed_dates"][date_key]
                daily["source_rows"]+=1
                daily["numeric_count_sum"]+=status["count"] or 0
                daily["lower_sum_known"]+=status["lower"] or 0
                daily["upper_sum_known"]+=status["upper"] or 0
                if status["status"]=="right_censored_published_upper_bound":
                    daily["censored_rows"]+=1
                if status["lower"] is None or status["upper"] is None:
                    daily["unknown_rows"]+=1
                if parquet:
                    buffer.append({
                        "source_id":item["source_id"],"source_sha256":actual_sha,
                        "source_member":member,"source_row":row_no,
                        "jurisdiction":spec["state"],"observation_date":obs,
                        "observation_precision":precision,
                        "measure_kind":spec["kind"],"source_grain":spec["grain"],
                        "geography_role":spec["geography_role"],"geography_value":where,
                        "make":clean("make"),"model":clean("model"),
                        "source_vehicle_class":clean("vehicle_type"),
                        "source_manufacture_year":clean("year"),"source_fuel":clean("fuel"),
                        "source_attributes_json":json.dumps(attribute,ensure_ascii=False,sort_keys=True),
                        "count_raw":str(raw_count) if raw_count is not None else None,
                        "published_count":status["count"],
                        "count_lower":status["lower"],"count_upper":status["upper"],
                        "count_status":status["status"],"candidate_bitre_class":None,
                        "bitre_class_mapping_status":"not_mapped_no_approved_source_crosswalk",
                    })
                    if len(buffer)>=batch_rows:
                        writer.write_table(_table(buffer,schema))
                        buffer.clear()
            summary["members"].append({"name":member,"rows":rows,"auxiliary_total_rows_skipped":skipped_aux,
                                       "observation_date":member_date})
        if not summary["source_rows"]:
            raise ValueError(f"{item['source_id']}: no countable/profiled source rows")
        summary["finite_published_sum_bounds"]=summary["rows_without_finite_bounds"]==0
        # Bounds are only for sums over PUBLISHED ROWS. They are not a fleet
        # interval when source coverage/exhaustiveness is unknown.
        summary["bound_interpretation"]="over_published_rows_only_no_exhaustiveness_claim"
        if writer is not None:
            if buffer:writer.write_table(_table(buffer,schema))
            writer.close()
            writer=None
            os.replace(tmp,output)
        return summary
    finally:
        if writer is not None:
            writer.close()
        if parquet:tmp.unlink(missing_ok=True)


def _load_controls(root: Path) -> dict[str,int]:
    path=root/"data/processed/m1/controls/bitre-2026-table1-controls.json"
    if not path.is_file():
        raise FileNotFoundError(
            "M1.1 controls are missing; run: py -3 scripts/m11_reconcile.py")
    book=json.loads(path.read_text(encoding="utf-8"))
    if book.get("national_total")!=22771150 or book.get("reference_date")!=REFERENCE_DATE:
        raise ValueError("BITRE M1.1 workbook controls reference date/national total drift")
    result={}
    for cell in book["controls"]:
        if cell["vehicle_type"]=="Total motor vehicles" and cell["state"]!="AUS":
            result[cell["state"]]=cell["vehicles"]
    if set(result)!=set(STATE_LABEL):
        raise ValueError("M1.1 workbook control missing state totals")
    return result


def compare_vintage(source: dict,controls: dict) -> dict:
    """Deliberately never assert equality between different vintages/scopes."""
    dates=sorted(x for x in source["observed_dates"] if x!="DATE_UNKNOWN")
    classifications={}
    for day in source["observed_dates"]:
        if source["kind"]!="stock":
            status="not_comparable_flow_vs_stock"
        elif day=="DATE_UNKNOWN":
            status="date_unknown_not_comparable"
        elif day!=REFERENCE_DATE:
            status="different_vintage_not_comparable"
        else:
            status="same_date_but_universe_and_class_crosswalk_unverified"
        classifications[day]=status
    return {
        "state":source["jurisdiction"],
        "bitre_reference_date":REFERENCE_DATE,
        "bitre_published_state_registered_motor_vehicle_total":controls[source["jurisdiction"]],
        "state_source_dates":dates,
        "date_and_scope_classification":classifications,
        "direct_count_difference_computed":False,
        "reason":"Different vintages, scopes, aggregation, disclosure, and geographic roles. No automatic stock or flow subtraction.",
    }


def _atomic_json(path: Path,obj: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".partial")
    try:
        temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
                        encoding="utf-8")
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def build_coverage_matrix(report: dict) -> dict:
    """Make every jurisdiction's BITRE baseline and supplemental evidence explicit.

    A missing local source is not a missing national registered-vehicle fleet.
    Requested-but-unavailable and not-requested are different statuses.
    """
    rows=[]
    by_state=defaultdict(list)
    for profile in report["source_profiles"]:
        by_state[profile["jurisdiction"]].append(profile)
    requested=set(report["groups_requested"])
    for state in STATE_LABEL:
        profiles=by_state[state]
        relevant_groups={
            "NSW":{"nsw"},"Vic":{"vic"},"Qld":{"qld","qld_flows"},
            "SA":{"sa","sa_mirror"},"ACT":{"act"},
        }.get(state,set())
        if not relevant_groups:
            status="bitre_only_no_additional_granular_local_source"
        elif not (requested & relevant_groups):
            status="supplemental_sources_not_requested_in_this_run"
        elif not profiles:
            status="supplemental_sources_requested_but_unavailable_or_invalid"
        elif not any(p["kind"]=="stock" for p in profiles):
            status="flow_only_no_supplemental_registration_stock"
        else:
            status="supplemental_publisher_evidence_available_not_bitre_equivalent"
        rows.append({
            "registration_jurisdiction":state,
            "bitre_2026_01_registered_motor_vehicles":report["bitre_state_controls"][state],
            "supplemental_status":status,
            "stock_source_ids":[p["source_id"] for p in profiles if p["kind"]=="stock"],
            "flow_source_ids":[p["source_id"] for p in profiles if p["kind"]=="flow"],
            "source_observation_dates":sorted({
                day for p in profiles for day in p["observed_dates"]
                if day!="DATE_UNKNOWN"
            }),
            "geography_roles":sorted({p["geography_role"] for p in profiles}),
            "observed_input_rows_not_unique_vehicles":sum(p["source_rows"] for p in profiles),
            "approved_bitre_class_crosswalk":False,
            "date_and_scope_comparable_to_bitre":False,
        })
    if sum(r["bitre_2026_01_registered_motor_vehicles"] for r in rows)!=22771150:
        raise ValueError("M1.2 coverage matrix BITRE state totals do not reconcile")
    return {
        "report_version":"0.1.0",
        "national_bitre_registered_motor_vehicles":22771150,
        "observation_date":REFERENCE_DATE,
        "report_is_population_release":False,
        "jurisdictions":rows,
        "interpretation":"Supplemental evidence is a different universe, date, measure, or geography until validated crosswalks and models are approved.",
    }


def run_m12(*,root:Path=ROOT,groups:set[str] | None=None,parquet:bool=False,
            limit_rows:int | None=None,batch_rows:int=50000,
            only_source:str | None=None,fail_on_error:bool=False) -> dict:
    cfg=load_registry(root)
    if groups is None:groups={"vic","nsw","sa","act","qld","qld_flows"}
    unknown=groups-{"vic","nsw","sa","sa_mirror","act","qld","qld_flows"}
    if unknown:
        raise ValueError(f"Unknown state source groups: {sorted(unknown)}")
    controls=_load_controls(root)
    sources,warnings=select_sources(root,cfg,groups)
    if only_source:
        sources=[x for x in sources if only_source in x["source_id"]]
        if not sources:
            raise ValueError(f"No acquired source matching {only_source!r}")
    profiles=[]
    failures=[]
    for idx,item in enumerate(sources,1):
        print(f"[M1.2 {idx}/{len(sources)}] {item['source_id']} ({item['spec']['kind']})",flush=True)
        try:
            info=scan_source(item,root=root,parquet=parquet,batch_rows=batch_rows,
                             limit_rows=limit_rows)
            info["alignment_to_bitre"]=compare_vintage(info,controls)
            profiles.append(info)
            print(f"  rows={info['source_rows']:,} members={info['source_members']} "
                  f"censored={info['censored_rows']:,} unknown={info['unknown_count_rows']:,}",flush=True)
        except (OSError,ValueError,BadZipFile,RuntimeError) as exc:
            failure={"source_id":item["source_id"],"error":f"{type(exc).__name__}: {exc}"}
            failures.append(failure)
            print(f"  ERROR {failure['error']}",flush=True)
    report={
        "pipeline":"m1.2-jurisdiction-evidence-harmonisation",
        "status":"profiled_source_evidence_not_calibrated_population",
        "bitre_reference_date":REFERENCE_DATE,
        "bitre_state_controls":controls,
        "sources_discovered_for_selected_groups":len(sources),
        "source_profiles":profiles,
        "source_failures":failures,
        "notices":warnings,
        "groups_requested":sorted(groups),
        "sampled_partial_run":limit_rows is not None,
        "staged_parquet":parquet,
        "population_release_created":False,
        "official_licences_cleared":False,
        "stock_sources":[p["source_id"] for p in profiles if p["kind"]=="stock"],
        "flow_sources_excluded_from_stock":[p["source_id"] for p in profiles if p["kind"]=="flow"],
        "all_source_rows_processed":sum(x["source_rows"] for x in profiles),
        "states_without_new_granular_files":cfg["missing_jurisdiction_policy"],
        "warnings_policy":"NSW age quarantined, ACT requires manual original source, SA mirror non-additive, QLD 2022 historical; no direct comparison to Jan 2026 BITRE",
    }
    path=root/"data/reports/m12"/("source-profile-sample.json" if limit_rows is not None
                                 else "source-profile.json")
    _atomic_json(path,report)
    coverage=build_coverage_matrix(report)
    coverage_path=root/"data/reports/m12"/(
        "coverage-matrix-sample.json" if limit_rows is not None else "coverage-matrix.json")
    _atomic_json(coverage_path,coverage)
    if fail_on_error and failures:
        raise RuntimeError(f"M1.2 had {len(failures)} source failures; see {path}")
    return report
