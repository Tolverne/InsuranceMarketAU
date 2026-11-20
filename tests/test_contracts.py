"""M0 schema-contract smoke tests. These fixtures are synthetic metadata only."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("source-manifest", "population-release", "model-manifest", "scenario-manifest")


@pytest.mark.parametrize("kind", KINDS)
def test_manifest_examples_conform(kind: str) -> None:
    schema = json.loads((ROOT / "contracts/schemas" / f"{kind}.schema.json").read_text())
    example = json.loads((ROOT / "contracts/examples" / f"{kind}.example.json").read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(example)


@pytest.mark.parametrize("kind", KINDS)
def test_required_version_cannot_be_omitted(kind: str) -> None:
    schema = json.loads((ROOT / "contracts/schemas" / f"{kind}.schema.json").read_text())
    example = json.loads((ROOT / "contracts/examples" / f"{kind}.example.json").read_text())
    example.pop("schema_version")
    assert not Draft202012Validator(schema).is_valid(example)


def test_ingested_source_requires_real_checksum() -> None:
    schema = json.loads((ROOT / "contracts/schemas/source-manifest.schema.json").read_text())
    example = json.loads((ROOT / "contracts/examples/source-manifest.example.json").read_text())
    example["status"] = "ingested"
    assert not Draft202012Validator(schema).is_valid(example)
