"""Verify immutable, metadata-only BITRE acquisition evidence."""
import json
from pathlib import Path


def test_verified_bitre_download_inventory() -> None:
    root = Path(__file__).resolve().parents[1]
    d = json.loads((root / "catalog/acquisition/bitre-2026-acquired-metadata.json").read_text())
    assert d["number_of_csvs"] == 17
    assert d["number_of_notes_files"] == 1
    assert len(d["resources"]) == 18
    assert sum(x["bytes"] for x in d["resources"]) == d["total_bytes"]
    assert {x["projection_id"] for x in d["resources"]} == {
        *{f"B26-{i:02d}" for i in range(1, 18)}, "B26-EXPL"
    }
    assert all(len(x["sha256"]) == 64 for x in d["resources"])
    assert all(x["bytes"] > 0 for x in d["resources"])
    assert d["source_rights_status"] == "publisher_license_review_not_completed"
