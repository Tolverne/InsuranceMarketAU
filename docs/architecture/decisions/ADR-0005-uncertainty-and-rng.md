# ADR-0005 — Separate epistemic uncertainty and stochastic outcomes

- **Status:** Proposed (M0)
- **Context:** Thousands of runs are useful only if assumptions and stochastic variation are distinguishable; strategy comparisons otherwise suffer avoidable noise.
- **Decision:** Nested draws for unknown population/model/behaviour parameters, and conditional market/claims outcomes. Use pinned counter-based or independently keyed deterministic random streams, paired baseline/alternative runs and explicit joint-correlation assumptions.
- **Consequences:** More computation and diagnostics but defensible distributions, variance attribution, stable comparisons and value-of-information studies.
- **Review when:** Empirical data supports posterior calibration, alternative uncertainty techniques or correlated catastrophic shock models.
