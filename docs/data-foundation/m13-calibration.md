# M1.3 — Sparse national vehicle-joint reconstruction (initial calibration slice)

Status: in development.

The reconstruction conditions on the official BITRE January 2026 Table 1 state-by-vehicle-type accounting controls and learns a synthetic *distribution* of manufacture year and motive power from independently published confidentialised projections. This is not vehicle microdata; no record linkage is performed.

**Training**: B26-01 state/class/year, B26-03 state/class/fuel and B26-02 class/year/fuel. **Holdout**: B26-10 state/class/year/fuel, never used to build support or fit weights. B26-10's public aggregate counts are confidentialised and cannot provide a truly independent physical ground truth, but are useful predictive diagnostics.

M1.3a will not treat the known-bad NSW vehicle-age ZIP, undated ACT file, Queensland registration rows or transactions as calibration observations. Source-specific inclusion and privacy review is required before incorporating those extra datasets. The QLD 2022 files may provide useful joint attribute evidence, but VIN Prefix is not an appropriate public synthetic-output field.

Full-scale make/model and location features require the later M1.3b factorisation and tests against B26-07/14/15/16/17, not a fictitious raw cross-table join.
