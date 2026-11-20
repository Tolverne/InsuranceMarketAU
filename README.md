# InsuranceMarketAU

**Australian Motor Insurance Market Data Foundation & Competitive Simulation Platform**

A consulting-first, evidence-led platform for constructing a versioned Australian vehicle and insurance market, modelling any number of insurers/brands/products with interchangeable models, and running reproducible probabilistic market and financial scenarios.

> **Status:** M0 design baseline (proposed; review before implementation). No production dataset or validated market forecast is implied.

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
