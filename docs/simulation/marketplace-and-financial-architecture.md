# Competitive marketplace, insurer and stochastic financial architecture

**Status:** v0.1 conceptual target architecture. The data foundation can be built independently before this runtime exists.

## 1. Participants are identical

A target company is not a special computational entity. Each participant belongs to a hierarchy:

```text
Economic group
  |-- legal risk carrier(s) / reinsurance arrangements
  |-- underwriting agency / MGA relationship(s)
  |-- brand(s)
      |-- product(s), coverage packages and channels
          |-- target-market predicate
          |-- underwriting rules / appetite / capacity
          |-- pricing model binding (versioned)
          |-- distribution, value proposition and retention rules
```

Risk ownership, distributor, brand and group can be many-to-many across products; the eventual relational model will support partnerships and white-label carriers rather than assuming one-to-one joins. Keep reporting hierarchy distinct from claims liability.

## 2. Model/plugin runtime contracts

Separate interfaces for **target market**, **underwriting**, **pricing**, **risk/claims**, **consumer choice**, **strategy** and **finance**. A model is not defined by GLM/GBM implementation. Every adapter declares:

- Stable model ID, semantic version, immutable artefact reference/hash and effective dates.
- Feature schema/version, required/optional inputs, units, null handling, transformations and currency/tax semantics.
- Batch input with quote date, coverage/excess, source feature release, context and model version.
- Typed batch output with status/reason, offer terms, premium components, quote validity and diagnostics; no ambiguous bare number.
- Error policy (missing features, model unavailable, timeout, unacceptable output), numerical tolerance and reproducibility/replay capability.
- Execution mode (`local_python`, `container`, `http_api`, `rules_table`) and secure credentials owned outside manifests.

For external services, preserve lawful response snapshots or signed output hashes for deterministic scenario replay. Pricing models and commercial offer assembly must not be confused with technical loss-cost models.

## 3. Market evolution, demand and decisions

Simulate at a declared interval (e.g. month, with precise event times when necessary). Start with fleet stock and synthetic insurance/household attributes. Generate entry/exit/migration, vehicle purchases, renewal dates, shopping triggers, changes in affordability, potential lapse and insurance choices.

At each eligible shopping event:

1. Determine channel and **consideration set**; not every product is necessarily known to each customer.
2. Apply target-market predicates and underwriting to all candidate offers.
3. Call each qualifying product's *pinned* pricing model in batches; compute comparable all-in terms.
4. Evaluate choice probabilities with coverage/excess, brand, channel, price, incumbency and unmet-need/outside option. Calibrate behaviour where empirical evidence exists.
5. Draw one realised outcome, record probability diagnostics and apply policy transfer/creation/lapse.
6. Update incurred exposures, group/brand/product in-force books and financial obligations.

`outside_option` (no optional cover) and `incumbent_keep` must be represented consistently; multi-brand customer choice does not multiply an individual customer's purchases. Group policy consolidation measures **incremental group business** and brand cannibalisation rather than merely reporting each brand's growth.

### Choice model

Use a simple multinomial logit as a transparent prototype, then test nested/mixed logit and non-price heterogeneity when data justify. The consideration set and brand awareness can matter more than premiums. Ensure probabilities sum to 1 over eligible offers and outside option, non-eligible offers never win, and known group affiliations do not create inconsistent double counts. Do not infer elasticity or competitor actions from nothing; represent unmeasured parameters as distributions/scenario assumptions.

## 4. Competitor strategy

Each participant gets an updateable configuration binding product appetite, distribution, model/version, capital/volume constraints, expenses and renewal behaviour. Fixed-strategy competitors should come first; responsive rule-based competitor agents can later react to observable market metrics with declared timing and information sets. Avoid giving competitors access to future or another insurer's private actuals (look-ahead leakage). Reporting can be at product, brand, carrier and group levels, with confidentiality/visibility controls.

## 5. Claims and finance

Claims are generated against peril-specific exposure, with frequency/severity dependencies and shared catastrophe shocks (to allow correlated market losses and accumulation). Model reporting lag, paid/incurred development, repair inflation, salvage/recovery and reinsurance at appropriate granularity.

Finance needs reconciled **written, earned, paid, incurred and ultimate** views. Minimum ledger dimensions: reporting period, insurer/group/brand/product, coverage, policy/claim, gross/net basis, transaction/valuation date, scenario/run/draw, AUD, cash/accrual classification.

Core result measures: policy count, earned exposures, GWP, earned premium, claim counts and incurred losses, expense ratios, combined ratio, underwriting result, operating result, cash runway, reinsurance costs/recoveries, capital and solvency stress.

Australian AASB 17 / IFRS 17 reporting and APRA regulatory capital should be **separate accounting/regulatory adapters**, not casually approximated by the management P&L. The model's accounting basis must be explicit. Financial estimates of competitors may carry more uncertainty than a client's own ledger.

## 6. Nested simulation and experiments

```text
Scenario manifest (pinned population/participants/models/assumptions)
  -> parameter or population draw m = 1..M
      -> outcome stream r = 1..R
          -> market + claims + finance
          -> diagnostic and ledger snapshots
  -> aggregated per-run KPI tables
  -> distributions, conditional quantiles, paired deltas, risk decomposition
```

At minimum separate: (a) epistemic uncertainty about population, price response, competitor model, cost and claims; (b) stochastic choices, accidents and catastrophes; (c) sampling variance if using weighted cohorts. Pseudorandom seed, algorithm and stream structure must be pinned. Scenario A/B comparisons reuse common randomness where valid for variance reduction, not independent draws by default. Model dependent shocks explicitly to avoid underestimating adverse tail risk.

**Metrics:** distribution of profitability and capital, probability of loss/shortfall, percentiles, conditional downside, market share, retention, acquisition, group cannibalisation, customer value, difference-versus-baseline with Monte Carlo standard errors. Report sensitivity and calibration; no point prediction without ranges.

## 7. Computational approach

Use event-driven demand and batched quote inference instead of every model quoting every vehicle on every time step. For full-population reports, execute vectorised group-bys over immutable Parquet partitions. For thousands of Monte Carlo runs, combine deterministic stratified/weighted cohorts with validation against full-fleet runs and benchmark tail-risk rare-event techniques. Distributed workers and cloud infrastructure are options after single-machine benchmarks.

## 8. Acceptance tests

- Identical input/configuration on two participant instances gives identical decisions and pricing before any strategy differences.
- A model swap changes only the model binding and downstream effects; old scenario outputs replay unchanged.
- Eligible quote probabilities plus outside option sum to one; ineligible product can never bind.
- Brand acquisition, group acquisition and cancellations reconcile; intra-group movement is identified.
- Written/earned premium, incurred/paid losses and group consolidation reconcile by period and policy.
- Reinsurance and shared catastrophe shocks do not create duplicated net losses.
- Same full manifest + fixed random streams gives bitwise/declared numeric reproducibility.
- Paired scenarios report uncertainty of **differences**, not just overlapping independent confidence intervals.

## 9. Sequence of implementation

Do **not** implement this module while the population contract is unstable. First: data foundation + feature view (M1/M2); then symmetric participant/model registry; then event choice; then claims/finance; then nested scenarios and consulting UI. Design tests and ports now, not the platform vendor stack.
