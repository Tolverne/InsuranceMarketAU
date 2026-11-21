# M1.0 — First actual source ingestion and integrity diagnostics

**Status:** IMPLEMENTED initial BITRE 2026 streaming source ingestion pipeline, not yet a calibrated national vehicle population. This is a deliberate first part of M1; population synthesis comes only after source reconciliation and disclosure review.

## Why the M1.0 first slice matters

The January 2026 BITRE dataset is an excellent national backbone: 17 confidentialised but distinct aggregate stock projections, plus explanatory notes. A source cannot be treated as a row-level vehicle table, and the 17 views must **not** be summed or joined on make, postcode or year to infer an individual registered vehicle. The workbook is a separate summary benchmark; future work extracts controls from it.

**Verified real CSV headers:** one extract uses `vehicle_type,state_abb,year_of_manufacture,no_vehicles`; a different extract uses `year_of_manufacture,vehicle_type,motive_power,no_vehicles`; and the state/power view uses `state_abb,vehicle_type,motive_power,no_vehicles`. Real source headers have been inspected via [M1 GitHub evidence job](https://github.com/Tolverne/InsuranceMarketAU/actions/workflows/m1-source-evidence.yml).

### BITRE confidentiality (from actual explanatory notes)

**Published total rows:** Real-world pilot inspection found a national total of **22,771,150** is present *as an additional source row* in each of three BITRE projections. The raw `no_vehicles` column sums to **45,542,300**, exactly twice the national fleet, when the grand-total record is naively included. The pipeline flags `vehicle_type='Total'` and `vehicle_type='-'` (plus explicit `Total` in any dimension) as published aggregate rows, retains them in Parquet for audit, and computes `detail_numeric_total` separately from `numeric_total`. This has been checked against three actual extracts, but other projection schemas remain to be profiled.

BITRE states that detailed tables suppress cells with **fewer than 3 units**, and perturb or suppress secondary cells, including totals, to reduce identification risks. Therefore summing interior cells may differ from totals in a detailed table or published workbook. Further, **garaging postcode** is sometimes replaced with registered postcode when true garaging postcode was unavailable. Some registered postcodes may be administrative rather than residential, invalid postcode uses `UNKN`, and registration jurisdiction may not equal address location.

**Full audit evidence:** A [real-source GitHub run](https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44843689743) streamed all **12,181,645 aggregate source rows** across 17 CSVs. Every extract had exactly one published national total, and every detail-only sum equalled **22,771,150**. All 17 column layouts mapped without unknown physical fields; no nonnumeric count tokens appeared. **Important:** zeros and numeric cells may still reflect suppression and perturbation; absence of nonnumeric tokens does **not** mean unmodified or unconfidentialised data. The exact headers, counts and resource hashes are pinned in [bitre-2026-physical-schemas.json](../../catalog/acquisition/bitre-2026-physical-schemas.json), and the staging pipeline checks against this contract.

**M1.0 policy:** preserve every original count string, represent numeric disclosure-adjusted counts separately, and classify any nonnumeric count as unavailable, **not zero**. Never silently apply IPF as though all these numbers are hard controls. The report includes reconciliation residuals labelled *diagnostic only*.

## Running on your local downloads

After merging this PR into main, from the root of `InsuranceMarketAU` in Windows PowerShell:

```powershell
git pull origin main
py -3 -m pip install -e ".[data,dev]"
py -3 scripts/m1_ingest.py --profile-only
```

That profiles all **17 actual BITRE CSVs** in `data/raw/bitre/2026-01-31/`. It checks every source's known SHA-256, reads the source header and count statuses, collects total/count warnings, and compares national state/type sums across three projections. It writes a report to `data/reports/m1/bitre-2026-profile.json`. **No data are uploaded to GitHub**.

To write standardised Parquet staging tables after reviewing the source profile:

```powershell
py -3 scripts/m1_ingest.py --parquet
```

This writes a separate immutable-source Parquet staging file per BITRE projection to `data/processed/m1/bitre/2026-01-31/`. Each row carries its projection ID, source hash/release ID, original dimension JSON, exact source count string, nullable numeric count, disclosure-status marker, geographic role, and cautiously mapped canonical columns. Filenames include source hash prefixes; rows are processed in bounded batches.

For a fast pilot on three relatively small projections:

```powershell
py -3 scripts/m1_ingest.py --selected B26-01,B26-02,B26-03 --parquet
```

This produces an explicitly **partial** three-projection report, **not** a full release. The source list and hashes come from `catalog/acquisition/bitre-2026-acquired-metadata.json`, which records the files previously downloaded/verified on a GitHub runner.

## Outputs and controls

| Output | Content | Design status |
|---|---|---|
| `data/reports/m1/bitre-2026-profile.json` | Input hashes, physical headers, counts/zeros/suppressed/unrecognized, mapping warnings, state/type partial control comparisons | Operational first slice |
| `data/processed/m1/bitre/2026-01-31/b26-xx--hash.parquet` | Typed source lineage + one row per published aggregate source cell, *not* a vehicle instance | Operational with PyArrow |
| Summary workbook | BITRE Index, Tables 1–15 and explanatory notes | **Not yet parsed into hard benchmark controls** |
| `catalog/...bitre-2026-acquired-metadata.json` | Observed 17 resource identities and SHA-256 fingerprints from prior real download tests | Committed evidence metadata |

### Data-quality guards

- **Fail on missing/changed source bytes** rather than silently ingest a new revision.
- **Fail on unknown count column**, missing vehicle type field, malformed CSV row lengths or negative counts.
- **Preserve any unknown physical dimension** in `source_dimensions_json`; mark it for mapping review rather than guess.
- **Unknown disclosure string is not zero**. Keep raw count and review field-specific sentinels.
- **No stock/flow confusion**: this stage ingests BITRE registered stock only; NSW transactions/QLD transfers are not counted as fleet stock.
- **No spurious hard calibration**: reported cross-projection deltas are diagnostic, without inventing tolerance bounds.
- **No production release** until summary workbook control totals, licences, confidentialisation and geography mappings receive formal review.
- **No output raw data in public Git**: `data/` is excluded.

## Explicit next M1 sub-stages

**M1.1:** parse national BITRE summary workbook into authoritative state/class controls, inspect all 17 actual raw headers, flags and disclosure categories, and reconcile projection-level aggregates and overlapping margins. Add holdout diagnostics and source-date documentation.

**M1.2:** reconcile independent state tables (Victoria Q3 2026, NSW month-end, SA owner postcode, ACT suppressed counts, QLD 2022 reference), each at actual vintage, scope and geographic role.

**M1.3:** construct an explicit constrained sparse national joint distribution with uncertainty/sensitivity; benchmark computational scaling before generating any tens-of-millions-row vehicle-level files.

M1.0 intentionally does **not** create synthetic vehicles, a population release manifest, or a market model.
