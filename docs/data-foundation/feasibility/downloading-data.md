# M0.2 — Automatically acquire Australian vehicle datasets

**Status:** initial downloader, not a synthetic population. **Verified source catalogue:** 21 November 2026. Government endpoints can change; download results, availability, licensing and actual file headers must be checked for every run.

## What happens to the data?

`scripts/download_vehicle_sources.py` downloads official source files, creates SHA-256 fingerprints, preserves each distinct file version under `data/raw/`, and writes an acquisition JSON report to `data/reports/`. Both directories are excluded from Git. The GitHub repository contains the source URLs, scripts, tests and technical documentation, **not the raw dataset**.

**You normally do not need to manually download or rename files.** The script discovers BITRE's 17 files and explanatory notes and South Australia's latest file using government catalogue APIs (CKAN). If one portal rejects automated requests, the report identifies which resource needs attention.

### Quick start — Windows PowerShell

After the PR is merged, from the local `InsuranceMarketAU` folder:

```powershell
git pull origin main
py -3 scripts/download_vehicle_sources.py --groups bitre,vic --list
py -3 scripts/download_vehicle_sources.py --groups bitre,vic,nsw,sa,act --download
```

If you want to try the branch before merging:

```powershell
git fetch origin
git switch feat/m0-2-automated-vehicle-data-acquisition
py -3 scripts/download_vehicle_sources.py --groups bitre --list
```

Python 3.11+; **no extra libraries, portal API key or AWS account required**. Use `--groups bitre` to start with the national backbone only. National detailed files may be large.

### South Australia fallback (if the government portal times out)

The original government CSV is also preserved by a third-party versioning service. This is **not** a government-hosted endpoint, so it is placed in a separately identified, opt-in source group rather than silently replacing the publisher source:

```powershell
py -3 scripts/download_vehicle_sources.py --groups sa_mirror --download
```

