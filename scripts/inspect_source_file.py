#!/usr/bin/env python3
"""Read-only, bounded-format inspection of *locally available* public source files.

Outputs file fingerprint, ZIP member list, CSV/TSV headers, or XLSX worksheet names
and header guesses. Never prints raw records; never downloads or uploads a file.
A file profile is *not* a licence or quality approval. Keep source and profiles
outside the public repository until publication rights and small-cell safety are
reviewed.

Usage:
    python scripts/inspect_source_file.py --file data/raw/bitre_2026.xlsx
    python scripts/inspect_source_file.py --file data/raw/vic.csv --output data/profiles/vic.json
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

MAX_ZIP_ENTRIES = 5000
MAX_HEADER_BYTES = 256 * 1024
MAX_UNCOMPRESSED_MEMBER = 250 * 1024 * 1024


def fingerprint(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def _csv_header_from_bytes(data: bytes) -> dict[str, object]:
    text = data.decode("utf-8-sig", errors="replace")
    first_lines = text.splitlines()[:10]
    if not first_lines:
        return {"headers": [], "delimiter": None}
    try:
        dialect = csv.Sniffer().sniff("\n".join(first_lines), delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    try:
        headers = next(csv.reader(io.StringIO(text), delimiter=delimiter))
    except (StopIteration, csv.Error):
        headers = []
    return {
        "headers": [str(x).strip() for x in headers],
        "delimiter": "\\t" if delimiter == "\t" else delimiter,
        "header_only": True,
    }


def inspect_csv(path: Path) -> dict[str, object]:
    opener = gzip.open if path.name.lower().endswith(".gz") else open
    with opener(path, "rb") as fp:
        data = fp.read(MAX_HEADER_BYTES)
    return {"kind": "csv", **_csv_header_from_bytes(data)}


def inspect_zip(path: Path) -> dict[str, object]:
    members: list[dict[str, object]] = []
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ZIP_ENTRIES:
            raise ValueError(f"ZIP has too many entries: {len(entries)}")
        for entry in entries:
            details: dict[str, object] = {
                "name": entry.filename,
                "compressed_bytes": entry.compress_size,
                "uncompressed_bytes": entry.file_size,
            }
            suffix = entry.filename.lower()
            if (suffix.endswith(".csv") or suffix.endswith(".tsv") or suffix.endswith(".txt")) and entry.file_size <= MAX_UNCOMPRESSED_MEMBER:
                with archive.open(entry) as fp:
                    details.update(_csv_header_from_bytes(fp.read(MAX_HEADER_BYTES)))
            members.append(details)
    return {"kind": "zip", "members": members}


def inspect_xlsx(path: Path) -> dict[str, object]:
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        workbook_name = "xl/workbook.xml"
        if workbook_name not in names:
            raise ValueError("XLSX missing xl/workbook.xml")
        with archive.open(workbook_name) as fp:
            workbook = ET.parse(fp)
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        sheets = [s.attrib["name"] for s in workbook.findall(f".//{ns}sheet")]
        return {"kind": "xlsx", "worksheets": sheets, "note": "Worksheet headers not inferred; inspect workbook layout directly."}


def inspect_file(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    info = fingerprint(path)
    suffix = path.name.lower()
    if suffix.endswith((".csv", ".tsv", ".txt", ".csv.gz", ".tsv.gz")):
        details = inspect_csv(path)
    elif suffix.endswith(".xlsx"):
        details = inspect_xlsx(path)
    elif suffix.endswith(".zip"):
        details = inspect_zip(path)
    else:
        raise ValueError("Supported formats: CSV, TSV, TXT, CSV.GZ, TSV.GZ, XLSX, ZIP")
    return {
        "inspector_version": "0.1.0",
        "file": info,
        "inspection": details,
        "source_evidence": "FILE_PARSED_LOCAL",
        "limitations": [
            "No row-level validity, completeness, total, licensing or confidentialisation checks performed",
            "Headers may contain private/identifying field labels; review before public sharing",
            "CSV/ZIP headers are interpreted as UTF-8; review source encoding",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path, help="Local file; tool never fetches URLs")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON report location (ignored under data/)")
    args = parser.parse_args()
    profile = inspect_file(args.file)
    rendered = json.dumps(profile, indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Source file profile saved to {args.output}")


if __name__ == "__main__":
    main()
