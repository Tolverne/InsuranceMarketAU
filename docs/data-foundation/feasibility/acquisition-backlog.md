# M0.1 data acquisition / partner outreach backlog

**Goal:** convert catalogue discoveries to **verified downloaded schemas and rights-cleared source releases**. In this research environment, publisher HTML and metadata were accessible but binary CSV/XLSX/ZIP fetching was blocked; no data file was ingested.

## Ordered source acquisition

| P | Data asset | Action | Source / requested evidence |
|---|---|---|---|
| 0 | BITRE 2026 17 joint tables + notes | Download exact resources from data.gov.au; inspect schema/count policy; checksums; ask BITRE for clarification if necessary | [BITRE dataset](https://data.gov.au/data/dataset/060ca7bb-83b0-4c9f-a58d-d7d1e7ec6083) |
| 0 | BITRE 2026 summary XLSX | Download, list sheets and compare all state/type totals | [BITRE report](https://www.bitre.gov.au/resource/roads-vehicles/road-vehicles-australia-january-2026) |
| 0 | VIC Q3 2026 stock CSV | Download and inspect \`CD_CLASS_VEH\`, fuel E, postcodes, category/cell counts | [Transport Victoria](https://opendata.transport.vic.gov.au/dataset/whole-fleet-vehicle-registration-snapshot-by-postcode) |
| 0 | SA 2026 registration CSV | Resolve primary links, parse owner postcode/body/year/cylinders and confidentiality, confirm derivative licence | [SA catalogue](https://researchdata.edu.au/registered-vehicles-postcode/2210007) |
| 0 | NSW 2026 5 ZIP resource families | Inspect member names, headers, month-end/status semantics and backdating | [TfNSW](https://data.nsw.gov.au/data/en/dataset/2-transport-nsw-vehicle-registration-statistics) |
| 1 | QLD 2022 detailed stock and 2026 flow | Inspect per-record fields/count and 2026 report comparisons; assess historical transfer dependence | [TMR 2022](https://www.data.qld.gov.au/dataset/vehicle-registrations) · [QLD flows](https://www.data.qld.gov.au/dataset/vehicle-registration-new-and-transfers-test) |
| 1 | ACT registered vehicle tables | Test 6-field make/model/suburb API, hidden cells, totals and alternate type/fuel tables | [ACT](https://www.data.act.gov.au/Transport/ACT-Registered-Vehicles-by-Make-Model-and-Suburb/h4vn-y97q) |
| 1 | TAS dated registration table | Capture archived reference date with vehicle/premium-class scope and reconcile table totals | [TAS](https://www.transport.tas.gov.au/registration/general_information/statistics) |
| 1 | WA and NT official detailed data | Request downloadable postcode/make/model/year/fuel tabs or sanctioned extraction, dates, suppression and licence | [WA transport](https://transport.wa.gov.au/projects-planning/transport-insights/areas-of-enquiry/western-australian-vehicle-fleet-model) · [NT stats](https://roadsafety.nt.gov.au/research-and-statistics/driver-licensing-and-registration-statistics) |

## Questions for BITRE

1. Is the January 2026 detailed file list exactly complete and will historic versions remain published?
2. How are cells with 0, 1–n, confidentialised, unknown, suppressed, not-stated or reclassified coded?
3. Do independent projections reconcile by construction? Which aggregate counts should serve as hard controls?
4. What are the precise vehicle eligibility / on-road registration exclusions, garage vs registered postcode, and cross-state handling?
5. Is bulk downloading/derived confidentialised aggregate redistribution allowed under the displayed CC BY 3.0 AU dataset licence?
6. What is the best route for requesting **joint garage postcode × make/model × year × motive power**, if disclosure-safe?
7. Are source headers stable between 2025 and 2026? Are code lists downloadable?

## Questions for state authorities (especially SA, WA, NT)

- Are aggregated **garaging postcode** counts available for \`vehicle class × make/model × year × fuel\`? Which suppressed/differentially private cells?
- What reference snapshot date and fleet status are included (registered/restricted/expired/month-end)?
- Is geography garaging, owner residential or register administrative postcode?
- Do counts include trailers, farm/special-interest, seasonal, commercial fleets and government vehicles?
- Can the historical source and new releases be used in commercial consulting, and what attribution/retention limits apply?
- Is an API/resource catalogue available for bulk refresh? Are corrections to older months retroactively published?

## Delivery workflow for the first actual resource

1. Register resource URL, owner, public licence statement and source-grain.
2. Store bytes privately (outside Git); compute SHA-256.
3. Write an inspection profile: headers, row counts, type inference, missingness/flags, minimum/maximum reference date, sample categories.
4. Cross-check original publisher data dictionary and alert on mismatches.
5. Confirm rights/attribution; set \`licence_review = verified\` only following a documented decision.
6. Commit manifest and **sanitized** schema/profile into \`catalog/sources/\`, not the source data.
7. Build a test fixture with artificial rows and schema drift tests.
8. Validate an independent aggregate control; only then mark the resource ready for M1 ingestion.

## Reproduce local inspection

\`\`\`bash
python scripts/inspect_source_file.py --file data/raw/vic_q3_2026.csv --output data/profiles/vic_q3_2026.json
python scripts/inspect_source_file.py --file data/raw/nsw_2026.zip --output data/profiles/nsw_2026.json
python scripts/inspect_source_file.py --file data/raw/bitre_2026.xlsx --output data/profiles/bitre_2026.json
\`\`\`

The script does not fetch automatically, avoids printing raw data rows, and only examines file/format/headers/ZIP member names by default. It does not authorize collection or sharing.
