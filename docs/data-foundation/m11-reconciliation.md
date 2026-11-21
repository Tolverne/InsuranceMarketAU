# M1.1 — BITRE workbook controls and disclosure-aware reconciliation

**Status:** M1.1 source control extraction and marginal diagnostics, not a completed calibrated population. Official reference date **31 January 2026**, workbook published **12 October 2026**. This builds directly on M1.0's verified 17 source Parquet staging files.

## Why this stage exists

The summary workbook has 15 tables with different meanings and units. For national registered-motor-vehicle stock, **Table 1** provides the appropriate primary 2026 published registration estimates by **8 jurisdictions × 10 vehicle classes** and their state/class/national totals. Table 2 is vehicles per capita, Table 3 is estimated average age, and Tables 13–15 concern other asset types; they must not be confused with a motor-vehicle count denominator.

The summary's national total is **22,771,150 motor vehicles**. It is a **published benchmark estimate**, not an exact vehicle-level record or an insurance policy count. Its state totals are:

| State | 2026 count |
|---|---:|
| NSW | 6,502,052 |
| Vic | 5,795,388 |
| Qld | 5,020,772 |
| SA | 1,664,049 |
| WA | 2,704,554 |
| Tas | 561,458 |
| NT | 173,660 |
| ACT | 349,217 |

The workbook extractor validates the exact SHA-256 and pinned Table 1 column layout; captures each source cell address and year; and emits **99 controlled cells** (8 jurisdictions plus national for 10 classes and the all-motor-vehicles total). Internal additive inconsistencies are reported, never silently adjusted.

## What the reconciliation actually does

Read separate, independently published aggregate Parquet tables from M1.0, **not individual vehicle records**. For each source, group its published aggregate counts to selected **shared marginal dimensions**. Compare only matching keys; preserve original source provenance, and do not multiply counts through table joins.

| Marginal | Publisher anchor / reference | Availability |
|---|---|---|
| Registered state × vehicle type | Workbook Table 1 | Any BITRE projection with registered state + class |
| Vehicle type × motive power | B26-02 | Projections with motive power |
| Vehicle type × year of manufacture | B26-01 | Projections with manufacture year |
| State × class × motive power | B26-03 | Matching high-dimensional projections |
| State × class × manufacture year | B26-01 | Matching projections |
| Vehicle type × **registration** postcode | B26-04 | Registration-postcode projections only |
| Vehicle type × **garaging** postcode | B26-09 | Garaging-postcode projections only |
| Vehicle type × make × model | B26-05 | Projections containing make and model |

Comparisons report signed/absolute residuals, median/95th-percentile/max differences, coverage, missing groups, numeric-zero cells and top discrepancies. Detailed paired residuals are written only to your local ignored data directory.

**Important disclosure semantics:** the original BITRE explanatory notes describe suppression of counts fewer than 3 and secondary perturbation/suppression. Numeric zero can be a disclosure-adjusted number, **not proof of a structural zero**. Missing groups are not treated as zeros, unknown count tokens are not imputed, and no unjustified statistical error interval or cell-level hard tolerance is invented.

The [versioned M1.1 constraint policy](../../catalog/constraints/bitre-2026-m11-policy.json) makes these treatment decisions machine-readable and explicitly leaves statistical hard/soft approvals unresolved. The staged Parquet auditor verifies source release, reference date, source-row sequence, source count/status consistency and the M1.0 physical row/count contract before comparing margins.

The workbook's national total is the highest-priority published accounting anchor. State/class counts are published benchmarks to be respected with explicit consistency decisions. Fine-grained projected counts remain soft or interval-candidate constraints until a documented likelihood/confidentialisation model is developed.

## Run locally (after PR merge)

You have already downloaded the raw sources and run full M1.0 staging. No more download is required.

