# M1.4a — Synthetic vehicle model diagnostics

Status: development. Preserve the M1.3a/B model fit, protect the current explorer, add source-verified independent holdout comparisons, error decomposition by segment, and reproducible seed/sample-size sensitivity. M1.4a is a **diagnostic milestone** and must not fit to B26-14, B26-16 or B26-17; a subsequent M1.4b calibration PR will address statistical improvements separately.

Initial real-source benchmark: [completed high-dimensional holdout audit](https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44862567592), with WAPE (published cells ≥100) B26-14 53.98%, B26-16 154.97%, B26-17 130.39%. These metrics are based on 85,000 weighted synthetic rows and disclosure-adjusted published aggregates, *not* independent vehicle-level truth.
