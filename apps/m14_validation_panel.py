"""Local-only M1.4a validation panel, loaded inside M1.3b Streamlit explorer.

Only reads aggregate synthetic diagnostics from data/reports/. It never
executes model fitting, reads raw publisher cells, or asks for VIN records.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data/reports/m14/current-diagnostics.json"
SENSITIVITY = ROOT / "data/reports/m14/sampling-sensitivity.json"

st.subheader("Independent model validation")
st.caption(
    "Comparison with BITRE B26-14 (type × year × fuel × make × model), "
    "a published aggregate cross-tab withheld from conditional fitting. "
    "Only originally published cells with counts ≥100 are compared."
)
if not REPORT.is_file():
    st.info(
        "No M1.4 validation report is available yet. Leave the explorer running "
        "or open a second PowerShell window and run: "
        "py -3 scripts/m14_validate.py. Refresh the page afterwards."
    )
else:
    @st.cache_data(show_spinner=False)
    def _load(path: str, stamp: int) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    report = _load(str(REPORT), REPORT.stat().st_mtime_ns)
    sample_record = report.get("sample", {})
    linked_sample = Path(sample_record.get("sample_file", ""))
    sample_stale = (
        not linked_sample.is_file()
        or linked_sample.stat().st_size != sample_record.get("sample_size_bytes")
        or linked_sample.stat().st_mtime_ns != sample_record.get("sample_mtime_ns")
    )
    if (report.get("pipeline") != "m14a-independent-validation-v1"
        or report.get("population_release_created") is not False
        or report.get("source_margins_recalibrated") is not False):
        st.error("Unexpected validation report contract — do not interpret these diagnostics.")
    elif sample_stale:
        st.error(
            "This validation report refers to a different synthetic sample. "
            "Run py -3 scripts/m14_validate.py after regenerating M1.3b, "
            "then refresh the explorer."
        )
    else:
        summary = report["metrics"]["overall"]
        sample = report["sample"]
        a,b,c,d = st.columns(4)
        a.metric("Published-cell WAPE", f"{100 * summary['published_cell_WAPE']:.1f}%")
        b.metric("Published cells represented", f"{100 * summary['sample_support_fraction']:.1f}%")
        c.metric("Synthetic sample rows", f"{sample['sample_rows']:,}")
        d.metric("Four-way max balancing error", f"{sample['max_four_way_mass_residual']:.6f}")
        st.warning(
            "**Diagnostic ≠ model certification.** These errors measure differences "
            "from published, disclosure-adjusted cross-tabs and include Monte Carlo "
            "sampling effects. They are not accuracy against actual individual "
            "vehicles or the size of an insurable classic/prestige market.",
            icon="⚠️",
        )
        st.caption(
            "The original 64,008 four-way source-calibrated combinations are "
            "independently checked to retain their expected weights, not merely "
            "checked against the national 22.77-million total."
        )

        age_tab, make_tab, class_tab, sampling_tab = st.tabs([
            "Vehicle age & classic cohorts",
            "Make residuals",
            "Vehicle type & publication cell sizes",
            "Monte Carlo sensitivity",
        ])
        with age_tab:
            cohorts = report["metrics"]["cohorts_overlap_do_not_add_them"]
            st.subheader("Older-than cohort residuals")
            cols = st.columns(3)
            for col, key in zip(cols, ("before_1980","before_1990","before_2000")):
                val = cohorts[key]
                with col:
                    st.metric(
                        key.replace("_"," ").title() + " WAPE",
                        f"{100 * val['published_cell_WAPE']:.1f}%" if val["published_cell_WAPE"] is not None else "n/a",
                    )
                    st.caption(
                        f"{val['source_cell_count']:,} published comparison cells; "
                        "cohorts overlap"
                    )
            rows = report["metrics"]["segments"]["age_band"]
            if rows:
                by_age = pd.DataFrame(rows)
                by_age = by_age[[
                    "label", "published_reference_mass",
                    "synthetic_expected_mass_on_same_cells",
                    "published_cell_WAPE", "sample_support_fraction",
                    "source_cell_count",
                ]]
                by_age.columns = [
                    "Manufacture-year band", "Published-count reference",
                    "Synthetic estimate on same cells", "Cell WAPE",
                    "Fraction of published cells represented", "Published cells",
                ]
                st.dataframe(by_age, hide_index=True, use_container_width=True)
                plot = by_age.set_index("Manufacture-year band")[[
                    "Published-count reference", "Synthetic estimate on same cells",
                ]]
                st.bar_chart(plot, y_label="Expected vehicles / published comparison mass")
            st.caption(
                "The original BITRE counts may be disclosure modified. "
                "A weighted count on precisely published cells is not a "
                "complete census of all vehicles in an age band."
            )

        with make_tab:
            st.subheader("Largest source-supported makes (B26-14)")
            st.caption(
                "Displayed makes are aggregate groupings of at least three "
                "published source cells, each originally ≥100, with total "
                "published count ≥1,000. Missing smaller cells are not zeros."
            )
            makes = report["metrics"]["segments"]["make"]
            if makes:
                frame = pd.DataFrame(makes)
                st.scatter_chart(
                    frame, x="published_reference_mass",
                    y="synthetic_expected_mass_on_same_cells",
                    x_label="Published count on compared cells",
                    y_label="Modelled expected count on same cells",
                )
                shown = frame[[
                    "label", "published_reference_mass",
                    "synthetic_expected_mass_on_same_cells",
                    "published_cell_WAPE", "sample_support_fraction",
                    "source_cell_count",
                ]]
                st.dataframe(shown, hide_index=True, use_container_width=True)
            else:
                st.info("No make aggregates passed the publication and data-coverage display rule.")
            old = report["metrics"]["segments"]["historic_make"]
            if old:
                st.subheader("Older makes: manufactured before 1990")
                st.dataframe(
                    pd.DataFrame(old)[[
                        "label", "published_reference_mass",
                        "synthetic_expected_mass_on_same_cells",
                        "published_cell_WAPE", "sample_support_fraction",
                    ]],
                    hide_index=True, use_container_width=True,
                )

        with class_tab:
            st.subheader("Class-level source residuals")
            st.dataframe(
                pd.DataFrame(report["metrics"]["segments"]["vehicle_type"]),
                hide_index=True, use_container_width=True,
            )
            st.subheader("Residuals by published cell size")
            frame = pd.DataFrame(report["metrics"]["segments"]["published_count_band"])
            st.dataframe(
                frame[["label", "source_cell_count",
                       "published_cell_WAPE", "sample_support_fraction"]],
                hide_index=True, use_container_width=True,
            )
            st.caption(
                "Published-cell thresholds of at least 100 help avoid "
                "interpreting low-count confidentialised cells as precise truth."
            )

        with sampling_tab:
            st.subheader("Sampling variation: fixed model, different random seeds")
            if not SENSITIVITY.is_file():
                st.info(
                    "Optional experiment not yet run. In PowerShell: "
                    "py -3 scripts/m14_validate.py --sensitivity "
                    "--sizes 85000,220000 --seeds 17,53,91"
                )
            else:
                sensitivity = _load(str(SENSITIVITY), SENSITIVITY.stat().st_mtime_ns)
                if (sensitivity.get("pipeline") != "m14a-independent-validation-v1"
                    or sensitivity.get("holdout_used_for_parameter_tuning") is not False):
                    st.error("Unrecognised sensitivity report.")
                else:
                    samples = pd.DataFrame(sensitivity["runs"])
                    if not samples.empty:
                        st.scatter_chart(
                            samples,
                            x="sample_size", y="heldout_B26_14_WAPE",
                            x_label="Weighted synthetic rows",
                            y_label="Published-cell WAPE (fraction)",
                        )
                        st.dataframe(
                            samples[[
                                "sample_size", "seed",
                                "heldout_B26_14_WAPE", "published_key_coverage",
                                "before_1980_WAPE", "before_1990_WAPE",
                                "synthetic_sample_ESS",
                            ]],
                            hide_index=True, use_container_width=True,
                        )
                    st.subheader("Across-seed standard deviations")
                    st.dataframe(
                        pd.DataFrame(sensitivity["summaries"]),
                        hide_index=True, use_container_width=True,
                    )
                    st.caption(
                        "The standard deviation across seeds only measures "
                        "finite Monte Carlo variability with fixed published "
                        "sources and fixed model coefficients; it is not a "
                        "confidence interval for the true fleet size or "
                        "for estimated make/model/postcode intersections."
                    )
        st.caption(
            "Release decision: diagnostic research only. "
            "M1.4b will investigate model calibration after this residual "
            "and stability evidence is reviewed."
        )
