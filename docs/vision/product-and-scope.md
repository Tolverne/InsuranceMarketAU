# Product vision, scope and consulting value

**Status:** proposal v0.1. **Audience:** consulting analysts, data scientists, pricing actuaries, management, investors, model risk reviewers.

## Vision

Build a national motor-insurance market data foundation and simulation environment where any number of insurers, underwriting agencies and brands compete for a shared synthetic Australian market. Produce defensible **distributions**, uncertainty attribution and incremental strategy comparisons, rather than unqualified point forecasts.

## Use cases

1. Addressable market and segment sizing for mainstream, prestige, EV, collector and commercial lines.
2. Compare competitor positioning from calibrated or hypothetical pricing models.
3. Test product, channel, appetite, branding and pricing changes and measure both customer acquisition and group cannibalisation.
4. Forecast portfolio evolution, earned premium, ultimate claims, expenses, cash movements, capital need and downside.
5. Evaluate scenarios using paired random streams and quantified parameter uncertainty.
6. Provide auditable, versioned consulting outputs and potential later deployment of an independent pricing service.

## Market boundaries

**Initial observed backbone:** Australian registered road vehicle fleet, subject to published source definitions and control totals. **Extended insurable universe:** potentially insurable unregistered/laid-up collector vehicles and niche classes, separately estimated and labelled. Do not silently treat all registered vehicles as insured or every vehicle as exactly one policy. CTP and optional motor property cover require different treatment; initial simulated insurance demand will focus on optional motor property, with CTP left as an explicitly scoped future module.

**Insurance entities:** distinguish corporate group, risk carrier (legal entity), managing agent, brand, product, offering, distribution channel, contract and risk exposure. A customer may encounter multiple offers, including offers backed by the same carrier.

**No privileged target:** a client or startup differs from a competitor by access to better data, configuration and reporting permissions—not simulator mechanics.

## Non-goals for M0–M2

- Production underwriting/quoting or binding actual policies.
- Collection of personal vehicle ownership data.
- Claims-accurate replication of specific proprietary insurer portfolios from public market data.
- A promise that competitor internal pricing, capital or financials are known.
- A nationwide address-level property-risk database.
- Final cloud/frontend selection before workloads and security needs are quantified.

## Success criteria

Deliver independently refreshable, reproducible synthetic populations; measured calibration error; explicit data/model uncertainty; fixed interface contracts; symmetric insurer participants; and eventually comparable probabilistic outcomes with clear provenance. Consulting outputs must distinguish evidence, estimates and assumptions.
