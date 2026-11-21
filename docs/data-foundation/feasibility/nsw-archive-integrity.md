# NSW 2026 archive content integrity incident

**Status:** Source publisher issue confirmed on 21 November 2026. Do not load the apparent 2026 vehicle-age ZIP.

## Evidence

Transport for NSW officially publishes distinct **Age of Registered Vehicles Snapshot 2026** and **Registered Heavy Vehicles by Configuration Snapshot 2026** resources: [NSW registration statistics](https://data.nsw.gov.au/data/en/dataset/2-transport-nsw-vehicle-registration-statistics).

The two distinct official download endpoints both returned the same 302,566-byte ZIP, SHA-256:

`a7add6b6a59095a8df97bab4173c5bf9dd4a31c025be1e16d6b6d7a6f7ced981`.

[Independent GitHub Actions reproduction](https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44842467336) showed every member file under **both** URLs is named `TfNSW_Registered_Heavy_Vehicles_by_Configuration_Snapshot_YYYYMM_1.csv` and contains columns:

```text
"VEHICLE TYPE"|"NOMINATED OPERATING CONFIGURATION"|"CONFIGURATION CODE"|"CUSTOMER ADDRESS LGA"|"COUNT"
```

They are not vehicle-age data. The cause at the publisher has not been confirmed; the evidence establishes a content/metadata mismatch, not necessarily a permanent government error.

## Correct action for M1

- Keep the **NSW heavy configuration** ZIP as valid for that purpose.
- Do **not** import the file named `nsw-age-2026--a7add6b6a590.zip` into vehicle-age tables.
- Preserve the source evidence, but quarantine the mislabeled age ZIP outside `data/raw/` until source integrity is resolved.
- Use the national BITRE January 2026 type/state/manufacture-year tables for NSW fleet-age distributions in the first release.
- Recheck the official age URL in a later source-refresh run. The downloader now checks expected ZIP member names **before** accepting source files.
- Do not equate month-end NSW 2026 records with BITRE's 31 January 2026 controls without explicit date and universe alignment.

## Windows PowerShell — quarantine wrong local age file

From the root of `InsuranceMarketAU`:

```powershell
New-Item -ItemType Directory -Force .\data\quarantine\nsw | Out-Null
Move-Item .\data\raw\nsw\2026\nsw-age-2026--a7add6b6a590.zip .\data\quarantine\nsw\
```

This moves the original source bytes out of the ingestion search path but retains the evidence and audit hash locally. The `data/` directory is ignored by Git.

## Important limitation

Our simple validator checks source ZIP **member naming**, not row-level values. All NSW files still require future M1 schema, row, scope and control-total validation.
