# Australian motor market source register — candidate/landing-page verification

> **M0.1 UPDATE (2026-11-21):** The national BITRE 2026 data.gov.au dataset has **17 detailed confidentialised projections**, and NSW/SA/ACT and jurisdictional control sources are more developed than this initial seed register. See [M0.1 feasibility report](feasibility/M0.1-report.md) and [BITRE extract inventory](feasibility/bitre-2026-extract-inventory.md) for the current detailed evidence assessment. This older register remains as historical M0 discovery context.

**Reviewed:** 2026-11-21. **Status:** *discovery only*. These URLs and landing-page claims have been checked; raw downloads, exact schemas, licensing for downstream commercial derivatives and completeness have **not** been fully assessed. The source manifest registry in `catalog/sources/` will track each acquired release separately.

## Initially confirmed primary publishers

| ID | Source (publisher) | Type & granularity | Observed vintage / release | Intended use and caution | URL |
|---|---|---|---|---|---|
| BITRE-RVA | Road vehicles, Australia (BITRE) | National/state **registered stock** aggregate tables | Reference 31 Jan 2026; released 12 Oct 2026 | National/category totals for unrestricted road-use registered vehicles, using NEVDIS. Different universe from all insurable assets. | [BITRE January 2026](https://www.bitre.gov.au/resource/roads-vehicles/road-vehicles-australia-january-2026) |
| VIC-FLEET | Whole Fleet Vehicle Registration Snapshot by Postcode (Vic DTP) | Quarter-end **joint aggregate** of postcode, make, fuel, class, manufacture year, colour | Q3 2026 resource; page states updated 15 Oct 2026 | Joint distribution & validation for Victoria. Landing page states vehicles excluding boats/trailers; errors in code spellings possible. | [Transport Victoria](https://opendata.transport.vic.gov.au/dataset/whole-fleet-vehicle-registration-snapshot-by-postcode) |
| QLD-STOCK | Vehicle registrations (QLD TMR) | Detailed historical registration extracts and by-suburb aggregate | State of register as at 10 Oct 2022 (explicit on page) | Historical vehicle attributes and joint structure; **do not** treat as Jan 2026 stock. Page excludes seasonal registrations, contains trailers/caravans in some resource groups. | [Queensland vehicle registrations](https://www.data.qld.gov.au/dataset/vehicle-registrations) |
| QLD-FLOW | Vehicle Registration New and Transferred Vehicle Details (QLD TMR) | Vehicle registration/transfer transactions; resource-specific record layout | Resources include 2025 and 2026 (exact coverage needs file inspection) | **Flows/events only**, not an existing fleet count. Transfer != addition. | [Queensland example resource](https://www.data.qld.gov.au/dataset/vehicle-registration-new-and-transfers-test/resource/f91b225c-f5ac-4a17-9d54-2142ae3fd229) |
| ABS-HH | Transport: Census, 2021 (ABS) | Households, vehicle counts and travel-to-work aggregates | 2021 Census | Conditional owner/household and usage proxies; time adjustment and distinction from registered fleet required. | [ABS transport census](https://www.abs.gov.au/statistics/industry/tourism-and-transport/transport-census/2021) |
| APRA-GI | Quarterly general insurance performance statistics (APRA) | Industry financials by class and state, **not** vehicle records | Page currently provides through June 2026; new framework from Jul 2023 | External insurance performance benchmarks, subject to definitions and accounting basis. **Institution-level GI statistics noted as on hiatus** on the page. | [APRA quarterly GI](https://www.apra.gov.au/news-and-publications/quarterly-general-insurance-performance-statistics) |
| BITRE-RAV | Road vehicle entry and recall statistics (BITRE) | Approved vehicle entries and recall information | Monthly resources | Candidate entry/reference trend (RAV entries are **not** equivalent to net changes in registered stock). | [BITRE road vehicle entry](https://www.bitre.gov.au/resource/roads-vehicles/road-vehicle-entry-and-recall-statistics) |

Some portals publish CC BY 4.0 at collection level (e.g., Victorian and QLD registration landing pages). That does **not** replace per-resource terms, privacy/reidentification checks or downstream-commercial-use legal review.

## Mandatory discovery before committing to M1 coverage

- [ ] NSW: registration stock and available joint cuts by state/postcode/class/year/make.
- [ ] WA: registration stock, class/age/fuel and cross-tab availability.
- [ ] SA: vehicle registration data grain, freshness, and public download rights.
- [ ] Tasmania: registered stock breakdown and geography.
- [ ] ACT: fleet stock and joint distributions.
- [ ] NT: registered fleet, remote/geographic and seasonal definitions.
- [ ] All jurisdictions: unregistered, seasonal/restricted and special-plate categories.
- [ ] Reference catalogues: vehicle models/variants and market values (rights and costs), geography crosswalks and fuel/engine code mappings.
- [ ] Claims/perils: road crashes, weather hazards, repair costs, theft, insured losses and catastrophe data, with jurisdiction/cover compatibility.
- [ ] Insurance market: penetration/coverage, price and consumer switching, insurer/brand market participation, CTP vs optional coverage boundary.

## Acquisition checklist per source

Record separately: owner/publisher, primary and downloadable URLs, licence and attribution, dataset reference date, publication date, acquisition timestamp, schema/code list, grain, row count, file hash, inclusion/exclusions, geography, update cadence, intended use, redistributability, approved access storage, observed quality issues, parser version, and actual controlled validation outcome.

**Important:** this register describes candidates and some verified landing pages, **not** a complete available dataset for all Australian vehicles. Missing state coverage and unknown source definitions remain first-class research tasks.
