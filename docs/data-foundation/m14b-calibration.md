# M1.4b — Capped soft calibration for the national synthetic fleet

**Status:** implementation of a candidate statistical calibration, subject to independent high-dimensional evaluation and commercial release gates. The original M1.3a and M1.3b models are **not overwritten**.

## Why we changed the model

M1.3a precisely preserved the published BITRE January 2026 state × vehicle class × manufacture year × motive-power accounting controls, but M1.3b assigned make/model and two postcode roles through separately published conditional distributions. The [M1.3b real-data independent audit](https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44862567592) found approximately **54% B26-14**, **155% B26-16** and **130% B26-17** WAPE against originally published **high-count aggregate cells (>=100)** in an 85,000-row weighted sample. These metrics do not measure individual-vehicle truth.

The [M1.4a seed sensitivity experiment](https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44874258572) demonstrated that more synthetic rows substantially improve coverage and reported error (B26-14 WAPE decreased from ~53.4% at 85k to ~41.3% at 120k). This means finite sampling matters; it does not prove the remaining discrepancy is purely sampling error.

## M1.4b method and source contract

This implementation adds **weight-only soft conditional calibration** as a separate model release candidate, rather than introducing unsupported new make/model/postcode combinations.

The original M1.3b sample already contains the attributes of each *fictional synthetic row* (state, class, year, fuel, make, model, postcode of registration, garaging postcode) and an expected fleet weight. The calibrator:

1. Requires the original M1.3b staged source registry, local SQLite source-conditioned index, **unchanged** synthetic rows and matching SHA-identified source manifest.
2. Retrieves publisher **conditional counts only for source categories present in the synthetic sample**, using a read-only indexed local SQLite query. Training is strictly restricted to **B26-15, B26-07, B26-05, B26-13, B26-08, B26-06, B26-04, B26-09**.
3. For each conditional publisher scope, compares the source's observed relative distribution among **comparable, supported** choices to the current weighted sample's distribution among those choices. A publisher cell must have numeric count >=10; the scope must have count >=100, at least two supported choices, and published-mass sample coverage >=15% before applying a soft correction. Missing keys and confidentialised numeric zeros are not structural zeros and are **not** forced to zero.
4. Runs four fixed rounds of damped conditional proportional updates with relaxation 0.35 and a bounded single-update multiplier of 1.6. Row weights are regularised to at most 8x or 1/8x their original values **before the four-way control reconciliation**; because that reconciliation follows the clamp, the bound is not an asserted exact final range.
5. **After every source family update**, rescales weights **within each original M1.3a state/class/year/fuel cell**, exactly restoring its initial expected mass. The national published accounting total **22,771,150** is therefore unchanged by design.
6. Writes a new synthetic-only candidate Parquet, its training-source fingerprint and a comparison of *comparable conditional training errors before and after*. These are **not** independent holdout errors, and the model is **never auto-promoted**.

Mathematically, with original four-way cell `g`, publisher conditioning scope `s`, and an already sampled category `c`, source share `p(c|s)` is calculated only over supported, eligible published choices. The current model share `q(c|s)` is updated by a bounded factor approximately `clip(p/q, 1/1.6, 1.6)^0.35`. The model is then projected back to the hard four-way expected masses `N_g`. Every dimension and original vehicle ID remain synthetic: no BITRE source rows are joined to real vehicle identities.

### Immutable data boundaries

| Model or data source | Treatment |
|---|---|
| M1.3a four-way national expected fleet | **Every cell preserved exactly** |
| Existing M1.3b 220k-row synthetic attribute sample | **Immutable baseline, remains explorer default** |
| B26-04/05/06/07/08/09/13/15 | Eight source-verified **training** soft conditional projections |
| B26-14/16/17 | **Strict independent holdouts**; not read by fit or parameter selection |
| Queensland historical VIN prefix, QLD flows, undated ACT files | **Not admitted to M1.4b** |
| Registered postcode vs garaging postcode | Different variables; pair association is not claimed observed |

The calibration has a major limitation: **it cannot create a model/year/postcode/fuel combination that was absent from the synthetic sample.** Even a lower training error does not prove that the rare classic/prestige market is correctly estimated. The independent holdout report shows both published-cell WAPE and the fraction of its published high-count keys represented in the sample; the latter cannot improve through weight-only fitting.

## Run locally on Windows

