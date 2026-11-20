#!/usr/bin/env python3
"""Download and fingerprint official Australian vehicle datasets.

Examples:
  python scripts/download_vehicle_sources.py --groups bitre,vic --list
  python scripts/download_vehicle_sources.py --groups bitre,vic,nsw,sa,act --download
  python scripts/download_vehicle_sources.py --groups qld --download --max-file-mb 1000

Raw data goes to git-ignored data/raw/, and private acquisition reports to
data/reports/. The script never commits data or approves a source licence.
Uses only Python standard library; requires public internet access.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "catalog/acquisition/download-sources.json"
CHUNK = 1024 * 1024
SAFE_FORMATS = {"csv", "tsv", "txt", "pdf", "zip", "xlsx", "xls"}
USER_AGENT = "InsuranceMarketAU-research/0.1 (public government open-data acquisition)"
REGISTRY_GROUPS = {"bitre", "vic", "nsw", "sa", "act", "qld", "qld_flows"}


def slug(value: str, limit: int = 65) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return clean[:limit].rstrip("-") or "resource"


def accepted_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and (host.endswith(".gov.au") or host == "gov.au")
    except (TypeError, ValueError):
        return False


def ckan_endpoint(base: str, dataset: str) -> str:
    return base.rstrip("/") + "/package_show?" + urlencode({"id": dataset})


def read_url(url: str, timeout: int, max_bytes: int) -> bytes:
    if not accepted_url(url):
        raise ValueError(f"Refusing non-government/non-HTTPS source: {url}")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    with urlopen(request, timeout=timeout) as response:
        if not accepted_url(response.geturl()):
            raise ValueError(f"Refusing redirect outside government HTTPS hosts: {response.geturl()}")
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Metadata response exceeds size limit")
        return data


def resource_extension(resource: dict) -> str | None:
    fmt = str(resource.get("format") or "").lower().strip(". ")
    url = urlparse(str(resource.get("url", ""))).path.lower()
    for ext in ("csv.gz", "xlsx", "csv", "tsv", "txt", "pdf", "zip", "xls"):
        if url.endswith("." + ext):
            return ext
    if fmt in SAFE_FORMATS:
        return fmt
    if fmt in {"excel", "spreadsheet"}:
        return "xlsx"
    return None


def discover_ckan(entry: dict, timeout: int) -> list[dict]:
    url = ckan_endpoint(entry["api_base"], entry["dataset"])
    body = json.loads(read_url(url, timeout=timeout, max_bytes=16 * 1024 * 1024))
    if body.get("success") is not True or not isinstance(body.get("result"), dict):
        raise ValueError(f"CKAN dataset returned unsuccessful response: {entry['id']}")
    dataset = body["result"]
    resources = dataset.get("resources", [])
    if len(resources) > entry.get("max_resources", 250):
        raise ValueError(f"Unexpectedly large source resource list: {len(resources)}")
    accepted = []
    for item in resources:
        title = str(item.get("name") or item.get("description") or item.get("id") or "")
        link = str(item.get("url") or "")
        ext = resource_extension(item)
        if not ext or ext not in SAFE_FORMATS:
            continue
        year = entry.get("filter_year")
        if year and str(year) not in (title + " " + link):
            continue
        accepted.append({
            "id": entry["id"] + "__" + slug(str(item.get("id") or title), 42),
            "group": entry["group"],
            "reference_date": entry["reference_date"],
            "title": title,
            "url": link,
            "format": ext,
            "kind": entry["kind"],
            "source": "ckan_discovered",
            "resource_id": item.get("id"),
            "dataset_id": entry["dataset"],
            "catalogue_url": url,
            "licence_label": str(dataset.get("license_title") or dataset.get("license_id") or "unknown"),
            "licence_status": "pending_review",
        })
    if not accepted:
        raise ValueError(f"No matching downloadable resources in {entry['id']} (check metadata/year filters)")
    return accepted


def discover_all(config: dict, groups: set[str], timeout: int,
                 static_only: bool = False) -> tuple[list[dict], list[dict]]:
    sources = [dict(x) for x in config["static_resources"] if x["group"] in groups]
    errors = []
    if not static_only:
        for entry in config["ckan_datasets"]:
            if entry["group"] not in groups:
                continue
            try:
                sources.extend(discover_ckan(entry, timeout))
            except (ValueError, HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                errors.append({"dataset": entry["id"], "error": f"{type(exc).__name__}: {exc}",
                               "catalogue_url": ckan_endpoint(entry["api_base"], entry["dataset"])})
    ids = [x["id"] for x in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("Non-unique source ids in combined catalogue")
    return sources, errors


def file_signature_ok(path: Path, ext: str) -> None:
    with path.open("rb") as fp:
        magic = fp.read(1024).lstrip()
    if not magic:
        raise ValueError("Empty data resource")
    if magic[:128].lower().startswith((b"<html", b"<!doctype html", b"<?xml version=\"1.0\"?><html")):
        raise ValueError("Received HTML rather than a downloadable dataset")
    if ext == "zip" and not magic.startswith(b"PK"):
        raise ValueError("ZIP extension but response is not a ZIP file")
    if ext == "xlsx" and not magic.startswith(b"PK"):
        raise ValueError("XLSX extension but response is not a ZIP-based workbook")
    if ext == "pdf" and not magic.startswith(b"%PDF"):
        raise ValueError("PDF extension but response is not a PDF")


def download_resource(resource: dict, output: Path, timeout: int, max_bytes: int,
                      tries: int = 3) -> dict:
    url = resource["url"]
    if not accepted_url(url):
        raise ValueError(f"Refusing URL: {url} (require official gov.au HTTPS host)")
    ext = resource["format"].lower()
    if ext not in SAFE_FORMATS:
        raise ValueError(f"Not an approved file extension: {ext}")
    folder = output / resource["group"] / slug(str(resource["reference_date"]))
    folder.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(tries):
        tmp = None
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with urlopen(request, timeout=timeout) as response:
                final_url = response.geturl()
                if not accepted_url(final_url):
                    raise ValueError(f"Redirect outside approved HTTPS government hosts: {final_url}")
                length = response.headers.get("Content-Length")
                if length and int(length) > max_bytes:
                    raise ValueError(f"Resource too large ({length} bytes); increase --max-file-mb")
                typ = response.headers.get("Content-Type", "").lower()
                if "text/html" in typ:
                    raise ValueError(f"HTML response instead of data, HTTP {response.status}")
                digest = hashlib.sha256()
                total = 0
                with tempfile.NamedTemporaryFile(mode="wb", dir=folder, prefix=".downloading-", suffix=".part",
                                                  delete=False) as fp:
                    tmp = Path(fp.name)
                    while True:
                        chunk = response.read(CHUNK)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValueError("Resource exceeds configured max file size")
                        fp.write(chunk)
                        digest.update(chunk)
            file_signature_ok(tmp, ext)
            checksum = digest.hexdigest()
            name = slug(resource["id"], 55) + "--" + checksum[:12] + "." + ext
            final = folder / name
            if final.exists():
                tmp.unlink(missing_ok=True)
            else:
                os.replace(tmp, final)  # Atomic, hash-named immutable asset
            return {
                "status": "downloaded", "path": str(final.relative_to(ROOT)) if final.is_relative_to(ROOT) else str(final),
                "sha256": checksum, "bytes": total, "url": url, "resolved_url": final_url,
                "source_id": resource["id"], "group": resource["group"],
                "reference_date": resource["reference_date"], "kind": resource["kind"],
                "licence_status": "pending_review",
            }
        except (HTTPError, URLError, OSError, ValueError, TimeoutError) as exc:
            last_error = exc
            if tmp is not None:
                tmp.unlink(missing_ok=True)
            if attempt + 1 < tries and not isinstance(exc, ValueError):
                time.sleep(min(2 ** attempt, 5))
                continue
            break
    raise RuntimeError(f"Download failed for {resource['id']}: {type(last_error).__name__}: {last_error}")


def acquisition(args: argparse.Namespace) -> dict:
    config = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    groups = set(x.strip() for x in args.groups.split(",") if x.strip())
    unknown = groups - REGISTRY_GROUPS
    if unknown:
        raise ValueError(f"Unknown groups: {sorted(unknown)}")
    sources, discovery_errors = discover_all(config, groups, args.timeout, args.static_only)
    if args.only:
        sources = [x for x in sources if args.only in x["id"]]
    report = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "download" if args.download else "list_only",
        "groups": sorted(groups),
        "catalogue_version": config["catalog_version"],
        "raw_data_in_git": False,
        "licence_status": "not_cleared_by_this_tool",
        "discovered": len(sources),
        "discovery_errors": discovery_errors,
        "resources": [],
    }
    for i, source in enumerate(sources, 1):
        print(f"[{i}/{len(sources)}] {source['group']}: {source['title']} [{source['format']}]")
        row = {
            "id": source["id"], "group": source["group"], "title": source["title"],
            "url": source["url"], "reference_date": source["reference_date"],
            "kind": source["kind"], "status": "listed",
            "licence_label": source.get("licence_label"),
            "licence_status": "pending_review",
        }
        if args.download:
            try:
                row.update(download_resource(source, args.destination, args.timeout,
                                             max_bytes=args.max_file_mb * 1024 * 1024))
                # Header/source profiling is optional; a profile error never erases original bytes.
                try:
                    from inspect_source_file import inspect_file
                    p = Path(row["path"])
                    if not p.is_absolute():
                        p = ROOT / p
                    if p.suffix.lower() in {".csv", ".zip", ".xlsx", ".tsv", ".txt"}:
                        profile = inspect_file(p)
                        row["inspection"] = profile["inspection"]
                except (ImportError, OSError, ValueError) as exc:
                    row["inspection_error"] = f"{type(exc).__name__}: {exc}"
            except RuntimeError as exc:
                row.update(status="failed", error=str(exc))
                print(f"  ERROR: {exc}", file=sys.stderr)
        report["resources"].append(row)
    report["downloaded_count"] = sum(x["status"] == "downloaded" for x in report["resources"])
    report["failed_count"] = sum(x["status"] == "failed" for x in report["resources"])
    report["unresolved_count"] = len(discovery_errors) + report["failed_count"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groups", default="bitre,vic,nsw,sa,act",
                        help="Comma-separated groups: bitre,vic,nsw,sa,act,qld,qld_flows")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="Discover URLs, do not download")
    mode.add_argument("--download", action="store_true", help="Download full resource bytes locally")
    parser.add_argument("--static-only", action="store_true", help="Skip CKAN API discovery (offline test)")
    parser.add_argument("--only", help="Optional substring of resource ID for selecting one resource")
    parser.add_argument("--destination", type=Path, default=ROOT / "data/raw",
                        help="Raw data root; default git-ignored data/raw")
    parser.add_argument("--report", type=Path, help="JSON run manifest; default data/reports/<UTC>.json")
    parser.add_argument("--timeout", type=int, default=90, help="Per-network-operation timeout")
    parser.add_argument("--max-file-mb", type=int, default=2048, help="Individual source file size cap")
    args = parser.parse_args()
    args.destination = args.destination.resolve()
    report = acquisition(args)
    default = ROOT / "data/reports" / ("acquisition-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    out = args.report or default
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nReport: {out}")
    print(f"Listed {report['discovered']}, downloaded {report['downloaded_count']}, unresolved {report['unresolved_count']}")
    if report["unresolved_count"]:
        print("WARNING: Some sources were not available. Check report before assuming completeness.", file=sys.stderr)
    return 1 if report["unresolved_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
