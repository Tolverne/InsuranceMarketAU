# M0 acceptance criteria and open questions

**Status:** design baseline; unchecked items are implementation/review work.

## Architectural acceptance

- [ ] Agree whether scope starts with registered motor vehicles only, with unregistered/laid-up extension separate.
- [ ] Confirm units, grains and inclusion/exclusion criteria for vehicle, household, driver, exposure, policy and insured risk.
- [ ] Approve group/carrier/agent/brand/product hierarchy and symmetric participant rule.
- [ ] Approve model inference and scenario manifest contracts and schema evolution/version pinning.
- [ ] Approve nested uncertainty structure and determinism strategy.
- [ ] Confirm privacy, licensing and publication policy for a public repository.

## Data feasibility

- [ ] Catalogue BITRE and all state/territory registration stock sources, including observation dates and jurisdiction coverage.
- [ ] Catalogue separately transaction/change-of-ownership data, scrappage/vehicle entry, vehicle reference, ABS and insurance financial sources.
- [ ] Test downloads, column definitions, permissible use and refresh cadence rather than relying on dataset landing pages.
- [ ] Specify harmonization of fuel, class, make/model, manufacture year, geographic codes and time axes.
- [ ] Establish hard/soft controls, handling of conflicting marginals and transparent calibration residuals.
- [ ] Define confidence/quality labels and distinguish empirical support from synthetic completions.

## Repository & delivery

- [x] Design documentation, ADRs, source register and contract directory exist.
- [x] Initial manifest schema examples and smoke validator included.
- [ ] End-to-end fixture pipeline from raw sample to canonical and release manifest.
- [ ] Contract CI green on all proposed model/data manifests.
- [ ] M0 specification reviewed and baseline tagged.

## Decisions needed before national M1 ingestion

1. Data rights and redistribution: which sources can be downloaded, cached, transformed and shared?
2. Geographic grain: postcode/state as default reporting vs finer geospatial risk enrichment where lawfully available.
3. Source vintages: common fleet reference date vs per-source temporal adjustment policy.
4. Population method: full simulated vehicle rows + optional weighted sample and ensemble releases.
5. Minimum quality threshold and escalation when published state totals disagree with national controls.
6. First user-facing workflow: market exploration vs API/CLI queries; defer final UI choice.

## M0.1 research checkpoint — 21 November 2026

- [x] Initial nationwide primary-source discovery covering Australia and all eight jurisdictions.
- [x] Identified 17 BITRE January 2026 cross-tab projections plus explanatory notes; catalogued observed dimension combinations.
- [x] Compiled source-date, stock/flow, geographical-role, confidentialisation and legal-access risks.
- [x] Added read-only local CSV/ZIP/XLSX file inspection script and deterministic artificial-data tests.
- [ ] **Acquire and parse real source files:** BITRE XLSX/cross-tab CSV, VIC CSV, SA CSV, NSW ZIP, and relevant others. Portal access was restricted in research runtime; do not upgrade evidence status without actual files.
- [ ] Confirm commercial derivative-use and data-retention terms per source; catalogue licence labels are not formal approval.
- [ ] Inspect detailed BITRE confidentiality rules and set feasible hard/soft control weights.
- [ ] Publish source-level schema profiles, reconciled totals, and a small end-to-end M1 fixture pipeline.

See [M0.1 findings](../data-foundation/feasibility/M0.1-report.md).
