# M2.0 — Insurance enrichment foundation (research-only)

## Scope

M2 consumes an **exact, verified M1.5 population release** through
`PopulationStore(release_id).iter_feature_view()`. It never changes or regenerates
the national registration market. This first slice provides a deterministic,
typed, model-versioned enrichment port for subsequent household, driver, value,
usage and insurance cover research.

The M1 vehicle registration universe is **not** the insurable or insured market.
A weighted sample row is not an observed driver, policy or household, and the
sampling weight remains **expected registered vehicles**, not exposure years.

## Delivered contract

`insurance_market_au.enrichment.EnrichmentProvider(population, spec)` streams
Arrow batches with all M1.5 fields unchanged and six clearly differentiated
fields: derivable age, hypothetical annual kilometres, hypothetical value,
coverage assumption, model digest and uncertainty label.

`EnrichmentSpec` holds the chosen seed, reference year, broad demonstration
ranges and optional explicit coverage category. **All numerical scenario
ranges are placeholders, not calibrated Australian facts.** Coverage is
`unknown` by default, and no people or policies are fabricated.

The provider's `pin()` contains the **complete immutable M1.5 population pin**,
M2 contract/model version, model parameter digest and all scenario parameters.
The SHA-256 counter draws are keyed by population release, release-local row ID,
seed and feature name. Reordering or rebatching does not change assigned
scenario values. Different M1 releases are never assumed to contain the same
individual vehicles.

This is not yet an immutable on-disk enrichment **release**: the dependency
pin is a reproducible model configuration and source reference. Full
content-addressed persisted enrichment releases, source-evidence catalogues,
QA/holdout benchmarks and uncertainty draws are later M2 deliverables.

## Illustrative use

```python
from insurance_market_au.population import PopulationStore
from insurance_market_au.enrichment import EnrichmentProvider, EnrichmentSpec

population = PopulationStore("pop-20260131-REPLACE_WITH_REAL_24_HEX_ID")
enriched = EnrichmentProvider(population, EnrichmentSpec(seed=20261122))
manifest = enriched.pin()
for batch in enriched.iter_feature_view(batch_size=25000):
    # Each batch retains the original sampling_weight and release-local IDs.
    print(batch.schema)
    break
```

Install dependencies with `py -3 -m pip install -e ".[release,dev]"`.
Run `py -3 -m pytest tests/test_m20_enrichment.py -q`.
There are no new downloads, fitting steps or prerequisites beyond a local
published M1.5 release.

## M2.1+ priorities and validation gates

1. Establish independently sourced distributions, dated source manifests,
   licence/privacy checks and conditional model assumptions for annual distance,
   vehicle value/depreciation and vehicle purpose.
2. Develop explicit owner/household and driver **latent entities** without
   pretending independently published aggregates are linked microdata.
3. Introduce exposure/coverage and insured-market participation as separate
   probabilistic models with configurable scenarios and holdout validation.
4. Publish content-addressed enrichment assets with source dependency hashes,
   drift/diagnostic reports and sample-weight conservation checks.
5. Add a research explorer for distributions, assumption sensitivity and
   uncertainty attribution, keeping empirical and hypothetical panels separate.

**Gate:** no commercial pricing, market share or customer segmentation claims
until evidence quality and model bias have been reviewed.
