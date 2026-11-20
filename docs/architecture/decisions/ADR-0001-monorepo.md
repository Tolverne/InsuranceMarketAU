# ADR-0001 — Single repository for code, contracts and documentation

- **Status:** Proposed (M0)
- **Context:** Data contracts, normalization, statistical reconstruction and simulated participant interfaces need synchronized changes. Small team and no deployed services yet.
- **Decision:** Keep code, architecture/ADRs, contract schemas, source metadata, notebook prototypes, tests and future IaC in one repository. Store raw datasets and generated population releases outside Git.
- **Consequences:** Easier atomic reviews, reproducible design evolution and one CI surface; may need codeowners or isolated workflows as teams grow.
- **Review when:** Pricing service/portal needs separate delivery, private IP ownership, significantly different access policy or independent operations.
