# Data/model governance — initial policy

This is a public design repository. Raw source downloads, named customers, full VINs/plates, proprietary quote data, credentials and unlicensed derivative materials belong in access-controlled storage outside Git. A professional consulting product will need a formal owner for source permissions, privacy impact assessment, intellectual property and client segregation before use.

## Gates

- **Data source:** publisher licence, reference scope, acquisition method, retention and derived sharing permissions.
- **Data release:** reconciled controls, provenance/completeness labels, quality report, exposure of suppressed/small groups.
- **Model release:** immutable version, training/validation inputs, drift, bias/fairness where relevant, feature contract, performance and limitation statements.
- **Experiment:** pinned manifests, seeds, independent validation set, scenario context, assumptions and uncertainty report.
- **Client reporting:** report approval, intended use, uncertainty disclosures and restricted data handling.

## Risk register seed

1. Identifiability and small-cell disclosure at postcode x rare vehicle combinations.
2. Licensing/terms limitations on source downloads, competitor quotes and reference model data.
3. False precision from imputation or inconsistent national/state control definitions.
4. Model bias/selection effects and unobserved competitor preferences.
5. Scenario look-ahead leakage and incorrectly independent catastrophe losses.
6. Cross-client confidential data leakage and unapproved model sharing.
7. Implicit accounting/regulatory promises from an internal management P&L.

Detailed controls and legal review status to be added after source feasibility work.
