# M1.5 — Immutable local population releases and downstream feature port

**Stage:** executable local-first research release mechanism. This is not a physical census, not a production insurance market, not a policyholder registry, and not a commercial or data-distribution approval.

## Motivation and architectural decision

M1.3b and M1.4b are research implementations and can be updated repeatedly. The downstream insurance-enrichment and competitive simulation layers must be able to use a **frozen version** of the population without adopting a specific model's internal algorithms or having historical scenarios silently change when the analyst revises a population.

M1.5 introduces an explicit **population-release boundary**:

```text
BITRE controls + M1.3a model
           |
       M1.3b fixed-seed sample ----- M1.4b reweighted candidate (optional)
           |                                |
      publish baseline                  publish candidate
           |                                |
           +------------+-------------------+
                        |
        data/releases/population/<release_id>/
            manifest.json
            quality-report.json
            fleet-state.parquet
            fourway-controls.parquet
                        |
             PopulationStore(release_id)
              |          |           |
             M2         M3        M4–M7
        enrichment   segments   pricing/simulation
```

No model implementation is imported by the downstream population-consumer class. The publisher imports the older models strictly to verify provenance and accounting controls. A research model can be refined and republished as a **new release ID** without invalidating old M2/M3/M4 scenario dependencies.

**Do not create a mutable `latest` pointer, alias or auto-promotion path.** Analysts explicitly select a model version or supply a pinned dependency.

## A research release is a snapshot, not a certification

The existing `contracts/schemas/population-release.schema.json` defines `status: published` as a valid metadata lifecycle state. M1.5 uses this to mean **frozen, locally published research data**. It does **NOT** mean the model has been independently certified, that source redistribution rights are established, or that the synthetic fleet represents insurable risks.

Every quality report includes explicit `commercial_pricing_use_approved: false`, `vehicle_level_truth_confirmed: false`, `make_model_postcode_associations_empirically_verified: false`, and `licence_and_privacy_review_approved: false`.

The M1.4b [real-world calibration audit](https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44962288896) improved B26-14 published-cell error while worsening the independently held-out **registered postcode** source views B26-16/17. Both model versions therefore remain research samples. No hard-coded historical 85,000-row error number is copied onto a different seed/size release. **Quality flags are assertions about what has actually been verified**, not empty stamps of approval.

## Frozen files and manifest integrity

Each release is stored in **Git-ignored local data**:

```text
data/releases/population/
  pop-20260131-<24 content-hash hex characters>/
    fleet-state.parquet
    fourway-controls.parquet
    quality-report.json
    manifest.json
```

The manifest is validated against the existing JSON Schema 2020-12 release contract. It records reference date, physical dataset schema version, published source IDs, expected synthetic row counts and total weights, model method/version, M1.3b random seed and model draw ID, `SHA-256` for each Parquet file, and a release-content SHA-256 fingerprint.

A canonical content fingerprint includes the frozen synthetic dataset hash, frozen M1.3a four-way controls hash, source model report fingerprint, source publication SHA identifiers, parameters/seed and the quality evidence hash. This yields a repeatable content-addressed release ID. Timestamps are metadata and do not determine identity.

**Publication algorithm:** verify both source model lineage and original four-way cells → create a random temporary sibling directory → byte-copy assets with SHA checks → atomically rename the complete directory to its final release ID. If the release ID already exists, verify all files and return that same release; never overwrite it. If the existing ID has been tampered with, abort rather than repair silently.

**Read verification:** validates the release JSON Schema and known relative paths, rehashes frozen assets, checks the pinned quality digest, scans the Parquet physical schema and positivity/synthetic status, verifies **all original M1.3a state × type × year × fuel cell masses** and national accounting weight. It requires no external network and **does not need the original source model Parquet or the M1.3a fitter after publication**.

This is **content-addressed, corruption-detecting immutability**, not an operating-system write-protection, digital signature, or multi-tenant access-control system. Anyone who controls the file system may erase releases. Durable object-store versioning, signatures and role-based permissions belong to a later deployment milestone.

## Published data contracts

`fleet-state-weighted-v1` is the exact M1.3b/M1.4b frozen Arrow schema:

| Field | Semantic type | Notes |
|---|---|---|
| `synthetic_row_id` | int64 | Release-local generated row identity; **not** VIN/rego or a durable identity across independently generated releases |
| `registered_state` | string | Source-published registration jurisdiction |
| `vehicle_type` | string | BITRE vehicle class |
| `manufacture_year` | string | Published year category, can have unclassified labels |
| `motive_power` | string | Published fuel/power category |
| `make`, `model` | string | Synthetic categorical assignment, not original vehicle-level observation |
| `registered_postcode` | string | Registration locality, **not** a garaging address |
| `garaging_postcode` | string | Separately inferred garaging locality; no observed postcode pair |
| `expected_vehicle_weight` | float64 | Positive expected registration accounting mass represented by one synthetic row; not exposure years |
| `is_synthetic` | bool | Must always be `true` |
| `uncertainty_kind` | string | Indicates conditional Monte Carlo inference and lack of observed cross-tab linkage |

For M2 onward, `PopulationStore.iter_feature_view()` exposes a versioned **`market_vehicle_base_v1`** typed Arrow RecordBatch with `synthetic_vehicle_id` and `sampling_weight` aliases and explicit `population_release_id` / `reference_date` fields. The source field identity and weight unit are documented in `contracts/feature-views/market_vehicle_base_v1.json`. No premium, driver, owner, value, annual km or insurer underwriting feature is silently imputed here: those belong to M2 and its own versioned feature views.

