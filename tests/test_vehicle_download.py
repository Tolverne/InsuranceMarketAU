"""No-network tests for the official-source acquisition client."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import hashlib
import json
from pathlib import Path

import pytest

FILE = Path(__file__).resolve().parents[1] / "scripts/download_vehicle_sources.py"
SPEC = spec_from_file_location("vehicle_downloader", FILE)
assert SPEC and SPEC.loader
mod = module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_catalogue_coverage() -> None:
    config = json.loads(mod.CATALOGUE.read_text())
    assert len(config["static_resources"]) == 10
    assert {x["group"] for x in config["ckan_datasets"]} == {
        "bitre", "sa", "qld", "qld_flows"
    }
    assert all(mod.accepted_url(x["url"], allow_mirror=x["group"] == "sa_mirror") for x in config["static_resources"])


def test_ckan_endpoint_escapes_parameter() -> None:
    assert mod.ckan_endpoint("https://data.gov.au/data/api/3/action", "id a").endswith(
        "/package_show?id=id+a"
    )


def test_source_url_host_protection() -> None:
    assert mod.accepted_url("https://data.gov.au/resource.csv")
    assert mod.accepted_url("https://opendata.transport.vic.gov.au/data.csv")
    assert mod.accepted_url("https://publicdata.au/file.csv", allow_mirror=True)
    assert not mod.accepted_url("https://publicdata.au/file.csv")
    assert not mod.accepted_url("http://data.gov.au/file.csv")
    assert not mod.accepted_url("https://data.gov.au.example.net/resource.csv")
    assert not mod.accepted_url("https://evil.gov.au.example.com/file.csv")


def test_offline_static_discovery_no_network(monkeypatch) -> None:
    def reject(*args, **kwargs):
        raise AssertionError("Network should not be accessed")
    monkeypatch.setattr(mod, "read_url", reject)
    config = json.loads(mod.CATALOGUE.read_text())
    resources, errors = mod.discover_all(config, {"bitre", "nsw"}, timeout=1, static_only=True)
    assert len(resources) == 6
    assert not errors


def test_ckan_discovers_2026_resources_and_ignores_html(monkeypatch) -> None:
    payload = {
        "success": True,
        "result": {
            "license_title": "CC BY",
            "resources": [
                {"name": "Registered road vehicles January 2026", "id": "one",
                 "format": "CSV", "url": "https://data.gov.au/dataset/r1.csv"},
                {"name": "Earlier snapshot 2025", "id": "two",
                 "format": "CSV", "url": "https://data.gov.au/dataset/r2.csv"},
                {"name": "Web landing 2026", "id": "three",
                 "format": "HTML", "url": "https://data.gov.au/landing"},
            ],
        },
    }
    monkeypatch.setattr(mod, "read_url", lambda *a, **kw: json.dumps(payload).encode())
    entry = {"api_base": "https://data.gov.au/data/api/3/action", "dataset": "d1",
             "id": "bitre", "group": "bitre", "reference_date": "2026-01-31",
             "kind": "stock", "filter_year": "2026"}
    resources = mod.discover_ckan(entry, timeout=1)
    assert len(resources) == 1
    assert resources[0]["resource_id"] == "one"
    assert resources[0]["licence_status"] == "pending_review"


class FakeResponse:
    def __init__(self, data: bytes, url: str):
        self._data = data
        self._pos = 0
        self._url = url
        self.headers = {"Content-Length": str(len(data)), "Content-Type": "text/csv"}
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def geturl(self):
        return self._url

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._data) - self._pos
        result = self._data[self._pos:self._pos + size]
        self._pos += len(result)
        return result


def sample_resource():
    return {"id": "test-resource", "group": "vic", "reference_date": "2026-09-30",
            "title": "Synthetic test", "kind": "stock", "format": "csv",
            "url": "https://opendata.transport.vic.gov.au/sample.csv"}


def test_content_addressed_download_idempotent(monkeypatch, tmp_path: Path) -> None:
    data = b"Year,Count\n2026,42\n"
    resource = sample_resource()
    monkeypatch.setattr(mod, "urlopen",
                        lambda *a, **kw: FakeResponse(data, resource["url"]))
    first = mod.download_resource(resource, tmp_path / "output", timeout=1, max_bytes=500)
    second = mod.download_resource(resource, tmp_path / "output", timeout=1, max_bytes=500)
    assert first["sha256"] == hashlib.sha256(data).hexdigest()
    assert first["path"] == second["path"]
    assert len(list((tmp_path / "output").rglob("*.csv"))) == 1
    assert not list((tmp_path / "output").rglob("*.part"))


def test_reject_html_masquerading_as_csv(monkeypatch, tmp_path: Path) -> None:
    resource = sample_resource()
    monkeypatch.setattr(
        mod, "urlopen",
        lambda *a, **kw: FakeResponse(b"<html>Access denied</html>", resource["url"]),
    )
    with pytest.raises(RuntimeError, match="HTML"):
        mod.download_resource(resource, tmp_path / "out", timeout=1, max_bytes=100)
    assert not list((tmp_path / "out").rglob("*.csv"))
