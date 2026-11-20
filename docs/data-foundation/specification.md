# Australian Motor Insurance Market Data Foundation Specification

**Document ID:** DF-001  
**Version/status:** v0.1 proposed design, 2026-11-21  
**Scope:** national market data foundation and interfaces required by downstream market, insurance and financial simulations. **This document is not a statement that any sources have been downloaded or calibrated.**

## 1. Purpose and acceptance outcome

The foundation will publish **immutable, queryable, statistically credible Australian vehicle populations** for a given reference date, with explicit coverage of the registered fleet and separately estimated otherwise-insurable vehicles. Each release will support (a) national/state/postcode market analysis, (b) optional linking of synthetic owner/driver/use/insurance features, (c) weighted simulation subsets and (d) reproducible alternative synthetic draws reflecting unresolved uncertainty.

**Design requirements:**

| ID | Requirement | M0/M1 verification |
|---|---|---|
| DF-01 | Every source has documented grain, provenance, date, licence, geography and controls | Manifest completeness validator |
| DF-02 | Stock and flow observations are physically and semantically distinct | Schema and reconciliation tests |
| DF-03 | Canonical vehicle, location, time and classification keys are versioned | Schema/foreign-key tests |
| DF-04 | Source vintage differences are transparent and adjustable | Reconciliation report |
| DF-05 | National and state controls are reconciled and deviations reported | Hard/soft constraint diagnostics |
| DF-06 | Unknown joint distributions are statistically synthesized, not silently claimed observed | Method/model lineage and uncertainty draw |
| DF-07 | Full-population and weighted-sample exports share denominator semantics | Weighted-total parity tests |
| DF-08 | Every release has stable immutable identifiers/checksums and source dependency hashes | Rebuild/replay test |
| DF-09 | Multiple plausible population draws can be sampled for sensitivity analysis | Ensemble variance tests |
| DF-10 | Feature views are versioned with null/unknown imputation and coverage semantics | Consumer contract tests |
| DF-11 | Accessible published outputs do not expose identifiable owner/vehicle records | Privacy and small-cell review |
| DF-12 | New source releases trigger explicit, testable refresh plans; historic versions stay available | Incremental rebuild comparison |

## 2. Defined populations and denominators

Do **not** conflate the following:

- **Registered stock:** motor vehicles satisfying the official registration definition at a specified observation date. BITRE's January 2026 release covers unrestricted road-use vehicles reported via NEVDIS. Jurisdictional sources may differ in seasonal/restricted/trailer exclusions.
- **Insurable vehicle universe:** registered stock plus separately modelled unregistered, laid-up, historic, stored or other eligible assets; not all such assets are necessarily offered optional property insurance.
- **Addressable eligible risk:** vehicles meeting a particular product's target/underwriting criteria at a time and for a coverage definition.
- **Potential insured exposure:** time-weighted vehicle-cover units capable of carrying a specific insurance risk.
- **Policy:** contract (possibly covering multiple vehicles/risks). Count policies, vehicles, customers, exposures and premiums separately.
- **Household/business:** owner/keeper or customer economic unit; not automatically equivalent to driver or policyholder.
- **Shopping event:** customer consideration/quote event; not synonymous with a transaction or an insurance purchase.

### Inclusion and exclusions (initial proposal)

Start with passenger, light commercial, motorcycles and heavy/commercial road vehicles in a common fleet dictionary, using official control categories. Trailers, caravans and specialist equipment require explicit classification: they may be included in the broader insurable asset universe but not silently in a motor-car denominator. Maintain **scope flags** for registered-unrestricted, registered-restricted, off-road/unregistered, seasonal, commercial and product class. CTP is out of scope for the first optional-property market simulator but should have its own future line-of-business module. A vehicle without optional cover remains in the fleet with the appropriate insurance status.

## 3. Source inventory and feasibility

See [source-register.md](source-register.md), with verified **landing pages** for BITRE, Victoria, Queensland, ABS and APRA. M0 research is not the same as having inspected source files and licences for each usage. Each source is typed as `stock`, `flow`, `joint_aggregate`, `marginal`, `reference`, `survey`, or `insurance_benchmark`.

**At a minimum source manifests include:** publisher, URL/resource ID, observed reference period, published date, acquired date, schema version, original format, row granularity, geography and classifications, record-count field, coverage, exclusions, permitted uses/licence, checksum, owner, refresh cadence and quality alerts.

### Source priority and conflicts

