# ADR-0003 — Immutable, evidence-linked population releases

- **Status:** Proposed (M0)
- **Context:** Australian sources contain stocks, transactions, aggregated margins and unequal observation dates; missing joint distributions cannot be inferred uniquely.
- **Decision:** Source manifests and checksums precede canonical normalization. Publish immutable reference-date population releases with control totals, quality findings, synthesis lineage, uncertainty/draw IDs, weight conventions and release hash. Never overwrite historic releases.
- **Consequences:** More storage and metadata, but scenario replay and auditability. Registered fleet and non-registered insurable extensions remain separable with explicit scope flags.
- **Review when:** Source licensing conflicts with retention or per-record disclosure; introduce tiered retention/derived-only releases.