```powershell
cd C:\Users\gtx\source\repos\InsuranceMarketAU
git pull origin main

# Add workbook parser to the existing data-engineering environment
py -3 -m pip install -e ".[data,dev]"

# Short pilot: three of the 17 already-staged BITRE projections
py -3 scripts/m11_reconcile.py --selected B26-01,B26-02,B26-03

# Full 17-table analysis (streams the larger local Parquet datasets)
py -3 scripts/m11_reconcile.py
```

If your previous stage was **profile-only**, generate Parquet first with `py -3 scripts/m1_ingest.py --parquet`.

Outputs in git-ignored directories:

- `data/processed/m1/controls/bitre-2026-table1-controls.json` and `.csv`: authoritative published source cells and their workbook cell positions
- `data/reports/m1/bitre-2026-m11-pilot-reconciliation.json` or `...-full-reconciliation.json`: summary and most significant discrepancies
- `data/reports/m1/bitre-2026-m11-pilot-residuals.csv` or `...-full-residuals.csv`: matched-cell comparison details, not input microdata

No automatic uploads to GitHub or S3. No synthetic vehicle population created.

## Verification and stages

The workbook layout is verified against the **official publisher XLSX**, not an invented spreadsheet layout. Tests cover source hash/layout drift, the 99 control cells, additive inconsistencies, total-row exclusion, genuinely missing margins, postcode-role separation, and staged Parquet lineage. GitHub CI independently exercises the small real-data pilot and contract tests.

**M1.2** will harmonise the jurisdictional data releases at their actual dates and geographic roles. **M1.3** will build the sparse-support statistical reconstruction, parameter-uncertainty ensembles, constrained calibration and later synthetic vehicle population release. Before that, we must make a reviewed decision about which workbook and detailed cells can be treated as exact vs soft given BITRE disclosure and record inclusion rules.


## Independently verified complete-source audit (21 November 2026)

The [complete 17-projection GitHub Actions audit](https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44847246292) **passed**. It streamed all **12,181,645 published aggregate rows**, retained distinct source identities, validated the workbook's **99 control cells**, and computed **47 common-margin comparisons**. All 47 pairs had at least one nonzero residual. Exact audit-level numbers are pinned in [bitre-2026-m11-full-audit.json](../../catalog/acquisition/bitre-2026-m11-full-audit.json).

| Shared margin | Comparisons | Maximum absolute residual | Projection responsible for maximum |
|---|---:|---:|---|
| State × vehicle type | 11 | 6,382 | B26-17 vs Table 1 |
| Type × motive power | 7 | 8,867 | B26-17 vs B26-02 |
| Type × manufacture year | 7 | 1,640 | B26-16 vs B26-01 |
| State × type × motive power | 4 | 4,235 | B26-17 vs B26-03 |
| State × type × manufacture year | 4 | 596 | B26-16 vs B26-01 |
| Type × registered postcode | 6 | 133 | B26-13 vs B26-04 |
| Type × garaging postcode | 1 | 95 | B26-12 vs B26-09 |
| Type × make × model | 7 | 257 | B26-17 vs B26-05 |

The **8,867 vehicle** difference occurs in the **passenger × petrol** margin: B26-02 reports 12,611,695 and B26-17 reports 12,602,828 (0.0703%). The **6,382** NSW passenger vehicle difference from the workbook is 0.1337%. Smaller make/model categories can show much larger *relative* discrepancies; those are especially important for classic/prestige segments.

The audit saw **4,177,485 numeric zero cells** across the 17 published tables, and no nonnumeric count tokens. This is emphatically **not** a count of zero vehicles or of definitively suppressed individuals. Suppression/perturbation occurs inside the published numeric values and can accumulate in high-dimensional margins. Both positive published values and published zeros remain subject to disclosure-adjustment uncertainty. Do **not** set an exact cell-level equality or an invented ±n error tolerance from these observations.

**M1.1 quality gate:** workbook and source-provenance parsing **passed**; total/segment parity diagnostics **passed as measurement**, not as a calibration criterion. The high-dimensional B26-16/B26-17 discrepancies are **flagged for future soft-constraint selection, uncertainty modeling, and independent holdout testing** in M1.3. No constrained synthetic population has yet been released.

