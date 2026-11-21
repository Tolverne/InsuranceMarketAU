# M1.3a — Australian synthetic vehicle-joint reconstruction

## Scope and status

This is the first working **statistical reconstruction** from the BITRE January 2026 registration foundation. It estimates 64,008 synthetic expected-population cells over **state of registration × BITRE vehicle class × year of manufacture × motive power**, calibrated to the publisher Table 1 state/class accounting benchmarks. This is a modelling pilot, not yet a complete make/model/postcode vehicle-level fleet or insurable-risk population.

The published national accounting total is 22,771,150 motor vehicles. These are *registered vehicles*, not vehicles insured by a particular product. State and class benchmarks are used as hard *operational balancing controls* in this pilot, but are BITRE publisher estimates, not guaranteed physically exact counts.

## Training, holdout and mathematical approach

| Publisher source | Observable dimensions | Usage |
|---|---|---|
| BITRE summary workbook Table 1 | State and ten motor-vehicle classes | Operational state/class accounting anchors, exactly balanced |
| B26-01 | State × class × year of manufacture | Disclosure-affected soft fitting margin |
| B26-02 | Class × year of manufacture × motive power | Disclosure-affected soft fitting margin |
| B26-03 | State × class × motive power | Disclosure-affected soft fitting margin |
| B26-10 | State × class × year × motive power | **Strict holdout**, never used to construct support, prior, fit or tune parameters |

Each positive workbook state/class benchmark is distributed over the cross-product of available *training* year/fuel categories. The starting state/class conditional prior is the product of the year and fuel marginal distributions, using national type-level backoff and positive pseudocounts. This explicitly avoids treating omitted joint combinations or disclosure-adjusted zero cells as structural impossibilities.

The implementation then runs a fixed number of **damped alternating proportional fitting** iterations: each of the three published soft-margin targets adjusts the weights by a bounded multiplicative factor. A state/class normalisation is applied after every update to keep the publisher accounting controls balanced. Published source cells do **not** become exact hard constraints. It is an interpretable engineering method, **not** a likelihood estimated from BITRE's unpublished suppression/perturbation mechanism, and it does not establish a unique global optimum.

A separately published B26-10 projection serves as an excluded, four-dimensional holdout. Weighted absolute percentage error (WAPE) is calculated on published aggregate cells. Both baseline and fitted WAPE are reported. Source zeros are disclosure affected, and the holdout is not actual vehicle microdata; therefore these are published-projection diagnostics rather than individual-vehicle prediction errors.

## Verified first national test

The [real BITRE national calibration CI test](https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44860333642) succeeded using four real source files and the workbook. It reproduced the following:

| Quality metric | Measured result |
|---|---:|
| Synthetic joint-support cells | 64,008 |
| Sum of fitted synthetic expected registrations | 22,771,150 |
| Initial held-out B26-10 WAPE | 22.10% |
| Calibrated held-out B26-10 WAPE | 2.01% |
| Held-out published cells with count >=100, WAPE | 1.91% |
| Held-out B26-10 unsupported published groups | 0 |
| State/class operational accounting total error | Below 0.00001 vehicles |

The historic fleet is particularly important for the classic/prestige motor pricing business. Using published holdout cells, the calibrated model obtained:

| Historic manufacture-year group | Published B26-10 aggregate cell total | Held-out WAPE |
|---|---:|---:|
| Before 1980 | 256,482 | 2.95% |
| Before 1990 | 440,805 | 4.31% |
| Before 2000 | 1,193,368 | 5.35% |

These vehicle totals refer to the *published holdout-cell sums* under the stated manufacture-year filters; they are not validated classic-car addressable markets or eligibility estimates. Smaller, rare make/model strata are **not yet validated** by this four-attribute model. The historic cohorts overlap (before 1980 is contained within before 1990, etc.) and must not be added together.

## Running locally after merging PR #8

Existing M1.0 Parquet data and M1.1 workbook controls provide all source files for this stage. Your M1.2 state files are not needed for fitting because their dates, administrative universes and geographical semantics remain different.

    cd C:\Users\gtx\source\repos\InsuranceMarketAU
    git pull origin main
    py -3 -m pip install -e ".[data,model,dev]"

    # Fitted expected four-way distribution, without individual sample rows:
    py -3 scripts/m13_fit.py

    # Optional reproducible 25,000-record synthetic-only illustration:
    py -3 scripts/m13_fit.py --sample-size 25000 --seed 42

The generated local, Git-ignored files include:

- data/reports/m13/pilot-validation.json — source lineage, published controls, training and heldout diagnostics, historic-cohort WAPE.
- data/processed/m13/joint-state-type-year-fuel.parquet — expected number of vehicles in each four-way synthetic aggregate cell; fractional values allowed.
- data/processed/m13/synthetic-pilot-n25000-seed42.parquet — optional *fictional* generated sample, with synthetic IDs and no VIN, address, postcode or personal record keys.

### Local interactive analytic viewer

    py -3 -m pip install -e ".[data,model,explore]"
    py -3 -m streamlit run apps/m13_explorer.py

This produces an interactive local page for slicing the four-way expected fleet by state, vehicle class, fuel and manufacture year, with historic holdout diagnostics. It does not host, upload or share any raw government file.

## Prior-source qualifications from M1.2

- **Queensland 2022**: eight files contain manufacture year/make/model/body/fuel and other vehicle-like characteristics, but no count column; a ninth is explicitly aggregated postcode/suburb/state/count. Those eight source parts may consist of unit-like entries. Grain and privacy/rights must be reviewed *before* inferring one vehicle per row. VIN Prefix must not enter a public synthetic vehicle export. These October 2022 observations are not January 2026 controls.
- **Queensland 2026 flow files**: have transaction date, identifier, registration/transfer type and make/model attributes; they are *flows*, not registered stock and cannot be added to the historical fleet.
- **ACT**: all 6,940 M1.2 rows have unparsed observation dates. They remain undated supporting evidence; ACT was **not** calibrated against January 2026.
- **Victoria September 2026**, **SA June 2026**, **NSW January–October 2026**: source dates, scope, geography and disclosure differ from BITRE. M1.2 retains their provenance; they were not forced into the January 2026 sample.
- NSW vehicle age download is known to contain heavy-vehicle configuration records and is quarantined.

## Why M1.3 is not complete

The full synthetic auto-insurance market needs make/model and location, which are not observed jointly in the same published detailed BITRE table for all required attributes. M1.3b should add conditional factorization using B26-05/07/14/15/16/17 and postcode views B26-04/06/08/09/11/12/13, without inventing per-vehicle record linkage. Holdout rare model/year and state/postcode accuracy, date sensitivity, source rights, perturbation uncertainty, and cohort-level privacy thresholds are necessary release gates.

The source-derived output is **not** a synthetic 22.77 million row dataset. Its expected 22.77 million vehicle mass is represented in 64,008 fractional support cells. Once validated make/model/geography joins, sensitivity ensembles and privacy conditions are approved, an extended synthetic individual-vehicle fleet release can be implemented.
