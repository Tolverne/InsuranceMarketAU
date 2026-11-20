# Registration field availability and join semantics

**Legend:** ✓ publisher/catalogue states observed; ◐ partial, separate table or dated/inconsistent; — not identified; ? not verified from actual resource headers. Roles and grain matter more than an apparent yes/no.

| Source | Stock current | Flow | Location | Vehicle class | Make/model | Year | Fuel | Other detail | Major boundary |
|---|---|---|---|---|---|---|---|---|---|
| BITRE 2026 | ✓ | — | ✓ registered and garage **in separate tables** | ✓ | ✓ | ✓ | ✓ | — | 17 different confidentialised projections |
| NSW 2026 | ✓ monthly | ✓ transactions | ? | ◐ | ? | ✓ age snapshot | ? | usage/heavy-configuration | multiple monthly ZIP resources |
| VIC Q3 2026 | ✓ quarter | — | ✓ garage postcode | ✓ | ◐ make in postcode table; model separate | ✓ | ✓ coarse \`E\` | vehicle colour referenced | 2026 Q3 ≠ 2026 Jan |
| QLD 2022 | ✓ historic | — | ◐ suburb count separate | ✓ | ✓ detailed vehicles | ✓ | ✓ | body, colour, purpose | no postcode at vehicle granularity in open source |
| QLD 2026 flows | — | ✓ | ◐ transaction LGA | ✓ | ✓ | ✓ | ✓ | transaction/customer category | transfer ≠ fleet entry |
| QLD 2026 report | ✓ aggregate | — | state / perhaps region | ✓ | — | ? | ✓ | body type | aggregation and scope |
| SA Jun 2026 | ✓ annual | — | ✓ **owner** postcode | ◐ body | ✓ make | ✓ | — | cylinders | primary file not inspected |
| WA | ◐ via BITRE | — | ◐ BITRE postcode | ◐ | ◐ BITRE extracts | ◐ | ✓ EV segment | WA EV quarter trends | no confirmed detailed WA public stock |
| TAS | ✓ live table | — | ✓ municipality | ✓ | — | — | ✓ EV body only | premium/restricted class | includes trailers/extra categories |
| ACT Nov 2026 | ✓ joint | — | ✓ suburb | ◐ broad | ✓ make/model | — | ◐ emissions rating only | count suppression | totals not additive without handling |
| NT | ◐ historic types | — | — | ✓ historic | — | — | ✓ EV segment | government fleet separate | not nationwide NT vehicle data |

## Field dictionary for M1 candidate dimensions

| Canonical field | Allowed observation roles | Key issue |
|---|---|---|
| \`registered_state\` | state/territory of **registry** | registered state may differ from owner state |
| \`registered_postcode\` | postcode on registration | may be PO box, owner/administrative address |
| \`garaging_postcode\` | postcode where vehicle generally garaged | relevant to pricing/geocoding but sometimes modelled |
| \`owner_residential_postcode\` | owner's residential postcode | not synonymous with garage; SA source uses this |
| \`municipality\` | municipal registration count | requires uncertain crosswalk to postcode/SA2 |
| \`vehicle_class\` | jurisdiction/body vs BITRE nationally mapped category | mapping not one-to-one |
| \`make\` / \`model\` | registry or standardized name at dated publication | model naming/variant ambiguity |
| \`manufacture_year\` | actual year or documented band | future/out-of-range errors |
| \`motive_power\` / \`fuel\` | data-source taxonomy and version | VIC \`E\` includes electric **or hybrid electric**, not equal to BEV |
| \`registered_count\` | integer or confidentialised interval | distinguish suppressed, rounded, unknown |
| \`observation_date\` | actual stock reference date | may differ from source release/update date |
| \`source_role\` | stock, flow, reference, benchmark | never sum stocks and transactions |
| \`count_status\` | observed, perturbed, suppressed, rounded, missing | must not fill suppressed with zero |

### Two design additions suggested by M0.1

1. Add **\`location_role\`** and **\`count_disclosure_status\`** to the eventual stock observation contract and constrain by projection ID, not just flat source IDs.
2. Add a **projection graph** linking each table's observed dimensions to common universe controls. Every synthetic joint interaction has an evidence/support grade.

## Unobserved downstream dimensions

Registration data do not reliably identify full vehicle variant, current value, usage kilometers, main/occasional driver, prior claims, garaging exact risk coordinates, optional motor cover, incumbent insurer or premium. M1 **does not** fabricate these as if vehicle-registry attributes. M2 or later enrichment introduces probabilistic/assumed features using separately registered sources.
