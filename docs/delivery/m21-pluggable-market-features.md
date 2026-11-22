# M2.1 — replaceable vehicle value and usage models (POC architecture)

**Status:** architecture and contract demonstration. All built-in values are hypothetical and uncalibrated; no source evidence has been fitted or implied.

## Architectural intention

Build the whole segmented market simulator **before** investing deeply in insurer-specific vehicle valuations or household/driver models. The correct unit of the national market is the M1.5 *weighted synthetic representative*, not a policy, driver, customer or household. Downstream segmentation and choice models must preserve that distinction.

```text
Immutable M1.5 population release + exact pin
             |
             v
M2 market feature provider -- value adapter (replaceable)
                           -- usage adapter (replaceable)
                           -- future ownership/driver/cover adapters
             |
             v
M3 weighted segment denominators -> M4 pricing participants
             |                         |
             +----------> M5 competitive market/choice
                                  -> M6 ledger
                                  -> M7 scenarios
```

The public `MarketFeatureProvider(...).iter_feature_view()` continues to emit `market_insurance_features_v1` Arrow batches with M1.5 rows and weights preserved. A model adapter implements `identity` (versioned assumptions) and `predict(rows, *, seed)`; the output column contract remains stable even when its algorithm changes from a demonstration constant to a valuation table, GLM, GBM, external API or more advanced model. Each selection pin includes exact population lineage, model IDs, version and assumption SHA-256 and seed. The immutable model version is **declared** by the adapter: governance and signed artefacts are future work.

`MarketFeatureProvider.summarize(...)` supplies an early weighted segment API with totals, effective support and hypothetical conditional averages. This is a *preview* for M3, not an insured or addressable-market denominator. It accepts at most three recognised categorical dimensions and never treats missing valuation/distance as a zero or drops unknown records from the vehicle mass.

## Example

```python
from insurance_market_au.population import PopulationStore
from insurance_market_au.enrichment.workbench import MarketFeatureProvider, MarketFeatureSpec
from insurance_market_au.enrichment.adapters import UniformValuePlaceholder

pop = PopulationStore("pop-20260131-REPLACE_WITH_A_REAL_RELEASE_ID")
provider = MarketFeatureProvider(
    pop, MarketFeatureSpec(seed=24,
        value_model=UniformValuePlaceholder(low_aud=5000, high_aud=80000)))
print(provider.pin())
print(provider.summarize(group_by=("registered_state", "vehicle_type"), max_groups=50))
```

For custom model implementations, use a class with `identity = ModelIdentity(...)` and `predict(rows, *, seed)`. Changing either implementation or assumptions **must** increment the declared model version; there is no automatic version-enforcement mechanism yet.

The current adapters operate over each Arrow batch converted to Python rows, which is appropriate for a POC but not a performance assertion for the full national data. Later models may expose vectorized Arrow or remote execution adapters behind the same feature contract.

## Deliberate exclusions

- No fake individual ownership, driver, claims or insurer policy attributes
- No real valuation inference, depreciation fitting or kilometre calibration
- No automatic inference that cover is purchased, or that every registered vehicle is addressable
- No persistence of M2 enriched releases or approval for pricing consultancy outputs
- No true probabilistic insured-market participation; defer to the explicit M2/M3 market participation layer

## POC delivery sequence

1. **M2.1:** Stable model adapter port and weighted segment aggregation (this PR)
2. **M2.2:** Placeholder ownership/driver/vehicle-purpose/coverage **interfaces** with explicit missing-value policy and no implied empirical calibration
3. **M3:** Reusable segment definition DSL, weighted denominator accounting, selection snapshots, uncertainty/sensitivity reports, analyst exploration
4. **M4:** Pluggable participant/product/rating models; explicit eligibility and quote/coverage contracts
5. **M5:** Demand/renewal events and competitive choice, including an outside option and market share conservation
6. **M6/M7:** Financial ledgers and reproducible scenario comparison; then revisit empirical input model sophistication

Evidence and research can be added in parallel to improve M2 adapters without redesigning M3–M7.
