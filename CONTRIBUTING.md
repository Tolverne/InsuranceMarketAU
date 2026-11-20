# Contributing

This repository is documentation-led during M0. Use focused PRs with a rationale, links to affected contracts/ADRs, verification results and migration notes.

## Proposed workflow

1. Create a descriptive feature branch; do not rewrite published data/model releases.
2. Update documentation and contracts in the **same PR** as code changes.
3. Record decisions with lasting architectural consequences in an ADR.
4. Run \`python scripts/validate_repository.py\` and future test/format commands.
5. Include a data-provenance and privacy/licence assessment for new datasets.
6. Preserve backwards compatibility or describe explicit schema migrations.

## Documentation conventions

- All dates ISO 8601; timezone noted for event timestamps.
- Currency includes ISO code (e.g. AUD), prices specify tax/duty/fee treatment.
- All counts describe the counted unit, period and population definition.
- Distinguish registered vehicles, insurable vehicles, insurance exposures, policies and people.
- Clearly label **observed**, **estimated**, **imputed** and **scenario-assumed** fields.
- Clearly label proposals versus implemented functionality; no fabricated performance claims.

## Security

Never commit source records containing identifiable customers, insurer secrets, raw quote responses with restrictions, API keys or licensed datasets unless rights and security controls are explicitly approved. See [SECURITY.md](SECURITY.md).