1. Use a consistent national **reference date** and published BITRE state/category control totals as a first national benchmark.
2. For attributes, prefer high-resolution recent **joint tabulations** whose grain is genuinely known, e.g. Victorian state/postcode/make/year/fuel/class aggregates.
3. Use individual-like Queensland October 2022 extract as historical reference only, not a national 2026 stock.
4. Use new registrations/transfers, approvals and other changes as **flows**, never directly add them to a stock without entry/exit accounting.
5. Use ABS demographic distributions for household/owner assignments only after resolving date, geography, population and conditional-correlation mismatch.
6. Use APRA class-of-business financials for aggregate external calibration where definitions match; they are **not** vehicle microdata or a source of competitor-specific GLM relativities.

Define which controls are **hard** (published counts within allowed rounding) and which are **soft** (dated, partial, uncertain or incompatible definitions). Hard constraints must not be combined when mathematically inconsistent. Produce residuals and a reviewer decision on discrepancies rather than hiding one.

## 4. Canonical architecture and grains

See [canonical-data-model.md](canonical-data-model.md). Model a vehicle **specification** separately from a synthetic **instance** and its dated **fleet state**. Keep geographic reference tables (state, postcode, SA2 where permitted), vehicle classification dictionaries, stock observation cells and transaction flows separate from generated members. Synthetic household/driver/insurance fields are optional enrichment extensions, not guaranteed observed vehicle properties.

Use immutable internal surrogate keys (e.g. `vehicle_id`, `vehicle_spec_id`, `release_id`) and explicit source-specific identifiers in controlled lineage tables. Do not publish VIN, plate or any source identifier that could facilitate reidentification. Synthetic IDs are stable **within one release**; cross-release continuity is a separately modelled lineage problem and should not be presumed.

Represent observation time, validity time, ingestion time and publication/release time separately. A date of arrival is not the fleet observation date.

## 5. Raw-to-release pipeline

```text
Source registration + rights review
  -> immutable raw acquisition (outside Git; checksum)
  -> staging profile (schema, records, nulls, distributions)
  -> canonical map (classifications, geographic crosswalks, time)
  -> control reconciliation (national/state/other margins)
  -> conditional population reconstruction (multiple draws)
  -> constraint enforcement + holdout validation
  -> synthetic vehicle-level release and optional weighted sample
  -> query views, statistics, lineage and immutable manifest
```

### 5.1 Acquiring and profiling

Source adapters should provide metadata-first discovery and retrieval. Capture HTTP/version metadata or manual download references where automated APIs are unavailable. Repeated ingestion of identical bytes must be idempotent. Store source payloads under access-controlled, content-addressed locations; protect proprietary inputs and retain licence/retention decision.

Profiling reports should cover null rate, data types, cardinality, invalid postcode/state combinations, category drift, duplicate observation keys, counts by unit, outliers (future manufacture year, implausible ages), and observed dates.

### 5.2 Harmonization

Maintain separately versioned reference mappings for vehicle class, make/model, fuel, year, body, state and postcode. Never overwrite original codes; retain `raw_value`, `canonical_value`, `mapping_version` and ambiguity. For geography, keep a point-in-time postcode/state crosswalk and unknown/ambiguous category: postcode boundaries do not perfectly align with SA2 or state for every dataset. Unknown, suppressed and not-applicable are distinct from zero.

### 5.3 Time alignment and accounting

Choose a release reference date (example 2026-01-31); source data may reference October 2022, Q3 2026 or the 2021 Census. A source-date mismatch is not fixed by silently relabelling records. When a temporal adjustment model exists, record its data, assumptions, error and model version. For stock changes, use a reconciled identity such as

\[
N_{t+1} = N_t + E_{t,t+1} - X_{t,t+1} + A_{t,t+1},
\]

where `E` and `X` represent correctly classified entries/exits and `A` documented scope/reclassification adjustments. **Ownership transfers do not normally change the total fleet stock** and must not be counted as entries. Historic extracts can inform conditional attributes but never establish current totals alone.

### 5.4 Population reconstruction

We should begin with a transparent benchmark pipeline rather than a black-box generative model:

1. Build control tables for jurisdiction/category/year/fuel and reliable observed cross-tabs.
2. Define a hierarchy of conditional distributions; identify pairs or higher-order relationships supported by observed joint tables.
3. Generate an initial categorical population from empirical joint cells where available; infer unsupported cells with smoothed/hierarchical models and assumptions.
4. Calibrate weights or counts to consistent marginals using iterative proportional fitting/raking or constrained optimization; respect structural zeros and integer counts.
5. Generate vehicle instances or a weighted sample, then sample residual continuous variables conditionally, with explicit methods and bounds.
6. Evaluate on *held-out* combinations or geographies not used as hard constraints. Report how much the synthetic population actually predicts rather than merely reproducing fitted margins.
7. Repeat with plausible parameter draws (not just changing RNG) to form a population ensemble.

Candidate methods include statistical matching, Bayesian hierarchical models, raking, copulas and conditional generative methods, but select them via evidence and testable calibration. If the data do not identify a joint relationship, keep that uncertainty visible and avoid fictitious microdata precision. Incorporate dependent household/vehicle assignment in M2, not necessarily in the M1 vehicle-only release.

### 5.5 Sampling strategy

Create a full synthetic vehicle-level population where feasible and a weighted analysis/simulation sample. If a sample row represents `w_i` fleet vehicles, its weighted sum must reproduce control denominators. The choice of design/sampling weights and probability of inclusion must be documented; do not treat weighted sampled rows as independent claims exposures without an appropriate simulation scheme. Scenario engine should be able to request a full cohort or a representative view with known stratification and design effect.

### 5.6 Release process

Publish to immutable URI/prefix such as `population/releases/<release_id>/` outside Git. A release has manifest, content hash, source dependencies, data dictionary version, population definition, geography codes, reference date, synthesis model and assumptions, PRNG identifier/seed, uncertainty draw ID, counts/weights, validation report and warnings. A source update creates a **new** release even if only some partitions change. Historical experiments pin a release hash; do not silently redirect `latest`.

## 6. Storage and query design

**Provisional:** source files in immutable object/file storage; canonical tables and generated populations as compressed Parquet with an Arrow schema registry; metadata/manifests JSON; query via DuckDB/Polars or equivalent. Avoid one huge table: use normalised master/reference tables and materialized feature views. Partition for scan pattern (release, geography, period) while avoiding too many tiny postcode files. Dataset rights may force private segregated storage or derived-only exports.

**Performance criteria:** benchmark an initial state-scale sample, then national 20m+ vehicle scale; profile RAM, CPU, disk, range filters and group-by operations. Do not make hard throughput or cloud-cost promises before this benchmark. Store high-cardinality strings via categorical codes/dictionaries where beneficial; reject schemas that require unbounded Python object columns for batch simulation.

## 7. Interfaces to downstream models

Provide a `PopulationRelease` reader that resolves a version and exposes `FleetState`, `VehicleSpecification`, geography keys, population weights and optional enriched feature views. Consumers ask for a **versioned feature contract** with documented null handling rather than directly depending on original state CSV columns. A model can require observed or imputed features, but must declare missing-feature behaviour; a sample quote cannot silently substitute state mean mileage unless that policy is pinned.

Data foundation does **not** contain a special startup-company row, competitor-specific premium, or a canonical pricing algorithm. These belong in separately versioned participant/model/scenario contexts.

## 8. Quality gates and publication rules

See [provenance-and-quality.md](provenance-and-quality.md). Block release on manifest incompleteness, invalid schema/weights, negative counts, duplicate keys, missing hard controls, broken source/lineage hashes, forbidden licence use, or irreconcilable hard constraints. Permit release with warnings on soft-control residuals only when quantified and approved. Report distributions for postcode/class/year/fuel and aggregate uncertainty; emit quality dashboards and downloadable validation artifacts.

## 9. Open design questions

- Which classes and niche unregistered populations belong in first release? Where is their independent control data?
- Do we target a full population for every uncertainty draw or a common base with parameter/weight variants?
- What postcode/state and year resolution is credible when one state has only marginals?
- Which synthetic variables are materially important to insurance pricing, demand and catastrophe accumulation?
- How do we measure calibrated uncertainty where published aggregates cannot identify a distribution?
- What data redistribution and derivative works are permitted for each source?
- When should an insurer's private portfolio calibrate the public national foundation vs live in a tenant-private overlay?

## 10. Deliverables

**M0:** this specification; entity dictionary; source register; provenance policy; manifest schemas/examples; deterministic checks; architecture/decision review.  
**M1:** verified source files; staging profiles; canonical normalized tables; full and weighted first fleet releases; source-control residuals; uncertainty experiments; repeatable build instructions and acceptance report.  
**M2:** household, driver, usage, optional cover and value feature views, demand/insurance benchmark constraints and uncertainty evaluation.
