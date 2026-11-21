"""Local M1.3a four-attribute expected-fleet explorer.

From repository root:
    py -3 -m pip install -e ".[data,model,explore]"
    py -3 -m streamlit run apps/m13_explorer.py

All input/output stay in local git-ignored data directories.
"""
from __future__ import annotations
from pathlib import Path
import json

import pandas as pd
import pyarrow.parquet as pq
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
JOINT=ROOT/"data/processed/m13/joint-state-type-year-fuel.parquet"
REPORT=ROOT/"data/reports/m13/pilot-validation.json"
# Preserve the original command and its M1.3a fallback. Once the expanded
# local weighted sample exists, load the new make/model/geography interface.
# Exactly one page calls set_page_config() per Streamlit run.
if (ROOT / "data/processed/m13b/weighted-synthetic-fleet.parquet").is_file():
    import runpy
    runpy.run_path(str(ROOT / "apps/m13b_explorer.py"), run_name="__main__")
    st.stop()

st.set_page_config(page_title="Australian Fleet M1.3a",layout="wide")
st.title("Synthetic Australian vehicle population — M1.3a")
st.caption("31 January 2026 BITRE | modelled expected counts, NOT real vehicles or insured policies")
if not JOINT.is_file() or not REPORT.is_file():
    st.error("First run from the repository root: py -3 scripts/m13_fit.py")
    st.stop()

@st.cache_data(show_spinner=False)
def read_data(joint_path:str,report_path:str):
    return (pq.read_table(joint_path).to_pandas(),
            json.loads(Path(report_path).read_text(encoding="utf-8")))

df,report=read_data(str(JOINT),str(REPORT))
st.warning(
    "This is a synthetic, four-attribute model. Make/model, postcode, "
    "insurance coverage, and individual vehicle identity are NOT inferred. "
    "Published counts are disclosure-adjusted.",icon="⚠️"
)
a,b,c,d=st.columns(4)
a.metric("Published national accounting anchor",f"{report['published_total_operational_anchor']:,}")
b.metric("Supported synthetic cells",f"{report['joint_support_cells']:,}")
c.metric("Prior B26-10 heldout WAPE",f"{100*report['initial_holdout']['overall_published_cell_wape']:.2f}%")
d.metric("Fitted B26-10 heldout WAPE",f"{100*report['fitted_holdout']['overall_published_cell_wape']:.2f}%")
st.caption("Heldout B26-10 is a separate published aggregate projection, NOT vehicle-level ground truth.")

with st.sidebar:
    st.header("Vehicle filters")
    states=sorted(df.registered_state.dropna().unique().tolist())
    classes=sorted(df.vehicle_type.dropna().unique().tolist())
    fuels=sorted(df.motive_power.dropna().unique().tolist())
    chosen_states=st.multiselect("Registration states",states,default=states)
    chosen_classes=st.multiselect("Vehicle classes",classes,default=classes)
    chosen_fuels=st.multiselect("Motive powers",fuels,default=fuels)
    latest_year=st.slider("Latest year of manufacture",1900,2026,2026)
    only_known_years=st.checkbox("Exclude unspecified years",False)

df=df[df.registered_state.isin(chosen_states)
      & df.vehicle_type.isin(chosen_classes)
      & df.motive_power.isin(chosen_fuels)].copy()
df["year_number"]=pd.to_numeric(df["manufacture_year"],errors="coerce")
df=df[df.year_number.isna()|(df.year_number<=latest_year)]
if only_known_years:
    df=df[df.year_number.notna()]
count_col="expected_synthetic_vehicles"
total=float(df[count_col].sum())
st.metric("Fitted expected count in selection",f"{total:,.0f}")
st.caption(f"Selected share of published fleet accounting anchor: {100*total/report['published_total_operational_anchor']:.3f}%")
left,right=st.columns(2)
with left:
    st.subheader("By registration state")
    st.bar_chart(df.groupby("registered_state")[count_col].sum().sort_values(ascending=False),
                 y_label="Expected vehicles")
with right:
    st.subheader("By motive power")
    st.bar_chart(df.groupby("motive_power")[count_col].sum().sort_values(ascending=False),
                 y_label="Expected vehicles")
left,right=st.columns(2)
with left:
    st.subheader("By vehicle class")
    st.bar_chart(df.groupby("vehicle_type")[count_col].sum().sort_values(ascending=False),
                 y_label="Expected vehicles")
with right:
    st.subheader("By year of manufacture")
    years=df[df.year_number.notna()]
    if len(years):
        st.line_chart(years.groupby(years.year_number.astype(int))[count_col].sum(),
                      y_label="Expected vehicles")
    else:
        st.info("No numeric manufacture years under the current filter.")

st.subheader("Historic-vehicle held-out validation")
older=report.get("heldout_segment_diagnostics",{}).get("age_cohorts",{})
if older:
    st.dataframe(pd.DataFrame([
        {"Cohort":name.replace("manufactured_","").replace("_"," "),
         "B26-10 published cell total":metrics["published_reference_sum"],
         "Heldout WAPE":metrics["published_cell_WAPE"],
         "Published cells":metrics["published_holdout_cells"]}
        for name,metrics in older.items()
    ]),hide_index=True,use_container_width=True)
st.subheader("Modelling scope")
st.write(
    "Training: B26-01, B26-02 and B26-03, with Table 1 state/type accounting "
    "controls. B26-10 is strictly held out. Different jurisdictions and "
    "date vintages have NOT been forced into January 2026. The output is "
    "neither individual vehicle data nor an insurable-risk portfolio."
)
