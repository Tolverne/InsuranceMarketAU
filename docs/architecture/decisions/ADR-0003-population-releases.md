# ADR-0003 — Immutable, evidence-linked population releases

- **Status:** Accepted for local M1.5 research release architecture; production governance remains unapproved
- **Context:** Australian sources contain stocks, transactions, aggregated margins and unequal observation dates; missing joint distributions cannot be inferred uniquely.
- **Decision:** Source manifests and checksums precede canonical normalization. Publish immutable reference-date population releases with control totals, quality findings, synthesis lineage, uncertainty/draw IDs, weight conventions and release hash. Never overwrite historic releases.
- **Consequences:** More storage and metadata, but scenario replay and auditability. Registered fleet and non-registered insurable extensions remain separable with explicit scope flags.
- **Review when:** Source licensing conflicts with retention or per-record disclosure; introduce tiered retention/derived-only releases.

- **M1.5 implementation detail:** Use a locally frozen directory and a deterministic SHA-derived release ID; copy both the weighted sample and its original four-way controls, with a source/quality manifest. A verified local `published` status means a frozen reproducible **research asset**, not an approved vehicle census or insurable market. Future pricing/enrichment/scenario runs pin the exact release ID and content SHA.
- **M1.5 trade-off:** Directory discovery rather than a mutable central registry index avoids transactional metadata races in the single-user prototype. SQLite/PostgreSQL metadata indexing and immutable cloud-object retention can be introduced behind the same consumer interface when multiuser concurrency and governance require it.
