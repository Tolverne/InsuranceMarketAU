# Verified real-source acquisition smoke (GitHub runner)

**Test time:** 2026-11-21 (Australia/Brisbane); [successful GitHub Actions run](https://github.com/Tolverne/InsuranceMarketAU/actions/runs/44837619616). The source data were downloaded on a temporary runner and were not committed to Git. **Machine-readable record:** [verified-source-smoke.json](../../../catalog/acquisition/verified-source-smoke.json).

## Successfully downloaded and inspected

| Resource | Size | SHA-256 | Inspection result |
|---|---:|---|---|
| BITRE Jan 2026 national workbook | 158,564 bytes | `e35996e412c58cdfd8ecf30d686bb852e4efd56b5cfbb9521af9b7cbda307e81` | XLSX opened as ZIP; Index, Tables 1–15, Explanatory Notes |
| Victoria Q3 2026 make/model CSV | 3,488,815 bytes | `1bce46ee689bc2195649d84e354d9bce18015c6d5daa88f3650dbf85c1594572` | CSV header: `CD_MAKE_VEH1`, `CD_MODEL_VEH`, `CD_CLR_BDY_VEH_P`, `TOTAL1` |

Both resources were fetched from the government publisher URLs and passed the script's basic file signature validation.

## Successful API discovery

The data.gov.au CKAN API **did return all 17 BITRE detailed 2026 files and explanatory notes** (18 resources, separate from the summary XLSX). The Queensland CKAN API returned two 2026 new-registration/transfer CSV resources. These were **listed, not downloaded** in this run.

## Blocker and fallback

The official South Australian CKAN dataset call returned **HTTP 504 Gateway Timeout** in this test. A separately identifiable third-party mirror of the original government CSV has been added as an **optional** `sa_mirror` group. The mirror's own publisher record and CC BY 4.0 attribution are described at [publicdata.au](https://publicdata.au/d/sa-registered-vehicles-by-postcode/), but the source hash must be cross-checked against government original bytes before it is approved for ingestion. It must never be silently substituted for a direct official file.

## What this verification does not prove

The XLSX worksheet list and CSV header are **format-only** observations. We have not yet verified all row counts, category codes, actual file quality, privacy constraints, source alignment, or the legality of redistributing complete raw files through public GitHub.

For full acquisition commands, see [download guide](downloading-data.md).
