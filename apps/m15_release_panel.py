"""M1.5 local research population registry within the existing Streamlit explorer.

The selector is read-only. It verifies the selected release's SHA-identified
Parquet, publication schema, synthetic flag and every original four-way
control before showing any derived weighted population. It does not
promote a candidate model, edit a release or expose raw government rows.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from insurance_market_au.population import PopulationStore, list_populations

ROOT = Path(__file__).resolve().parents[1]

st.subheader("M1.5 — Population release registry")
st.caption(
    "Frozen local research assets, each with its own verified fleet sample, "
    "original four-way accounting controls and source/quality evidence. "
    "A published asset is not a commercial population approval."
)
items=list_populations(ROOT)
ready=[r for r in items if r["status"]=="published"]
if not ready:
    st.info(
        "No frozen synthetic population releases yet. In PowerShell run "
        "'py -3 scripts/m15_release.py --publish baseline', "
        "and optionally '--publish candidate' after M1.4b calibration. "
        "Then refresh this page."
    )
else:
    labels={r["release_id"]: (
        r["release_id"]+" • "+r["model_version"]+
        " • "+f'{r["rows"]:,}'+" weighted rows"
    ) for r in ready}
    chosen=st.selectbox("Frozen population release",options=list(labels),
                        format_func=lambda rid:labels[rid])
    try:
        store=PopulationStore(chosen,root=ROOT)
    except (ValueError,OSError,KeyError,RuntimeError) as exc:
        st.error(
            "The selected release could not be verified. Its files or "
            "metadata may have changed. This must be investigated, not silently repaired."
        )
        st.code(str(exc))
    else:
        pin=store.pin()
        physical=store.report["physical_checks"]
        a,b,c,d=st.columns(4)
        a.metric("Expected registered fleet",f'{physical["expected_vehicles"]:,.0f}')
        b.metric("Synthetic weighted rows",f'{physical["synthetic_rows"]:,}')
        c.metric("Four-way accounting residual",f'{physical["maximum_fourway_count_residual"]:.8f}')
        d.metric("Weighted ESS",f'{physical["effective_sample_size"]:,.0f}')
        st.success("SHA, schema and original four-way accounting controls verified",icon="✅")
        st.warning(
            "This is a verified, **research-only** synthetic asset. "
            "No accuracy guarantee for rare make/model/postcode counts, "
            "no direct insurance exposure, and no approval for commercial pricing.",
            icon="⚠️",
        )
        st.caption(
            "Model provenance: "+store.manifest["synthesis"]["model_version"]+
            " • reference date "+store.reference_date+
            " • dataset contract "+store.dataset_schema_version
        )
        st.subheader("Explore a frozen release")
        dimension=st.selectbox(
            "Breakdown",
            ["registered_state","vehicle_type","manufacture_year",
             "motive_power","make","registered_postcode","garaging_postcode"],
            key="m15_released_dimension",
        )
        registered_states = store.aggregate(group_by=("registered_state",),max_groups=100)
        states = sorted(x["dimensions"]["registered_state"]
                        for x in registered_states["returned_groups"])
        state=st.selectbox(
            "State of registration (optional)",
            ["All states",*states],
            key="m15_released_state",
        )
        selected_filters=None if state=="All states" else {"registered_state":state}
        summary=store.aggregate(group_by=(dimension,),filters=selected_filters,max_groups=20)
        st.caption(
            f'{summary["total_synthetic_rows"]:,} synthetic representative rows support '
            f'{summary["total_estimated_registered_vehicles"]:,.0f} estimated '
            "registered vehicles for this selection. "
            "The strongest claims supported by the sample are four-way accounting controls, "
            "not its unvalidated additional relationships."
        )
        if summary["returned_groups"]:
            view=pd.DataFrame([
                {
                    dimension:g["dimensions"][dimension],
                    "Modelled vehicles":g["estimated_registered_vehicles"],
                    "Synthetic rows":g["synthetic_sample_rows"],
                    "Effective sample size":g["effective_sample_size"],
                    "Interpretation":g["support_status"],
                }
                for g in summary["returned_groups"]
            ])
            st.dataframe(view,hide_index=True,use_container_width=True)
            st.bar_chart(view.set_index(dimension)["Modelled vehicles"],
                         y_label="Modelled registered fleet")
            if summary["omitted_group_count"]:
                st.caption(
                    f'{summary["omitted_group_count"]:,} smaller groups omitted '
                    "from the displayed top-20, not treated as zeros."
                )
        else:
            st.info(
                "No synthetic rows matched the chosen filters. "
                "This does NOT establish that the real Australian population is zero."
            )
        st.subheader("Pinned downstream dependency")
        st.caption(
            "M2 enrichment and future market scenarios should store this exact "
            "release ID and asset SHA. Never reference a mutable 'latest' population."
        )
        st.code(json.dumps(pin,indent=2),language="json")
        st.download_button(
            label="Export population dependency pin",
            data=json.dumps(pin,indent=2)+"\n",
            file_name=chosen+"-population-pin.json",
            mime="application/json",
        )
        with st.expander("Quality gates and model limitations"):
            st.json(store.quality["quality_gates"])
            for value in store.quality["limitations"]:
                st.caption("• "+value)
