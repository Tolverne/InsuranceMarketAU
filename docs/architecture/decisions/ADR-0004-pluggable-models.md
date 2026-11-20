# ADR-0004 — Typed, model-agnostic execution ports

- **Status:** Proposed (M0)
- **Context:** Competitor quote models may be GLMs, GBMs, rating tables, ensembles or external APIs and may change as new evidence arrives.
- **Decision:** Use versioned feature and output schemas and a \`ModelRunner\` batch adapter contract. Keep target-market rules, underwriting eligibility, pricing output and consumer choice separate. Pin each run to a concrete model artefact hash/version.
- **Consequences:** Algorithm independence and replay; requires missing-feature policy, unit/currency semantics, timeout/error behaviour, effective-date handling and parity tests. External API responses need replay snapshots if historical determinism is required.
- **Review when:** Production-grade online pricing demands latency/SLA, model governance or compliance requirements beyond batch consulting simulation.
