"""Validate documented contracts and local Markdown references.

Run after: python -m pip install -e ".[dev]"
This validates *metadata structure*, not real data fitness or insurer forecasts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
KINDS = ("source", "population-release", "model", "scenario")


def validate_contracts() -> None:
    for kind in KINDS:
        schema_file = CONTRACTS / "schemas" / f"{kind}-manifest.schema.json"
        example_file = CONTRACTS / "examples" / f"{kind}-manifest.example.json"
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
        example = json.loads(example_file.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(example), key=str)
        if errors:
            raise ValueError(f"{kind}: " + "; ".join(str(e) for e in errors))


LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def validate_local_markdown_links() -> None:
    failures: list[str] = []
    for md in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]:
        for path in LINK.findall(md.read_text(encoding="utf-8")):
            target = path.split("#", 1)[0]
            if not target or target.startswith(("http:", "https:", "mailto:", "/")):
                continue
            if not (md.parent / target).exists():
                failures.append(f"{md.relative_to(ROOT)} -> {path}")
    if failures:
        raise ValueError("Broken local Markdown links:\n" + "\n".join(failures))


if __name__ == "__main__":
    validate_contracts()
    validate_local_markdown_links()
    print("Contract examples and local documentation links validated.")
