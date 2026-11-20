# Data security and responsible use

The public repository contains code, designs and non-sensitive metadata, **not a licensed data lake**.

- Do not commit VINs, number plates, names, contact details, addresses of identifiable people, credentials, restricted insurer quotes or commercial client data.
- Collect the minimum information needed. Use synthetic identifiers in published/demo populations.
- Maintain dataset-level legal basis/licence, access classification, retention, permitted use and onward-sharing rules.
- Aggregate or suppress small sensitive geography/driver groups in externally shared reports.
- Treat scraped/quoted competitor pricing as potentially restricted by terms, privacy and legal obligations; require approval before collection.
- Encrypt controlled raw datasets at rest/in transit; isolate tenants and log access when a service is deployed.
- Source metadata is public only if publication itself is permitted. Do not encode client-specific secrets into manifests.

Any future privacy impact assessment, legal/licence review or threat model should be recorded in `docs/governance/`.
