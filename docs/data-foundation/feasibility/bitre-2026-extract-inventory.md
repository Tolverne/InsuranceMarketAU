# BITRE Road Vehicles January 2026 — detailed extract inventory

**Reference date:** 31 January 2026.  
**Discovery evidence:** [BITRE 2026 summary](https://www.bitre.gov.au/resource/roads-vehicles/road-vehicles-australia-january-2026) and [ARDC/RDA metadata for official data.gov.au dataset](https://researchdata.edu.au/road-vehicles-australia-january-2026/4251449). **Dataset ID** \`060ca7bb-83b0-4c9f-a58d-d7d1e7ec6083\`. Underlying [data.gov.au dataset](https://data.gov.au/data/dataset/060ca7bb-83b0-4c9f-a58d-d7d1e7ec6083). Licensing shown in ARDC catalogue as CC BY 3.0 Australia; confirm actual resource terms before use.  
**Status:** **17 resource titles + 1 explanatory notes documented, exact downloadable file names, schemas and bytes NOT inspected.** All 17 are confidentialised aggregate **stock** views, not microrecords.

Variables: \`T\` vehicle type, \`S\` state/territory, \`P_r\` registered postcode, \`P_g\` garaging postcode, \`Y\` manufacture year, \`F\` motive power/fuel, \`M\` vehicle make and model (or \`M_make\` make only).

| ID | Published projection / dimensions | Geographic role | Methodological importance |
|---|---|---|---|
| B26-01 | T × S × Y | State | Age distribution by class/state |
| B26-02 | T × F × Y | None | Fuel × age by class |
| B26-03 | T × S × F | State | Fuel by state/class |
| B26-04 | T × S × P_r | Registered postcode | Regional class controls |
| B26-05 | T × F × M | None | Make/model × power |
| B26-06 | T × S × P_r × F | Registered postcode | Regional fuel by class |
| B26-07 | T × Y × M | None | Model-year distributions |
| B26-08 | T × S × P_r × Y | Registered postcode | Regional age by class |
| B26-09 | T × S × P_g × F | Garaging postcode | Garaging fuel by class |
| B26-10 | T × S × F × Y | State | Power-age by state/class |
| B26-11 | T × P_r × M | Registered postcode | Model distribution by registered postcode |
| B26-12 | T × P_g × M | Garaging postcode | Model distribution by garage postcode |
| B26-13 | T × S × P_r × M | Registered postcode | State-specific model/geography |
| B26-14 | T × Y × F × M | None | Model-year-fuel |
| B26-15 | T × S × Y × M | State | State-specific model-year |
| B26-16 | T × S × P_r × Y × M_make | Registered postcode | High-dimensional make/age/geography |
| B26-17 | T × S × P_r × F × M | Registered postcode | High-dimensional model/fuel/geography |

\`B26-EXPL\`: Road Vehicles January 2026 explanatory notes; **must inspect** for count censoring/perturbation, unknowns, unit definitions, offence/vehicle type exclusions and variable code lists.

## Why we still require synthesis

These are different **projections** of an unobserved higher-dimensional table, not records that can be joined on category names. One cannot determine an exact vehicle-level \`(state, garage postcode, registered postcode, make, model, year, fuel)\` record from the separate aggregates.

- B26-16 knows registered postcode × make × year but not model or fuel in the same cell.
- B26-17 knows registered postcode × make/model × fuel but not manufacture year in the same cell.
- B26-12 has garage postcode × make/model but no year or fuel.
- B26-09 has garage postcode × fuel but no make/model.
- \`P_r\` and \`P_g\` do **not** have a paired joint in the catalogue: garaging assignment correlation is not identified.

**Model implications:** use nested conditional distributions or a constrained synthetic contingency tensor, fit consistency across projections with suppression-adjusted tolerances, and assign correlated postcode roles only with explicit additional assumptions/data. Geographic reporting must name the postcode role.

## Proposed initial control priority

1. **BITRE summary workbook** for common national/state/type controls (verify consistency with confidentialised tables).
2. **Projection-level controls** from detailed extracts after exact handling of zero/suppressed/perturbed counts is established.
3. **Jurisdictional dated joint tables** for independently observed conditional relationships or validation; do not hard-pin 2026 Q3 to a January 2026 national state.
4. **Minimum external evidence score** for each inferred interaction. Where unsupported, use broad assumptions and sensitivity ranges.

## Extraction checklist

- [ ] Resolve every data.gov.au CSV resource ID, direct URL and file format.
- [ ] Compute bytes, SHA-256 and header row; decode flags and count unit.
- [ ] Reproduce total per table and compare to BITRE summary after confidentiality treatment.
- [ ] Identify suppressed, rounded, perturbed, other and unknown-category handling from B26-EXPL.
- [ ] Inspect \`P_r\` and \`P_g\` geographic definitions and cross-state codes.
- [ ] Audit mismatch between make-only and make/model tables.
- [ ] Document which pairs/triples are observed, which are not; create a constraint schema.
- [ ] Avoid releasing small cell values in client deliverables without licensing/privacy review.

**Reminder:** names/variable groupings here are based on catalogue metadata, not direct inspection of all source file headers.
