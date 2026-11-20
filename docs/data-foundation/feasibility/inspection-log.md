# M0.1 reproducible inspection log and field evidence

**Run date:** 2026-11-21.  
**Environment:** Primary publisher HTML/metadata pages accessible; binary resource downloads (CSV, XLSX, ZIP) not reliably accessible for parser-level inspection. Local Python runtime has no public DNS access. **This document does not claim byte-level validation.**

## Evidence grades

- \`PUBLISHER_PAGE\`: publisher description, publication date, licence label visible.
- \`CATALOGUE_PAGE\`: aggregator/discovery index gives metadata; publisher resource needs checking.
- \`PUBLISHER_SCHEMA_PREVIEW\`: field names/types visible in publisher HTML table, not parsed from actual file.
- \`FILE_PARSED\`: actual resource bytes, hash and sample/headers extracted locally (**none achieved so far**).

## Source-level inspections

### BITRE January 2026
- **Publisher page:** [BITRE](https://www.bitre.gov.au/resource/roads-vehicles/road-vehicles-australia-january-2026), state/territory unrestricted on-road vehicle registry stock as at 31 January 2026, release 12 October 2026.
- **Summary file:** \`https://www.bitre.gov.au/sites/default/files/documents/bitre-road-vehicles-australia-january-2026.xlsx\` (XLSX, 154.85 KB displayed). Resource endpoint identified by publisher; file not successfully fetched here.
- **Detailed dataset:** [ARDC/RDA catalogue](https://researchdata.edu.au/road-vehicles-australia-january-2026/4251449) exposes 17 projection titles plus explanatory notes, dataset ID \`060ca7bb-83b0-4c9f-a58d-d7d1e7ec6083\`.
- **Next check:** verify download URLs/schema/count suppression and population definitions directly against data.gov.au CSVs + notes.

### Victoria Q3 2026
- **Publisher page:** [VIC dataset](https://opendata.transport.vic.gov.au/dataset/whole-fleet-vehicle-registration-snapshot-by-postcode), quarter-end 30 September 2026, ~27.9 MB CSV, CC BY 4.0 labelled in resource page.
- **Publisher schema preview:** [VIC resource](https://opendata.transport.vic.gov.au/dataset/whole-fleet-vehicle-registration-snapshot-by-postcode/resource/fb041326-4af4-4797-abef-de9cb6347bae) exposes:
  - \`CD_MAKE_VEH1\` string — make
  - \`NB_YEAR_MFC_VEH\` integer — manufacture year
  - \`POSTCODE\` integer — garage postcode (load as string preserving leading zeros if any)
  - \`CD_CL_FUEL_ENG\` string — fuel; \`E = Electric or Hybrid Electric\` at this vintage
  - \`TOTAL1\` integer — vehicle count
  - \`CD_CLASS_VEH\` appears in the [Q1 2026 data preview](https://opendata.transport.vic.gov.au/dataset/whole-fleet-vehicle-registration-snapshot-by-postcode/resource/1272c696-e5de-47f8-9bf3-2cb432f23fd4/view/60775ccf-bb67-4549-8df7-396cd26ec705) but Q3 resource's published data dictionary does **not** list it; **actual CSV header must resolve this inconsistency**.
- **Next check:** parse Q3 header, field types, unclassified/missing postcode, joint row counts, duplicate keys, relationship to BITRE January.

### NSW 2026
- **Publisher page:** [TfNSW dataset](https://data.nsw.gov.au/data/en/dataset/2-transport-nsw-vehicle-registration-statistics). Description states month-end registrations, age/usage/heavy-configuration snapshots and transactions, with two-month backdated transaction revisions.
- **File links (metadata-only):** [Vehicle registration snapshot 2026](https://opendata.transport.nsw.gov.au/data/dataset/2342b8e4-d4fc-4549-82de-b36380ea46f2/resource/ce42b24e-ffb9-4f6c-9637-6a26f9574624/download/tfnsw_vehicle_registrations_snapshot_2026.zip); [age snapshot 2026](https://opendata.transport.nsw.gov.au/data/dataset/2342b8e4-d4fc-4549-82de-b36380ea46f2/resource/64715b2a-0079-4eda-a618-a36ef72105c7/download/tfnsw_age_of_registered_vehicles_snapshot_2026.zip).
- **Next check:** ZIP file member listing/headers and monthly reference dates, caveats about fleet status, geographic detail, suppressed aggregates.

### Queensland
- **Historic fleet:** [QLD registration dataset](https://www.data.qld.gov.au/dataset/vehicle-registrations) describes detailed light/other/motorcycle extracts and suburb aggregate; registered 10 October 2022, excluding seasonal.
- **Recent movements:** [new and transferred transactions](https://www.data.qld.gov.au/dataset/vehicle-registration-new-and-transfers-test) 2026 resources with make/model, vehicle attributes, transaction/customer type, local government area.
- **Current aggregate controls:** [TMR registration reports](https://www.tmr.qld.gov.au/safety/transport-and-road-statistics/registration-statistics), current 30 June 2026 per landing page.
- **Privacy limitation:** TMR states it does **not** release postcode at individual vehicle level as open data. [Government reply](https://www.data.qld.gov.au/datarequest/comment/075d74f8-faa3-4e6f-aae4-95ac375080f1).
- **Next check:** actual extract headers, surrogate identifiers, primary-class mapping; no assumption of one-to-one join between suburb and vehicle rows.

### South Australia
- [ARDC/RDA record](https://researchdata.edu.au/registered-vehicles-postcode/2210007) states annual 30 June 2012–2026 by postcode of owner's residential address × make × body × cylinders × manufacture year, reference \`TRLB04\`, licence label CC BY 4.0. Primary data.sa.gov.au portal returned 403 in environment.
- **Next check:** primary CSV resource URL and header, whether counts of 1 are suppressed, historical schema changes, exact licensing and attribution terms.

### Australian Capital Territory
- [ACT dataset](https://www.data.act.gov.au/Transport/ACT-Registered-Vehicles-by-Make-Model-and-Suburb/h4vn-y97q), 6 columns listed in publisher preview: \`data_as_at\` timestamp, \`suburb\` text, \`make\` text, \`model\` text, \`emissions_category\` text and \`count\` number; 6,940 rows shown, last updated 14 November 2026.
- **Disclosure:** count rows with value ≤10 are suppressed; includes trailers/motorbikes and warns that related ACT datasets may not sum due to different filters/quality.
- **Next check:** API sample, suppressed-code type/nulls, date range and total reconciliation.

### Tasmania
- [Registration statistics](https://www.transport.tas.gov.au/registration/general_information/statistics) HTML presents counts by body type, municipality, premium class and EV body type. Page changes monthly (observed search snippets reference 31 October 2026 while an earlier page view surfaced 30 September 2026). Do **not** hardcode today's site counts in a persistent fleet release without capture date.
- **Potential scope issue:** one visible page view shows body-type and premium-class grand totals with a small discrepancy; verify from the same archived snapshot and ask about \`No premium\`, trailers and restricted registrations.
- **Next check:** retrieve a dated archived page, parse each HTML table and record source reference date.

### Western Australia
- [WA quarterly EV licensing](https://transport.wa.gov.au/projects-planning/electric-vehicles/western-australian-electric-vehicle-registrations) provides September 2026 EV subtype count (55,701 BEVs and 17,770 PHEVs) and change. This is EV segment only.
- [Western Australian Vehicle Fleet Model](https://transport.wa.gov.au/projects-planning/transport-insights/areas-of-enquiry/western-australian-vehicle-fleet-model) is described as an internal forecasting model, **not** evidence of public underlying microdata.
- **Next check:** request state source/cross-tabs, class/year/fuel by postcode and publication rights. BITRE detailed projections already support WA.

### Northern Territory
- [NT Road Safety statistics](https://roadsafety.nt.gov.au/research-and-statistics/driver-licensing-and-registration-statistics) lists quarterly registered vehicle-type counts through the visible 1 July 2024 table.
- [NT EV strategy](https://dli.nt.gov.au/strategies/electric-vehicle) says 31 October 2026 EV totals by passenger/commercial, motorcycle and heavy type.
- [NT Government Fleet Profiles](https://data.nt.gov.au/dataset/northern-territory-fleet) explicitly cover government agencies, not the whole jurisdiction.
- **Next check:** publisher request for more recent all-fleet type, fuel, age and postcode aggregate data.

## Portable inspection tool

The repo provides \`scripts/inspect_source_file.py\` to inspect **already downloaded local** CSV/XLSX/ZIP (or bounded HTTPS retrieval with an explicit opt-in). It captures SHA-256, size, tabular headers and ZIP members locally in a JSON profile. This is an inspection aid, **not** a trusted ingestion or licence-granting pipeline. Start with government source links; never commit source bytes to the public repo.

## Unresolved questions

1. How exactly does BITRE confidentialisation work per table and count status?
2. Which dimensions are present in the *physical* VIC Q3 CSV, as opposed to catalogue descriptions?
3. Does TfNSW provide postcodes in any 2026 snapshots or is it state/month aggregate only?
4. Do SA/ACT publisher outputs include small-cell suppression/total bypass?
5. Can any detailed WA/NT source be licensed for commercial derivative work?
6. What is the legal treatment of joining independent, low-count vehicle-attribute aggregates to household or geospatial risk data?
