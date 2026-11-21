# M1.3b — make/model and geographic extension

Development status: implementation in progress. Preserve the M1.3a calibrated four-way distribution exactly as weighted base cells; infer make/model, registered postcode and garaging postcode using separate published conditional aggregate projections, without joining unrelated BITRE source rows as vehicle microdata. The enriched local sample must be explicitly labelled as **synthetic Monte Carlo estimates**, not exact make/model/postcode vehicle stock or insurance policy exposure.

Training: B26-15/B26-05/B26-07 for make-model, B26-13/B26-08/B26-04 for registered postcode, B26-09 for garaging postcode. Held out: B26-14 (year-fuel-make-model), B26-16 (state-registered postcode-year-make), B26-17 (state-registered postcode-fuel-make-model). B26-10 remains excluded from base M1.3a calibration.

Queensland historical unit-like records (including VIN prefix), QLD flows, and undated ACT data will not be linked or used as contemporaneous January 2026 training evidence.
