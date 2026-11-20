"""Read-only source probe tests using wholly artificial small files."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import io
from pathlib import Path
from zipfile import ZipFile

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/inspect_source_file.py"
spec = spec_from_file_location("source_inspector", SCRIPT)
assert spec is not None and spec.loader is not None
inspector = module_from_spec(spec)
spec.loader.exec_module(inspector)


def test_csv_header_only_no_raw_row_values(tmp_path: Path) -> None:
    p = tmp_path / "fixture.csv"
    p.write_text("POSTCODE,MAKE,COUNT\n4000,TEST,41\n", encoding="utf-8")
    result = inspector.inspect_file(p)
    assert result["inspection"]["headers"] == ["POSTCODE", "MAKE", "COUNT"]
    assert result["file"]["bytes"] == p.stat().st_size
    assert "4000" not in str(result)
    assert result["source_evidence"] == "FILE_PARSED_LOCAL"


def test_zip_member_headers_without_extraction(tmp_path: Path) -> None:
    p = tmp_path / "fixture.zip"
    with ZipFile(p, "w") as zf:
        zf.writestr("sample.csv", "Year,VehicleClass,Count\n2026,Passenger,12\n")
        zf.writestr("readme.txt", "description only")
    result = inspector.inspect_file(p)
    assert result["inspection"]["members"][0]["headers"] == ["Year", "VehicleClass", "Count"]
    assert not (tmp_path / "sample.csv").exists()


def test_xlsx_workbook_names(tmp_path: Path) -> None:
    p = tmp_path / "fixture.xlsx"
    workbook_xml = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheets><sheet name="Controls" sheetId="1"/></sheets></workbook>'
    )
    with ZipFile(p, "w") as zf:
        zf.writestr("xl/workbook.xml", workbook_xml)
    assert inspector.inspect_file(p)["inspection"]["worksheets"] == ["Controls"]


def test_unsupported_format_rejected(tmp_path: Path) -> None:
    p = tmp_path / "wrong.pdf"
    p.write_bytes(b"%PDF dummy")
    with pytest.raises(ValueError, match="Supported formats"):
        inspector.inspect_file(p)


def test_missing_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        inspector.inspect_file(tmp_path / "missing.csv")
