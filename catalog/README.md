# Metadata and source catalog

Commit only **public metadata and reviewed source manifests**, never the raw or derived dataset itself. `catalog/sources/` is where per-source inventory entries will live; register actual acquired files and SHA-256 checksums after rights review. The canonical narrative inventory is `docs/data-foundation/source-register.md`.

Source status lifecycle: discovered → approved → ingested, or quarantined. Do not set ingested without hash and profiling evidence. Registry updates create new source release IDs rather than replacing the old ingestion lineage.
