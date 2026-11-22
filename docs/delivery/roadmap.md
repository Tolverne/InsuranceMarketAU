# Delivery roadmap — stage gates, not deadlines

| Milestone | Goal | Exit evidence |
|---|---|---|
| M0 — Architecture & source feasibility | Semantic entities, source register, provenance, machine-readable manifests, security and quality gates | Reviewed specifications, schema examples and contract tests |
| M1 — National vehicle population | Ingest/register official controls and detailed state sources; normalize/synthesize vehicle fleet | Reproducible release, calibration report, geographic/category counts, queryable population |
| M2 — Insurance enrichment | Households, drivers, usage, optional cover and value models | Feature views, uncertainty attribution and independent validity checks |
| M3 — Market intelligence workbench | Segment builder, denominators, addressable market and data-quality views | Transparent segment reports, reproducible filters |
| M4 — Universal participant & model registry | Symmetric group/carrier/brand/product definitions, pluggable models | Batch contract tests and two heterogeneous model adapters |
| M5 — Choice & competitive market | Shopping/renewal events, offer visibility, outside option, retention and brand cannibalisation | Conservation/choice tests; market-share calibration |
| M6 — Claims & financial ledgers | Claim development, premium earning, expenses, reinsurance, group consolidation | Reconciled P&L/cash views and stress validations |
| M7 — Probabilistic scenario engine | Parameter/outcome draws, common random numbers, distributed execution if needed | Distribution plots, scenario deltas, reproducibility/performance tests |
| M8 — Consulting UX & governance | Client projects, secured exports, approvals and reports | Tenant/privacy and reproducibility acceptance tests |
| M9 — Optional production services | Independent model/pricing APIs when justified | Dedicated SLA/security/integration requirements |

## Near-term delivery order

1. M0 review of national vehicle universe: stock vs flow, scope inclusion and jurisdiction gaps.
2. Source feasibility: obtain downloadable samples, verify licences and actual column definitions.
3. Canonical schema smoke-test with at least two *differently grained* sources.
4. First reproducible national population **prototype** with diagnostics; only then select scaling/storage deployment.

Prior prototypes (e.g. other pricing labs) are candidates for reuse after interface and licence review, not prescribed dependencies.

## Research-population hand-off after M1.5

- `M1.3b` remains the default **research** synthesis and `M1.4b` an explicitly unapproved weight-calibrated comparison. Their high-dimensional geographic errors remain an active research question; M1.5 does not certify them.
- `M1.5` publishes content-addressed, locally frozen weighted Parquet release assets with a four-way accounting snapshot, model/source fingerprints, quality report, synthetic sample weight conventions and a verified consumer feature port.
- `M2` starts from `PopulationStore(exact_release_id).iter_feature_view()` and introduces separate, versioned ownership, value, usage, driver and coverage features. Its derived version must include the complete population dependency pin.
- `M3–M7` similarly pin each population and enrichment release plus the required pricing/choice/financial model versions and random stream for reproducibility. Population-model research can progress in parallel without rewriting earlier scenario inputs.

## M2.0 research enrichment foundation

M2.0 establishes a streaming, deterministic **hypothetical insurance-feature** port over the exact M1.5 population release. It includes a typed Arrow feature contract, reproducible assumption digest, population dependency pin, conservative unknown-coverage default and fixture tests. No empirical insurance calibration, household/driver linkage or persisted enrichment release is claimed. See [M2.0 implementation guide](m20-enrichment-foundation.md). M2.1 should tackle source evidence and explicitly conditioned usage/value distributions before adding probabilistic household, driver or insured-market participation models.

## M2.1 model-replacement port and M3 hand-off

M2.1 deliberately prioritises a **replaceable market model architecture** over valuation calibration. `MarketFeatureProvider` exposes the existing typed M2.0 view while delegating vehicle value and usage to independently versioned model adapters. The prototype weighted `summarize()` endpoint gives M3 an initial registered-fleet segment denominator; it must not be interpreted as insured market or policy exposures. Future input evidence can replace the adapters without changing M3–M7 consumers. See [M2.1 architecture and implementation](m21-pluggable-market-features.md).

## M2.2 actor/participation adapter boundary

M2.2 adds a separately replaceable categorical owner/driver/purpose/insurance-participation adapter over the M2.1 feature stream. Defaults are **unknown**; opt-in simulator scenarios produce hypothetical, deterministic assignment only. Its segment report conserves weighted registration mass as insured-scenario + not-insured-scenario + unknown, while forbidding conversion of these figures into observed policy exposure. The full M1.5 + M2.1 + M2.2 selection is pinned. The next structural priority is M3's analyst segment filters, denominator policies and assumption-sensitive market snapshots. See [M2.2 guide](m22-market-actor-ports.md).
