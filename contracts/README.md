# Machine-readable interfaces

This directory carries proposed JSON Schema 2020-12 manifests and valid **illustrative** examples, not published datasets or executable pricing models.

- `schemas/source-manifest.schema.json`: discovery/ingestion metadata with stock/flow separation.
- `schemas/population-release.schema.json`: immutable population and quality release metadata.
- `schemas/model-manifest.schema.json`: algorithm-independent model binding and typed input/output contract.
- `schemas/scenario-manifest.schema.json`: pinned marketplace experiment with separate assumption/outcome draws.
- `examples/`: contract fixtures using deliberately non-existent `example://` assets.

**Scope:** metadata/control contracts only. Physical Arrow/Parquet feature/event schemas will be designed using verified source samples and recorded here in future milestones. The validator checks schema validity and examples; it does not prove statistical calibration.

Run `python -m pip install -e ".[dev]"` then `python scripts/validate_repository.py` and `pytest`.
