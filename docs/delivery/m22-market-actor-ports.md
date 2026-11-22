# M2.2 — Replaceable market actors and participation ports

M2.2 extends the M1.5 → M2.1 streaming market feature contract without altering historical releases or the M2.1 API. The next goal is **M3 segmented market intelligence**, then **M4 participant pricing adapters**, then **M5 competitive demand and choice**. Research-grade valuation and population calibration can continue independently.

## Contract

`ExtendedMarketProvider(population, ExtendedMarketSpec(...))` wraps the M2.1 provider and appends six stable fields: owner category, driver relationship, vehicle purpose, insurance-participation status, coverage, and the full selection digest. The first five are **categorical scenario flags**, not people, households, licences, policy records or insurance observations.

- Default `UnknownActorModel` deliberately labels all categories `unknown`. It does not equate unknown with uninsured.
- Optional `ScenarioActorModel` provides reproducible **hypothetical** ownership, vehicle purpose and insurance participation outcomes for simulator architecture demonstrations. Driver relationships remain unknown; scenario draws are keyed by release/row/seed and stable under different batch boundaries.
- Model identity, version, assumptions and SHA-256 pin include the full M2.1 and M1.5 lineage.
- Registered vehicle mass is always retained. The segment report separates hypothetical insured, hypothetical uninsured and unknown weighted vehicle mass. These are not insured-policy counts or exposure years.
- The actor models do **not** assign household IDs, person IDs or linked driver identities; these would require a different data-generation and linkage model with its own research and validation.

## Example

```python
from insurance_market_au.population import PopulationStore
from insurance_market_au.enrichment.actors import ScenarioActorModel
from insurance_market_au.enrichment.market_view import ExtendedMarketProvider, ExtendedMarketSpec

pop = PopulationStore("pop-20260131-REPLACE_WITH_REAL_RELEASE_ID")
model = ExtendedMarketProvider(
    pop, ExtendedMarketSpec(actors=ScenarioActorModel(insured_probability=0.75)))
print(model.pin())
print(model.summarize(group_by=("registered_state", "owner_type_scenario")))
```

The 0.75 above is an arbitrary demonstration assumption, not an Australian insurance rate. The `summarize()` API uses an unobserved scenario denominator that should never be labelled as an empirically validated addressable or insured market. The next M3 contract will specify explicit market eligibility, segment selection, numerator/denominator definitions and provenance.

## Local tests

```powershell
py -3 -m pip install -e ".[release,dev]"
py -3 -m pytest tests/test_m22_actors.py -q
py -3 -m pytest -q
```

**Scope boundary:** M2.2 implements replaceable model ports and streaming summaries, not persisted enrichment releases, independent insurance calibration or an M3 analyst application. No individual or proprietary records enter Git.
