# InsuranceMarketAU

**Australian Motor Insurance Market Data Foundation & Competitive Simulation Platform**

A consulting-first, evidence-led platform for constructing a versioned Australian vehicle and insurance market, modelling any number of insurers/brands/products with interchangeable models, and running reproducible probabilistic market and financial scenarios.

> **Status:** M0 architecture, M1.0–M1.5 synthetic-population research workflows and the M2.0 hypothetical enrichment feature port are implemented. Frozen **research-only** weighted population releases and local Streamlit exploration are available. No commercial population validation, policyholder data, production dataset or validated market forecast is implied.

## Principles

1. **One shared market, symmetric participants.** A client, a startup and every competitor are configured using the same insurer/carrier/brand/product entities.
2. **Observed evidence before synthesis.** Preserve the original source, dates, grain, licence and limitations; do not turn hypothetical detail into observed fact.
3. **Models are replaceable.** Underwriting, pricing, choice, risk, expenses and financial adapters expose contracts independent of GLM/GBM/API implementations.
4. **Reproducible uncertainty.** Immutable population and model versions, explicit assumptions, common random numbers and separated parameter/outcome uncertainty.
5. **Consulting-first, not vendor-locked.** Prefer portable data formats and local-first research; choose cloud and service frameworks on evidence.
6. **Data safety.** No raw proprietary datasets, personal records, credentials or large generated populations in Git.

## Start here

- [Architecture & component boundaries](docs/architecture/system-architecture.md)
- [Full data foundation technical specification](docs/data-foundation/specification.md)
- [Canonical entity and feature model](docs/data-foundation/canonical-data-model.md)
- [Data-source register](docs/data-foundation/source-register.md)
- [Marketplace & scenario simulation](docs/simulation/marketplace-and-financial-architecture.md)
- [M0 acceptance criteria](docs/delivery/m0-acceptance.md)
- [Delivery roadmap](docs/delivery/roadmap.md)
- [Architecture decision records](docs/architecture/decisions/README.md)
- [Machine-readable contracts](contracts/README.md)

## Repository layout

| Directory | Purpose |
|---|---|
| `docs/` | Versioned design, data methodology, ADRs and delivery plans |
| `contracts/` | JSON Schemas, examples and future Arrow/Parquet contracts |
| `catalog/` | Source metadata and ingestion configuration (not raw data) |
| `src/insurance_market_au/` | Future Python packages for ingestion, synthesis, models, simulation and analysis |
| `pipelines/` | Data acquisition, normalization, validation and release workflows |
| `apps/` | Future analyst/consulting applications and APIs |
| `tests/` | Contract, data-quality, stochastic, integration and performance tests |
| `scripts/` | Lightweight local validation and developer utilities |
| `infra/` | Future deployment definitions; provider not yet selected |
| `notebooks/` | Research notebooks; never canonical processing logic |
| `examples/` | Non-sensitive scenario demonstrations |
| `data/` | Local-only staging location, Git-ignored |

## Working agreement

Open design and implementation changes as pull requests. New source ingestion requires a source manifest, licence review, validation rules and documented transformation. New models require a model manifest, feature/output contract and deterministic parity tests. A scenario can only be called reproducible when it pins every upstream release and random stream.

See [CONTRIBUTING.md](CONTRIBUTING.md). No open-source licence has been selected; do not assume redistribution rights for code or external datasets.

## M0.2 — Official vehicle source acquisition

Read the [source download guide](docs/data-foundation/feasibility/downloading-data.md).

```sh
python scripts/download_vehicle_sources.py --groups bitre,vic,nsw,sa,act --list
python scripts/download_vehicle_sources.py --groups bitre,vic,nsw,sa,act --download
```

Raw data goes into ignored `data/raw/`, and acquisition manifests into `data/reports/`. The [GitHub Actions workflow](.github/workflows/acquire-vehicle-data.yml) supports remote source discovery and download; raw artifacts are disabled unless expressly opted in after rights review.

## M1.5 — Publish a frozen research population

After generating the M1.3b sample (and optionally M1.4b candidate), install the release-management dependencies and freeze a named, content-addressed version:

```powershell
py -3 -m pip install -e ".[data,model,explore,release,dev]"
py -3 scripts/m15_release.py --publish baseline
py -3 scripts/m15_release.py --list
py -3 -m streamlit run apps/m13_explorer.py
```

The Streamlit **Population releases** tab provides a read-only selector, SHA verification, weighted exploratory summaries and an exportable population dependency pin. M2 enrichment and all future simulations must consume an **exact release ID**, not a mutable current-file path. No published research release is automatically approved for pricing, and the independently documented rare make/model/postcode uncertainty remains material.

See [M1.5 technical guide](docs/data-foundation/m15-population-releases.md), the [versioned feature-view contract](contracts/feature-views/market_vehicle_base_v1.json) and [scenario population pin schema](contracts/schemas/population-selection.schema.json).

## M2.0 — Research-only insurance feature port

Read [M2.0 contract, limitations and implementation guide](docs/delivery/m20-enrichment-foundation.md). `EnrichmentProvider(PopulationStore(release_id), EnrichmentSpec())` returns deterministic, streaming Arrow features without changing M1 releases. Mileage and value are unvalidated scenario placeholders; coverage defaults to unknown. The model pins its exact source population and all parameters.

## M2.1 — Replaceable market-feature models

[Architecture and sample usage](docs/delivery/m21-pluggable-market-features.md): `MarketFeatureProvider` streams M1.5-pinned Arrow features through independently versioned valuation and usage adapters. It includes a weighted segment-summary preview for future M3 development. Built-in models are illustrative placeholders, not actual Australian market valuations or insured-market estimates.

```powershell
py -3 -m pytest tests/test_m21_market_features.py -q
```

## M2.2 — Market actors and insurance participation

The [M2.2 model port](docs/delivery/m22-market-actor-ports.md) adds replaceable owner/driver/purpose/coverage and participation fields to the streaming M2.1 feature view. `ExtendedMarketProvider` preserves registration weights and original population lineage. The default values are unknown; opt-in `ScenarioActorModel` produces **hypothetical scenario** participation counts, not actual policies or insured risk exposure. Run `py -3 -m pytest tests/test_m22_actors.py -q`.