The downstream scenario dependency object is `population-selection-v1` (`contracts/schemas/population-selection.schema.json`): exact release ID, asset and release-content SHA, weighted representation, accounting count, sample rows, dataset version, reference date and explicit research-only status. Future M5–M7 runs should pin it in their scenario/experiment metadata, and fail if it cannot be matched.

## Windows PowerShell runbook

After merging PR #12, reuse existing M1.3a/b data; **no new source download or regeneration is needed.** You only need to generate M1.4b if you want to freeze its experimental candidate too.

```powershell
cd C:\Users\gtx\source\repos\InsuranceMarketAU
git pull origin main
py -3 -m pip install -e ".[data,model,explore,dev]"

# Publish and verify the safe baseline, without modifying its working Parquet:
py -3 scripts/m15_release.py --publish baseline

# Optional — if M1.4b candidate is already present/current:
py -3 scripts/m15_release.py --publish candidate

# Or publish both when available:
py -3 scripts/m15_release.py --publish both

# Discover frozen local research releases:
py -3 scripts/m15_release.py --list

# Copy one returned exact release ID into this variable:
$RID = "pop-20260131-PASTE_THE_24_HEX_CHARACTERS_FROM_LIST"

# Check immutable sample, proof SHA and every original four-way cell:
py -3 scripts/m15_release.py --verify $RID

# Obtain a JSON dependency pin for a future scenario:
py -3 scripts/m15_release.py --pin $RID

# Read aggregate fleet estimates from a frozen release:
py -3 scripts/m15_release.py --aggregate $RID --group-by registered_state
py -3 scripts/m15_release.py --aggregate $RID --group-by make --filter registered_state=Qld
```

To launch the same explorer as M1.3b/M1.4b, stop the existing process with Ctrl+C and run:

```powershell
py -3 -m streamlit run apps/m13_explorer.py
```

Open the printed local URL, usually `http://localhost:8501`, then the new **Population releases** tab. Select a frozen ID, inspect weighted class/state/make counts and quality gates, and export the pinned dependency JSON. This is separate from the older in-memory baseline-vs-calibrated model selector.

## Python integration example

```python
from insurance_market_au.population import PopulationStore

# Caller/analyst explicitly chooses the exact version, never 'latest'.
release_id = "pop-20260131-REPLACE_WITH_A_REAL_24_CHARACTER_HEX_ID"
population = PopulationStore(release_id)

# Future scenario manifest stores this exact dependency.
population_pin = population.pin()

# Typed Arrow RecordBatches for the M2 feature builder.
for batch in population.iter_feature_view(
    filters={"registered_state": "Qld"},
    batch_size=25000,
):
    # batch has synthetic_vehicle_id, sampling_weight,
    # population_release_id, source categories and uncertainty indicators.
    pass

# Read-only weighted segment report with synthetic-support diagnostics.
report = population.aggregate(
    group_by=("registered_state", "vehicle_type"),
    filters={"motive_power": "Petrol"},
    max_groups=50,
)
```

This port uses batch scanning and weighted group-by processing rather than materialising a 22.77-million-record real-vehicle register. A filter returning zero synthetic rows does not prove no actual vehicles exist in that segment, and the reported effective sample size is a measure of weighted Monte Carlo support, not an uncertainty interval for a market size.

## Acceptance, regression and governance

- Baseline and calibrated candidate publish under **different version IDs**, even when the sampled vehicle identities are the same.
- Repeating a release publication with identical inputs is **idempotent**.
- Changing the source sample/seed/algorithm/report produces a **new ID**; old releases remain readable and verifiable.
- Altering an asset or metadata after publication is **detected and refused**.
- Missing or additional four-way cells, nonfinite/zero weights, duplicate generated row IDs, swapped postcode/feature schemas or non-synthetic rows fail before release.
- M1.4b release must prove original M1.3b sample SHA agreement and preserve **all non-weight columns** exactly, and must retain the original holdout-source isolation flags.
- No release is labelled commercially approved, even when the data-integrity and accounting tests pass.
- Consumer queries require explicit IDs and cannot read arbitrary file paths or query unknown columns; a data version cannot silently switch.
- The existing M0 population-release JSON Schema still validates all manifests; the new population-selection contract supports future scenario bindings.
- Unit/fixture CI uses synthetic, intentionally non-identifying rows. Full real-BITRE smoke test is recorded separately and retains only **aggregate metadata**, never source or synthetic vehicle Parquet as GitHub Actions artifacts.

### Future improvements

M2 introduces `enrichment_release_id`, feature-model versions, insurer/driver/ownership attributes and explicit conditional uncertainty. M3 can use pinned population assets for segment research. M4–M7 must record population, enrichment, participant, pricing and behavioural model versions plus the random stream for any scenario replay.

When the underlying national synthesis is improved (larger support, more accurate location relationships, new official release), create another M1 population release and compare scenario outputs **with all other assumptions held constant**, rather than editing an earlier release.

## First successful official-source acceptance run

The [successful M1.5 authentic BITRE audit](https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44966800111) reconstructed the January 2026 weighted model, froze **85,000-row** M1.3b and M1.4b research samples independently, verified all **64,008** original four-way mass cells for each, exercised the hash-checked read-only feature port and confirmed idempotent publication. The registry recorded approximately **22,771,150 expected vehicles** for both versions.

The two example content-addressed release IDs and their exact CI commit are pinned in `catalog/validation/m15-verified-real-pilot.json`. Your local release IDs can differ because you generated a larger sample and may have attached newer evidence. The example IDs are **not downloadable datasets**, and no real BITRE source or synthetic Parquet files were uploaded as GitHub artifacts. Success is limited to release integrity and reproducible accounting—not rare-model/postcode population accuracy or insurance pricing approval.

