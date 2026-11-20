# Data provenance, uncertainty and quality framework

**Status:** v0.1 proposed. A populated synthetic row is not evidence that a value was observed.

## Provenance classes

1. **Observed:** directly published at the claimed grain and date; preserve dataset/release pointer.
2. **Harmonized:** faithfully transformed/categorized from observed values; preserve mapping/version.
3. **Estimated:** inferred at a stated aggregate/population level from empirical modelling.
4. **Imputed/synthesized:** assigned to a synthetic row using a statistical relationship and RNG; record method and draw.
5. **Scenario-assumed:** chosen to explore a hypothesis, not empirically established.

At scale, store batch/column-level lineage plus sparse per-row exception flags and immutable upstream references; avoid repeating long metadata objects for 20m records. Publish a modelled-variable summary per release and conditional certainty/range where feasible.

## Quality dimensions and evidence

| Dimension | Checks | Report |
|---|---|---|
| Validity | Types, domain values, postcode/state, dates, manufactured year, weights | Failure counts and rates |
| Completeness | Missing, suppressed, unknown, imputed, not applicable | Feature/grain coverage |
| Uniqueness | Source event IDs, aggregate cell keys, release vehicle keys | Duplicates |
| Consistency | Stock vs stock, sum of parts, class/taxonomy, time transitions | Reconciliation table |
| Accuracy / calibration | Residuals to independent controls, held-out joint distributions | Error metrics with weights |
| Timeliness | Observation/ingestion lag, temporal-adjustment gap | Age and assumptions |
| Representativeness | State, vehicle age, class, EV, rural and sparse-cell performance | Segment diagnostics |
| Statistical uncertainty | Across model/parameter draws and conditional outcomes | Credible/sensitivity intervals |
| Rights/privacy | Licence, restriction, small-cell disclosure, controlled access | Pass/fail review gate |

## Calibration policy

Write a machine-readable validation report for every release. Define `count_error = synthetic_weighted_count - observed_count` and absolute/relative deviations where denominator > 0. Also report distribution distances (e.g. total-variation or divergence) where meaningful; do not average away catastrophic small-segment failures. Separate constraints **fit during synthesis** from **independent validation**. Report exclusions, suppressed cells and missing comparison data explicitly. Never claim zero discrepancy solely because raking forced agreement on its fitted margins.

## Hard versus soft controls

Hard controls are exact within stated data/rounding conventions and scope. A release fails if hard controls cannot be honored. Soft controls receive reliability weights and dated/method-adjusted comparisons; violations are logged with reason and threshold. When sources disagree, a documented reconciliation choice is required: no silent priority override.

## Population uncertainty

Distinguish:
- **Parameter/model uncertainty:** missing conditional relationships, source-vintage adjustments, coverage gaps, valuation and usage models.
- **Imputation randomness:** alternative synthetic assignments conditional on a fixed estimated model.
- **Sampling variance:** weighted sample construction and rare strata.
- **Scenario/process randomness:** customer choices, accidents and catastrophe outcomes (simulator layer).

Store `population_draw_id`, `synthesis_model_id`, random algorithm and seed/substream IDs. Never give a confidence interval based only on imputation seeds if dominant uncertainty is unidentified parameters.

## Controlled publication

Each release is accompanied by a coverage statement, data dictionary, lineage graph, calibration residuals, known biases, sensitivity report and release decision. If a source forbids redistribution, retain and serve only authorized derived outputs. Before sharing high-resolution results externally, apply small-cell/privacy review and relevant licence restrictions. No raw personal or identifiable source records in Git.

## Failure escalation

1. **Block:** invalid schema/negative counts, privacy restriction breach, absent source licence review, broken hash or hard-control contradiction.
2. **Quarantine:** unexplained mapping or time inconsistency; preserve raw artefact and issue.
3. **Warn:** documented soft discrepancies; quantify impact on downstream target markets.
4. **Approve:** signed-off release report and pinned manifest.

## Initial M1 diagnostics

- National and state totals by class with official source comparisons.
- State x vehicle age, make, fuel, postcode distribution where published.
- Synthetic rarity/outlier assessment and the source dimensions supporting each joint distribution.
- Full-versus-weighted sample parity, effective sample size and rare-category inclusion.
- Holdout calibration on cells not explicitly fitted.
- Rerun reproducibility and change attribution between source vintages.
