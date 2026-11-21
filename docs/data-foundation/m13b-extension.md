# M1.3b — Make/model and postcode filters for the synthetic fleet explorer

**Status:** exploratory conditional inference, not an observed joint registration file or an insurer-risk population. Works with the January 2026 BITRE data already acquired and staged in M1.0.

## New interactive filters

The existing Streamlit command (apps/m13_explorer.py) now automatically opens the M1.3b view when the local weighted synthetic sample is present; otherwise it retains the original M1.3a interface. Users can select **registration state, BITRE vehicle class, manufacture year, motive power, make, model, registration postcode and garaging postcode**. Analysis includes weighted vehicle-count estimates, sample row count and effective sample size (ESS), with warnings for rare selections.

There are two distinct source geographies: registration postcode and **garaging postcode**, which may include a publisher fallback. They are not interchangeable, and their relationship within a particular synthetic row is **inferred, not directly observed**.

## Conditional model

The original M1.3a **state × vehicle class × manufacture year × motive power** model is preserved exactly, in expected aggregate weight. Its original positive support cells are allocated at least one synthetic row each, and additional rows are allocated in proportion to expected population. Each synthetic row receives the fraction of its parent expected mass. The total remains the published 22,771,150 national accounting benchmark, with no source record linkage.

Separate BITRE source projections support the extra attributes:

| Training projection | Published conditioning dimensions | Sampled attribute |
|---|---|---|
| B26-15 | state/class/year × make/model | make, model |
| B26-07 | class/year × make/model | make/model fallback |
| B26-05 | class/fuel × make/model | fuel-affinity adjustment/fallback |
| B26-13 | state/class/make/model × registration postcode | registration postcode conditioned on model |
| B26-08 | state/class/year × registration postcode | age-conditioned registration postcode |
| B26-06 | state/class/fuel × registration postcode | fuel-conditioned registration postcode |
| B26-04 | state/class × registration postcode | broad registration-postcode fallback |
| B26-09 | state/class/fuel × garaging postcode | separate garaging postcode |

Every source is checked against its pinned 2026 release SHA, reference date, source row order, expected physical rows, and national published detail sums, before indexing it separately in local SQLite. All publisher total rows are excluded. A published numeric zero does not mean a genuine structural zero. Fallbacks for missing conditional groups are recorded in the validation report.

The approximation can be written as a product of the fitted four-way base N(state,type,year,fuel) and conditional make/model, registration postcode and garaging postcode distributions. These conditional factors are constructed from **different projections**; their combined joint association is not observed. Exact national/state/class/year/fuel weighted marginals do not mean exact make/model/postcode combinations.

## Independent holdout checks

Three detailed projections are excluded from source conditioning and sampling:

| Holdout | Unseen published dimensions |
|---|---|
| B26-14 | vehicle type, year, fuel, make, model |
| B26-16 | vehicle type, state, registration postcode, year, make |
| B26-17 | vehicle type, state, registration postcode, fuel, make, model |

Optional heldout validation compares synthetic weighted estimates with **published cells of at least 100**, and reports WAPE and the number of published groups not represented in the finite sample. This deliberately excludes the millions of low-count/suppressed cells and is **not** vehicle-level truth, an unbiased model-error estimate, or a confidence interval.

The explorer warns if a filter has fewer than 30 synthetic rows or ESS below 30. ESS quantifies only Monte Carlo sampling information; it does not cover omitted vehicle relationships, publication confidentiality adjustments, or potential administrative-source bias.

## Run locally after merging

Keep your existing M1.0 and M1.3a files. There are no new downloads required.

    cd C:\Users\gtx\source\repos\InsuranceMarketAU
    git pull origin main
    py -3 -m pip install -e ".[data,model,explore,dev]"

    # Build the eight indexed conditional source tables once, then 220k
    # reproducible weighted synthetic analysis rows:
    py -3 scripts/m13b_expand.py --rows 220000 --seed 42

    # Same browser explorer command as M1.3a:
    py -3 -m streamlit run apps/m13_explorer.py

Stop any already-running Streamlit PowerShell session with Ctrl+C before launching the updated code. Open the locally displayed URL (normally http://localhost:8501). The terminal should remain open while the local app runs.

For the independent source comparison:

    py -3 scripts/m13b_expand.py --validate-only

That command uses already-staged B26-14/16/17 source Parquet, which M1.0 produced when all 17 were ingested. It does not change the sample and does not use the holdout in fitting. Choose more rows for better Monte Carlo resolution but not as a substitute for modelling source uncertainty.

## Local output

- data/processed/m13b/conditionals.sqlite — indexed published source-specific conditional counts, **not** linked microdata.
- data/processed/m13b/conditionals-manifest.json — release checksums/source row counts; source revision requires deliberate recataloguing.
- data/processed/m13b/weighted-synthetic-fleet.parquet — synthetic analysis rows with expected vehicle weights, no original vehicle identifiers.
- data/reports/m13b/validation.json — lineage, weights, unknown/fallback counts, optional heldout residuals.

Files remain excluded from Git; the application does not upload them anywhere.

## Model limits and next acceptance gates

This release provides a rich **POC analytical viewer**, not a claimed exact synthetic Australian vehicle census. Inferred make/model/year/fuel and registration/garaging postcode combinations can be materially inaccurate for rare classic/prestige vehicles. The appropriate next work is source-marginal soft calibration, low-count model and geographic validation, sensitivity/uncertainty ensembles, registration-stock to insured-demand modelling, and a license/privacy review before any national record-level release.

The 2022 Queensland vehicle-like tables include VIN Prefix and have an unverified individual-record grain; QLD 2026 transaction data are flows. ACT's 6,940 rows still have no parsed observation date. None of these state sources was treated as a January 2026 BITRE hard constraint.