After PR #11 has been merged, use your existing M1.3b source data and synthetic Parquet files; no new download is required.

```powershell
cd C:\Users\gtx\source\repos\InsuranceMarketAU
git pull origin main
py -3 -m pip install -e ".[data,model,explore,dev]"

# Fit a separate candidate using only 8 training projections:
py -3 scripts/m14b_calibrate.py

# Separately evaluate the fixed baseline and fixed calibrated candidate
# against withheld B26-14/16/17 (staged in M1.0):
py -3 scripts/m14b_calibrate.py --validate-only

# Restart your unchanged Streamlit entrypoint:
py -3 -m streamlit run apps/m13_explorer.py
```

Stop the previous Streamlit PowerShell server with Ctrl+C before restarting it. Open the local URL printed (usually http://localhost:8501). Your sidebar gains a **Synthetic model weights** selector: baseline or calibrated candidate. The new **Calibration comparison** tab shows source-specific training scores, expected-mass preservation, and independent heldout WAPE for baseline versus candidate where the evaluation has run.

### Local output contracts (under git-ignored `data/`)

| Output | Meaning |
|---|---|
| `processed/m14b/calibrated-weighted-fleet.parquet` | Same synthetic attributes/row IDs as M1.3b, with only expected weights modified |
| `reports/m14b/calibration.json` | Model/parameter version, source SHA, immutable baseline SHA, hard four-way tolerances and soft training margin diagnostics |
| `reports/m14b/heldout-comparison.json` | **Paired same-row** B26-14/16/17 high-count published-cell WAPE, support coverage and older-vehicle cohorts |

The calibration layer does not upload data to the pricing engine, change any live rate, expose government microdata or publish a 22.77-million-row synthetic fleet.

## Calibration and promotion discipline

Training hyperparameters, update order and source coverage gates are **predeclared** and versioned in `catalog/calibration/m14b-policy.json`; we do **not** select parameters to optimise B26-14/16/17. The withheld comparison is intended to answer whether a conditional fitting change transfers to unseen published aggregate views. If the holdout fails to improve, or improvements are outweighed by increased rare-segment errors, retain M1.3b as the default and investigate new synthetic support, conditional dependence and source confidentialisation before a broader release.

The **correct commercial next step is not market-share forecasting yet**. Investigate the high-dimensional independent residuals for old vehicles, rare makes and postcode intersections, then produce a properly documented candidate synthetic population with uncertainty ranges, source licence/privacy review and downstream data contracts before feeding a pricing or choice simulator.

## First real-source M1.4b result — mixed, not release-ready

The [completed official-source training and three-holdout audit](https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44962288896) built the baseline 85,000-row weighted sample with seed 42, recalibrated it **without touching its attributes or original base expected masses**, and then evaluated exactly the same synthetic row support against independently withheld publisher projections. Maximum difference in an original four-way cell was **3.5 × 10^-10 expected vehicles**.

| Held-out projection (published cells >=100) | Unmodified M1.3b WAPE | M1.4b candidate WAPE | Candidate minus baseline |
|---|---:|---:|---:|
| B26-14 — class/year/fuel/make/model | 53.98% | **47.77%** | -6.21 percentage points |
| B26-16 — class/state/registration postcode/year/make | 154.97% | **175.87%** | +20.90 percentage points |
| B26-17 — class/state/registration postcode/fuel/make/model | 130.39% | **141.33%** | +10.94 percentage points |

The candidate *improved* all eight comparable **training** conditional objectives, but **worsened both high-dimensional registration-postcode holdouts**. The fraction of published high-count cells represented by the 85,000-row sample remained only 43.26% (B26-14), 13.60% (B26-16) and 17.07% (B26-17). Because M1.4b reweights existing rows, it cannot increase this source-key coverage.

**Conclusion:** fitting published training margins better does not automatically generalise to independently published location/model relationships. The M1.3b baseline remains the Streamlit default, and neither model is a validated commercial postcode-level synthetic population. The M1.4b result should be used for model-method research, not market-size or pricing decisions. We should next examine source support, coarse geographical hierarchies and alternative joint sampling approaches; any further improvements must use fresh validation design rather than tuning parameters on the already consulted B26-14/16/17 holdouts.

Full versioned evidence and independent source SHAs are in `catalog/calibration/m14b-verified-pilot.json`. These published-cell WAPEs are NOT measures of true individual-vehicle prediction error.

