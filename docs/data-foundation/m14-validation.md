# M1.4a — Independent model diagnostics and Monte Carlo sensitivity

**Status:** diagnostic milestone, not a recalibrated or commercially approved national population.

## Background and motivation

M1.3a's state × vehicle class × manufacture year × fuel expected counts reproduced the national BITRE January 2026 accounting anchor of 22,771,150. However, the full M1.3b high-dimensional real-source audit identified significant discrepancies in the additional model/geography combinations. In the 85,000-row weighted sample, WAPE on *published cells with count >=100* was **53.98%** (B26-14, type/year/fuel/make/model), **154.97%** (B26-16, state/registered-postcode/year/make) and **130.39%** (B26-17, state/registered-postcode/fuel/make/model). The pre-1980 B26-14 published-cell WAPE was about **97.24%**. Source audit: https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44862567592.

These percentages are comparisons with *confidentialised publisher projections*, not an independent vehicle-level census. Finite Monte Carlo sampling, original disclosure adjustments, omitted joint dependencies, and the existing model's conditional fallbacks can all contribute. Large errors are an important warning before pricing or market-size decisions.

## What M1.4a implements

**Current-sample diagnostics (B26-14 only).** B26-14 is not used by M1.3b's source-conditioned sampler. The diagnostic rereads the separately staged publisher projection, revalidating source release ID, SHA contract, observation date, physical row numbers and published source detail sums. It only compares originally published numerical source cells >=100, keeping suppressed or missing categories distinct from true structural zeros.

**Strict sample invariants.** Every synthetic row must be labelled synthetic with a positive finite expected vehicle weight; every positive base M1.3a state/class/year/fuel cell must retain its expected population mass. Checking only that a national 22.77m total adds up is insufficient. A changed base cell, missing source cell, or stale model report causes validation to stop.

**Disaggregated errors.** The report includes overall published-cell WAPE, signed bias, published-cell coverage, sample size and mass, median and 90th-percentile absolute cell errors, and disjoint age-band, vehicle-class, source-count-band, make and historic-make summaries. It also reports overlapping before-1980, before-1990 and before-2000 cohorts. Never add these overlapping cohorts together. The public make summaries require >=3 included publisher cells and >=1,000 total published reference count; no individual source record, suppressed cell or VIN is exported.

**Seed and sample-size sensitivity.** Using a *fixed model* with predeclared random seeds and sample sizes, the workflow produces alternate weighted synthetic samples in independent data/processed/m14/replicates files. It evaluates them against B26-14 without rewriting the current M1.3b explorer sample and deletes temporary replicate Parquet by default. Source holdout is not consulted during sample generation. Results include mean and population standard deviation *across seeds* for high-dimensional WAPE, published-cell coverage and classic-vehicle cohorts. This standard deviation reflects only *finite sampling variation*, not uncertainty about true insured market counts.

**Streamlit model diagnostics tab.** The existing fleet explorer command automatically reveals the new source comparison panel. It shows modelled versus published counts for age bands and major makes, historic-vehicle accuracy, sample coverage and optional across-seed sensitivity.

## Windows PowerShell

After PR #10 is merged, reuse the source files and weighted sample you already generated:

    cd C:\Users\gtx\source\repos\InsuranceMarketAU
    git pull origin main
    py -3 -m pip install -e ".[data,model,explore,dev]"

    # Read-only independent diagnostic of the current M1.3b sample
    py -3 scripts/m14_validate.py

    # Optional: sample-size/seed sensitivity, no changes to baseline explorer data
    py -3 scripts/m14_validate.py --sensitivity --sizes 85000,220000 --seeds 17,53,91

    # Restart your local explorer (Ctrl+C in the old PowerShell)
    py -3 -m streamlit run apps/m13_explorer.py

Existing M1.0 Parquet for B26-14 is required; no source redownload or separate sign-in is needed if the full original BITRE staging was completed.

Reports under ignored local directories:

| Path | Description |
|---|---|
| data/reports/m14/current-diagnostics.json | Source hash, current sample fingerprint, strict four-way balancing check, age/class/make B26-14 published-cell residuals |
| data/reports/m14/sampling-sensitivity.json | Predeclared sample sizes/seeds, reproducible errors and across-seed Monte Carlo spread |
| data/processed/m14/replicates | Optional retained synthetic replicate files; deleted by default |

The existing local files data/processed/m13b/weighted-synthetic-fleet.parquet and data/reports/m13b/validation.json are not modified by these commands.

## Acceptance and calibration next steps

1. **Evidence integrity:** publisher release date, SHA/lineage and physical row checks pass, and all original four-way base cells are reproduced.
2. **Sampling uncertainty:** compare multiple independent fixed-model replicates, record WAPE and coverage at each sample size, and measure variations in older-car segments. Do not treat seed-to-seed spread as a confidence interval for the real fleet.
3. **Model discrepancy:** investigate persistent high-dimensional residuals after accounting for Monte Carlo variability. Publisher disclosure means discrepancies cannot be fully attributed to one error source.
4. **Classic/prestige segments:** explicitly require sufficient source coverage before claiming addressable-market estimates by rare make/model/postcode.
5. **M1.4b calibration:** replace/augment the current conditional mixtures with source-compatible, disclosure-aware soft calibration and smoothing, fitting **only** the original M1.3b training projections B26-04/05/06/07/08/09/13/15. Reserve B26-14/16/17 as tests. Retain the original M1.3a four-way accounting controls and distinguish registered from garaging geography.

M1.4a is diagnostic research. It **does not** certify the national synthetic population, create a 22.77-million-record release or imply that registered vehicles equal potential insured customers.
