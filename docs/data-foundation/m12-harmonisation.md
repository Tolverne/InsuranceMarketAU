# M1.2 — State-source harmonisation and quality gates

**Status:** source-aware ingestion and harmonisation of the separately published jurisdictional data files. This is **not** a calibrated national fleet or verified source equivalence to the BITRE January 2026 universe. The canonical registered motor-vehicle benchmark remains the 22,771,150 BITRE publication estimate from M1.1.

## Why sources must be partitioned rather than joined

| Evidence | Source observation period | Geography / grain | Data-quality limitation |
|---|---|---|---|
| BITRE national (M1.0–M1.1) | 31 January 2026 | State, registered or garage postcode, class, fuel, year, make and model in distinct aggregate projections | Confidentialised; population denominator published as 22,771,150 |
| Victoria by postcode | Q3 2026, 30 September | **Garaging postcode**, source vehicle-class code, make, manufacture year, fuel code | Source class codes not yet approved as BITRE classes; **no model column** |
| Victoria by model | Q3 2026, 30 September | Make, model, colour; no postcode/year | Do not row-join to Victoria postcode data |
| NSW registrations snapshot | Monthly source partitions 2026-01 through 2026-10 | **Customer address LGA**, category, make, year, fuel, transmission, colour and shape | ZIP has **30 split monthly CSVs**; includes trailers; many counts published as `<=5` |
| NSW usage / heavy configuration | Monthly 2026 | Customer address LGA, distinct publisher categories | Subsets of NSW snapshot, not additions to stock |
| NSW registration transactions | Monthly 2026 | Customer address LGA, registration and transfer activity | **Flow only**, not registered stock; never add to stock |
| South Australia | 30 June 2026 | **Owner postcode**, make, body, cylinders, year | Includes trailers; owner postcode can be interstate. Mirror is excluded if official file exists |
| ACT | Row-specific 'Data as at' | Published suburb, make/model, emissions category | Includes trailers and motorcycles; small counts <=10 may be suppressed. Manual official CSV supported |
| Queensland historic registration | 10 October 2022 | Raw source categories, physical record grain not yet approved | May contain detail-level records. **Never assume one row equals one vehicle** |
| Queensland new/transferred | 2026, precise row-date coverage requires profiling | Publisher specific fields | **Flow only**, never stock |
| WA, Tasmania, NT | No new local granular dataset in M1.2 | Continue to use BITRE registered-state estimates | Do not claim those jurisdictions are missing from national data |

The publisher's source-of-registration, garaging postcode, customer LGA, owner postcode and reported suburb do **not** describe the same geographical variable. A postcode outside SA in the SA owner address does not mean the vehicle should automatically be reclassified as interstate registered.

## Implemented processing

The machine-readable source contract at [M1.2 source registry](../../catalog/harmonization/m12-sources.json) pins verified headers for VIC, SA and NSW, and declares unresolved source fields/grain for QLD. The pipeline resolves previously-downloaded files using git-ignored acquisition reports, recomputes SHA-256 checksums, and refuses changed headers or incorrect ZIP members. It recognises the ACT manual file previously downloaded with PowerShell and avoids duplicated SA source/mirror bytes. It excludes the known-bad NSW age ZIP.

Each source is processed separately using bounded-memory readers. CSV and CSV members of ZIPs are decoded with publisher delimiters (comma or pipe), with original source member and row lineage retained. NSW monthly member dates are reconstructed from the embedded publisher YYYYMM filenames; files belonging to the same month can be considered the same month's partitions, **but different months are never summed into a stock count**.

Published point counts and count intervals are separate:
- Numeric 0 stays a *published* zero, not a structural zero.
- Displayed <=5 in NSW becomes point-count NULL, **lower 0, upper 5** for that *published cell*; ACT <=10 is treated similarly when explicitly shown.
- Missing/unrecognized count cells are not imputed or set to zero.
- The combined lower/upper sums are for *published rows only*, not certified state fleet population bounds.
- Where physical row grain is unverified, such as QLD, no vehicle count is inferred from row count.

Optional Parquet staging contains original-source dimensions that have an explicitly documented meaning, type-safe counts and bounds, publisher class codes, geography, source hash/member/row/date and a `not_mapped_no_approved_source_crosswalk` status rather than falsely asserting exact BITRE classification.

## Running locally after merging PR #7

All required source files are already downloaded on your computer; **do not re-download them**.

    cd C:\Users\gtx\source\repos\InsuranceMarketAU
    git pull origin main
    py -3 -m pip install -e ".[data,dev]"

    # First inspect small source groups (does not create Parquet):
    py -3 scripts/m12_harmonise.py --groups vic,sa,act --profile-only

    # Test NSW with a bounded sample from each ZIP member:
    py -3 scripts/m12_harmonise.py --groups nsw --only-source nsw_usage_2026 --sample-rows 100 --profile-only

    # Full profiles of all state sources (can be lengthy):
    py -3 scripts/m12_harmonise.py --groups vic,nsw,sa,act --profile-only
    py -3 scripts/m12_harmonise.py --groups qld,qld_flows --profile-only

    # Optional typed staged outputs:
    py -3 scripts/m12_harmonise.py --groups vic,sa,act --parquet
    py -3 scripts/m12_harmonise.py --groups nsw --parquet

A source-profile JSON and a separate per-jurisdiction **coverage-matrix.json** are written under **data/reports/m12/**. The matrix preserves all eight national BITRE state controls, identifies locally available supplemental stock vs flow evidence by date/geography, and distinguishes states with BITRE-only evidence from states not selected in a partial run. Sampled runs write **source-profile-sample.json** and are explicitly labelled partial. Successful Parquet files are written under **data/processed/m12/stock/** and **data/processed/m12/flow/** and remain excluded from Git.

**Note:** the source-profile JSON is replaced on each non-sampled invocation. Save reports that you want to compare across runs under distinct local filenames. The QLD full-grain profiler may take longer because its historical files are large; Parquet staging for QLD is optional until the source-grain review is complete.

## Quality gates and M1.3 hand-off

1. Input checksum and physical headers must match an acquisition or manual verified reference.
2. Monthly NSW stock files must retain month-end partition identities, with overlapping stock/flows kept separate.
3. Official SA takes precedence over a byte-equivalent third-party mirror; NSW age stays quarantined.
4. All output geography roles, vehicle categories, numeric count statuses and source periods must remain explicit.
5. The M1.1 BITRE reference benchmark is included for context **but no automatic direct equality or age-adjusted extrapolation is asserted**.
6. Unknown QLD record grain, ACT total coverage, crosswalks from VIC/NSW publisher vehicle codes to BITRE class, and licensing require formal review before source-weighted synthesis.

M1.3 will choose validated soft constraints and build the sparse national joint distribution with uncertainty and held-out evaluations; do not interpret this M1.2 output as real vehicle-level microdata.
