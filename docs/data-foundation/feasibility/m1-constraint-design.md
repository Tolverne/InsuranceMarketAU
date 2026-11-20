# M1 national synthesis: source-constrained statistical design

**Status:** design proposal pending detailed source files, explanatory notes and measured constraints. This is not a validated estimator.

## Fundamental unit and universe

A source stock cell is \`(source_release, reference_date, dimension_codes, count_or_interval, disclosure_status)\`. A vehicle population is a *synthetic* object drawn from a distribution over these cells and optional attributes. Model the unrestricted registered fleet first. Keep restricted, trailer and unregistered collectible extensions as separately defined scope strata.

## Projection graph

Let \`X\` be an unknown sparse contingency tensor over canonical vehicle dimensions such as

\[
X_{s,p_r,p_g,t,m,y,f}
\]

where \`s\` state, \`p_r\` registered postcode, \`p_g\` garage postcode, \`t\` vehicle class, \`m\` make/model, \`y\` manufacture year and \`f\` fuel.

Each published BITRE cross-tab supplies a *different projection* \`A_k X\` over its subset of dimensions. Observations \`b_k\` may be exact, rounded, perturbed, suppressed or incomplete:

\[
b_k = A_k X + \epsilon_k,\qquad X \ge 0.
\]

Do **not** treat all \`b_k\` as exact equations before reading explanatory notes. Explicitly encode interval/likelihood constraints for suppressed or rounded values. National grand totals are a different control tier from partial/suppressed granular cells.

## Recommended starting model

1. **Choose common universe/date and class codes.** Define registered class counts and error budgets from BITRE summary.
2. **Canonicalize all tabulations.** Long-form table \`projection_id, code_tuple, count, disclosure_status, lower_bound, upper_bound, reference_date, location_role\`.
3. **Validate tabulations.** Check uniqueness, structural zeros, prohibited category combos, row totals, cross-table marginal sums; classify contradictions before fitting.
4. **Construct sparse support.** Avoid full Cartesian product of postcode × model × year × fuel. Generate only plausible vehicle configurations using specification/observed joint support and hierarchical backoff for rare models.
5. **Prior distribution.** Derive initial \`q(X)\` from observed joint projections, combining source evidence with explicit weight, not naive independent multiplication. Enforce mechanically implausible fuel/manufacture combinations only when supported by reliable reference information.
6. **Constrained fitting.** Begin with raking / iterative proportional fitting on compatible exact margins; use a generalized calibration objective for uncertain/perturbed margins, e.g.
   \[
   \min_{X\ge0}\quad \mathrm{KL}(X\Vert q) +\sum_k \lambda_k\,L_k(A_kX,b_k),
   \]
   with constraints for true hard controls. Document soft weights \`lambda_k\` and losses \`L_k\`. These are *design examples*, not fixed implementation choices.
7. **State cross-validation.** Hold out some observed BITRE projections and jurisdiction tables (or cells not used for fit); report predictive error, not merely fit error.
8. **Uncertainty ensemble.** Draw plausible parameters/conditional interactions, recompute constrained populations and assess segment sensitivity. Different random assignment seeds alone do not capture the non-identifiability of missing joints.
9. **Materialize efficiently.** Publish aggregate cell solution and versioned weighted sample; full synthetic vehicles after performance/quality benchmark.

## Key identifiable and unidentified relationships

**Observed partially:** model × region, model × year, model × power, state × year × power, postcode × year/make, etc.  
**Not identified directly from catalogue:** registration vs garaging postcode pair; postcode × **model** × **manufacture year** × **fuel** simultaneously; model variant/trim; location × customer age/annual km; private vs commercial insured status for a specific vehicle.

If a target segment relies on an unidentified interaction (e.g. 1970s prestige cars garaged in one flood-prone suburb), output a wide scenario range or request better data; do not publish a narrow point estimate justified by unrelated marginals.

## Pitfalls and tests

- **Misjoined margins:** cross-tab joins multiply fleet counts. Test that each output segment totals against source controls.
- **Source vintage leakage:** no future Sep 2026 state data as a Jan 2026 direct observation; temporal adjustment must be modelled if used.
- **Pseudo-precision:** item-by-item synthetic IDs do not imply observed individual vehicles.
- **Privacy:** rare model × postcode × manufacture year combinations can disclose or narrow down ownership; apply output suppression/aggregation.
- **Scope mismatch:** BITRE on-road unrestricted vehicles versus TAS including trailers/restricted, QLD excluding seasonal, VIC excluding trailers; reconcile at class scopes.
- **Fuel misclassification:** VIC E includes electric or hybrid electric, not only pure battery EV.
- **Unknown vs zero:** zero/suppressed/missing are distinct in the likelihood/constraint model.
- **Duplicate make/model naming:** distinguish normalization mapping/version before joining projections.
- **Weighted cohorts:** sample weights must reproduce totals; rarity stratification/variance measured.

## Candidate pilot

At **national state × vehicle class × make × year × power** scale, fit B26-14 and B26-15 with state/power controls B26-03/B26-10. Deliberately hold out B26-01 (state/year) or subsets to test reconstruction. Then incorporate postcode B26-16 and B26-17; test explicitly how outcomes change under different postcode × age × fuel dependence assumptions. Final order depends on actual cell files and suppression notes.

## Release criterion

No M1 fleet release unless (1) input licences cleared, (2) all controlling source files hashed and stored privately, (3) feasible constraint system and residual report, (4) independent holdout accuracy, (5) uncertainty/confidentialisation review, (6) location role and universe scopes documented, (7) reproducible build and output schema validated.