Original government source: [DIT Registered Vehicles by Postcode](https://data.sa.gov.au/data/dataset/registered-vehicles-by-postcode). Mirror and provenance: [publicdata.au, version 2026-07-09](https://publicdata.au/d/sa-registered-vehicles-by-postcode/v/2026-07-09/). The direct `source.csv` mirror claims to preserve the original publisher bytes. Verify hashes, rights and attribution before treating it as equivalent to a government download.

### Optional Queensland data

QLD's historic detailed registration extracts are potentially hundreds of MB per part. To review the complete file list without downloading:

```powershell
py -3 scripts/download_vehicle_sources.py --groups qld --list
py -3 scripts/download_vehicle_sources.py --groups qld --download --max-file-mb 3000
```

QLD's 2026 registration/transfer data is a **transaction flow**, not the fleet stock:

```powershell
py -3 scripts/download_vehicle_sources.py --groups qld_flows --download
```

### What to download and where the script saves it

All actual direct URLs and dynamically discovered government catalogue endpoints live in the [machine-readable acquisition catalogue](../../../catalog/acquisition/download-sources.json).

| Source group | What gets downloaded | Source / manual fallback link | Local directory |
|---|---|---|---|
| `bitre` | Summary XLSX; catalogue-selected **17 confidentialised projections + explanatory notes** | [BITRE Jan 2026](https://www.bitre.gov.au/resource/roads-vehicles/road-vehicles-australia-january-2026); [detailed data.gov.au dataset](https://data.gov.au/data/dataset/060ca7bb-83b0-4c9f-a58d-d7d1e7ec6083) | `data/raw/bitre/2026-01-31/` |
| `vic` | Q3 2026 postcode/vehicle and separate model CSVs | [VIC by postcode](https://opendata.transport.vic.gov.au/dataset/whole-fleet-vehicle-registration-snapshot-by-postcode); [VIC by model](https://opendata.transport.vic.gov.au/dataset/whole-fleet-vehicle-registration-snapshot-by-model) | `data/raw/vic/2026-09-30/` |
| `nsw` | Five 2026 ZIPs: registration stock, age, usage, heavy configuration, transaction flows | [NSW transport data](https://data.nsw.gov.au/data/en/dataset/2-transport-nsw-vehicle-registration-statistics) | `data/raw/nsw/2026/` |
| `sa` | 30 June 2026 vehicle make, year, cylinders, body, owner postcode | [SA Registered Vehicles by Postcode](https://data.sa.gov.au/data/dataset/registered-vehicles-by-postcode) | `data/raw/sa/2026-06-30/` |
| `act` | ACT make/model/suburb/emissions aggregated counts CSV | [ACT registered vehicle data](https://www.data.act.gov.au/Transport/ACT-Registered-Vehicles-by-Make-Model-and-Suburb/h4vn-y97q) | `data/raw/act/2026/` |
| `sa_mirror` (optional) | Publisher-original SA CSV preserved by a third-party mirror, used if official CKAN is unavailable | [Versioned SA 2026 mirror](https://publicdata.au/d/sa-registered-vehicles-by-postcode/v/2026-07-09/) | `data/raw/sa_mirror/2026-06-30/` |
| `qld` | Historical detailed registration CSV parts and suburb summary | [QLD vehicle registrations](https://www.data.qld.gov.au/dataset/vehicle-registrations) | `data/raw/qld/2022-10-10/` |
| `qld_flows` | 2026 new registration and transfer CSVs | [QLD new and transferred](https://www.data.qld.gov.au/dataset/vehicle-registration-new-and-transfers-test) | `data/raw/qld_flows/2026/` |

The original feasibility report also lists [WA, Tasmania and NT sources](M0.1-report.md). No equally detailed, verified current whole-fleet bulk download has been found for those jurisdictions. They are partly represented by the BITRE national data.

**Important:** each BITRE CSV describes a different observed projection. **Do not join them as though they are individual vehicles.** Use the [projection inventory](bitre-2026-extract-inventory.md) and later M1 statistical reconstruction pipeline.

## File names — no manual naming needed

The downloader uses:

```text
data/raw/<group>/<source-reference-date>/<stable-resource-id>--<first-12-hex-digits-of-SHA256>.<format>
```

For instance `data/raw/vic/2026-09-30/vic-postcode-q3-2026--a1b2c3d4e5f6.csv` is an **illustrative filename**, not a real downloaded source. The actual filename/hash is written in `data/reports/acquisition-YYYYMMDDTHHMMSSZ.json`. If a source changes, a new hash-named file is kept rather than overwriting it.

The inspector produces headers, ZIP entries and XLSX worksheet names when supported:

```powershell
py -3 scripts/inspect_source_file.py --file "data/raw/vic/2026-09-30/ACTUAL-FILE-NAME.csv"
```

## Execute via GitHub Actions (no local setup)

Once the PR is merged, open [Actions → Acquire Australian vehicle source data](https://github.com/Tolverne/InsuranceMarketAU/actions/workflows/acquire-vehicle-data.yml) and choose **Run workflow**.

Choose `groups` (e.g. `bitre`; optional `sa_mirror`) and `mode`:
- **list** — discovers direct URLs on GitHub's runner, saves a 30-day JSON report artifact, downloads no source bytes.
- **download** — downloads and checks files on GitHub's runner, saves the JSON report, then deletes raw files with the temporary runner.

There is a separate `publish_raw_artifact` option to keep raw downloads in a **7-day GitHub Actions artifact**. Do not enable it without confirming source licences, attribution and privacy/redistribution permissions: artifacts in a public repo may be shared, are not durable storage, and large files may exceed GitHub limits.

For a **durable, shared** dataset, acquire the files locally and sync to a **private** object store such as S3. Example with a bucket and AWS CLI you configure yourself:

```powershell
aws s3 sync data/raw/ s3://YOUR-PRIVATE-BUCKET/insurancemarketau/raw/ --sse AES256
```

Do not use GitHub source control, Git LFS or a public bucket as the canonical data lake.

## Common failures

| Failure | Treatment |
|---|---|
| Government catalogue API returns 403/429 | Affected resource is marked unresolved; use official source link for manual fallback or retry. |
| Resource returns a portal HTML page instead of CSV/XLSX | Downloader rejects it. |
| Source redirects outside approved government HTTPS host | Downloader rejects it pending explicit source review; some legitimate publishers use external CDNs. |
| A file exceeds configured size cap | Raise `--max-file-mb` only after confirming the resource is genuine. |
| Suppressed or confidentialised counts | Keep published raw data unchanged; do not infer that absent means zero. |
| Acquisition run reports missing resources | The run exits non-zero, and the JSON manifest shows the gaps. |

This tool acquires source bytes **but does not normalize data or populate the canonical simulation tables**. That comes next in M1, after checking BITRE's explanatory notes and cross-tab consistency.
